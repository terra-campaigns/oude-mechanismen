#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "pypdf>=6.0.0",
#     "pyyaml>=6.0.0",
# ]
# ///
"""
Compile Tier 3 reference routing index (.agents/context/references.json) from
Markdown digests in the campaign's _gm-materials/digests/ directory.

Setting-agnostic: contains zero campaign lore. Discovers sources dynamically.
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import unquote
import yaml

try:
    import pypdf
except ImportError:
    pypdf = None


def ensure_heading_blank_lines(text: str) -> str:
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if re.match(r"^#{1,6}\s+\S", line):
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                out.append("")
    return "\n".join(out).strip() + "\n"


def find_repo_root(custom_dir: str = None) -> Path:
    """Detect the campaign repository root directory by walking parent directories."""
    if custom_dir:
        p = Path(custom_dir).resolve()
        if p.exists() and p.is_dir():
            return p
        raise FileNotFoundError(f"Provided repository directory '{custom_dir}' does not exist.")

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "_config.yml").exists() or (candidate / ".agents").is_dir():
            return candidate

    raise FileNotFoundError(
        f"Could not locate a campaign repository from current directory '{cwd}'. "
        f"Please run from within a campaign vault or pass --repo-root."
    )


def find_drive_dir(repo_root: Path, explicit_drive_dir: Optional[str] = None) -> Path:
    repo_root = repo_root.resolve()
    if explicit_drive_dir:
        raw = Path(explicit_drive_dir).expanduser()
        target = raw.resolve() if raw.is_absolute() else (repo_root / raw).resolve()
        if target.is_dir():
            return target
        raise FileNotFoundError(f"Explicit drive_dir '{explicit_drive_dir}' does not exist or is not a directory.")

    config_file = repo_root / ".agents" / "context" / "tier1_sources.yml"
    if config_file.exists():
        # Non-YAML read failures (OSError, UnicodeDecodeError, yaml.YAMLError) propagate loudly
        # instead of silently falling back to repo_root.
        cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
        if not isinstance(cfg, dict):
            cfg = {}
        raw_drive = cfg.get("drive_dir")
        if raw_drive:
            raw = Path(str(raw_drive)).expanduser()
            target = raw.resolve() if raw.is_absolute() else (repo_root / raw).resolve()
            if target.is_dir():
                return target
            raise FileNotFoundError(
                f"Configured 'drive_dir' path '{raw_drive}' does not exist or is not a directory. "
                f"Please verify {config_file}."
            )

    if repo_root.is_dir():
        return repo_root
    raise FileNotFoundError(f"Repository root '{repo_root}' does not exist or is not a directory.")


def _parse_frontmatter(content: str) -> Tuple[Optional[Dict[str, Any]], str, str, Optional[str]]:
    """Split leading YAML frontmatter from *content*.

    Returns (mapping_or_None, fm_prefix, body, error_or_None). Only YAML mapping
    headers populate the dict; empty, scalar, or list headers return an error string
    while preserving fm_prefix='' and body=content for callers that tolerate bare text.
    """
    if not content.startswith("---"):
        return None, "", content, "missing YAML frontmatter block"
    fm_match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n?", content, flags=re.DOTALL)
    if not fm_match:
        return None, "", content, "malformed frontmatter delimiters"
    try:
        loaded = yaml.safe_load(fm_match.group(1))
    except yaml.YAMLError as exc:
        return None, "", content, f"malformed YAML frontmatter: {exc}"
    if not isinstance(loaded, dict):
        return None, "", content, f"frontmatter must be a YAML mapping, got {type(loaded).__name__}"
    return loaded, content[: fm_match.end()], content[fm_match.end() :], None


def compile_references(repo_root: Path, drive_dir: Path, clean_headings: bool = False):
    digests_dir = drive_dir / "_gm-materials" / "digests"
    if not digests_dir.exists():
        print(f"[WARN] No _gm-materials/digests directory found at {digests_dir}")
        return

    md_files = sorted(digests_dir.rglob("*.md"), key=lambda p: p.as_posix())
    if not md_files:
        print(f"[WARN] No Markdown digest files found in {digests_dir}")
        return

    sources = []

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        # Only split frontmatter when the leading '---' block parses as a YAML mapping;
        # Markdown thematic breaks and non-mapping YAML (lists, scalars) stay in the body.
        loaded, fm_prefix, body, _ = _parse_frontmatter(content)
        frontmatter: Dict[str, Any] = loaded if loaded is not None else {}

        if clean_headings:
            cleaned_body = ensure_heading_blank_lines(body)
            cleaned = fm_prefix + cleaned_body
            if cleaned != content:
                md_file.write_text(cleaned, encoding="utf-8")
                body = cleaned_body

        body_lines = body.splitlines()
        title = md_file.stem
        source_pdf = None

        # 1. Parse Title
        for line in body_lines[:5]:
            m = re.match(r"^#\s+(.+?)(?:\s*—\s*Reference Digest)?$", line)
            if m:
                title = m.group(1).strip()
                break
        if frontmatter.get("title") is not None and str(frontmatter.get("title")).strip():
            title = str(frontmatter["title"]).strip()

        # 2. Parse Source PDF
        raw_src = None
        if frontmatter.get("source_pdf") is not None and str(frontmatter.get("source_pdf")).strip():
            raw_src = str(frontmatter["source_pdf"]).strip()
        else:
            for line in body_lines[:10]:
                m = re.search(r"(?:Source(?:\s+PDF)?):\s*(?:\*\*\s*)?(?:Google Drive\s*)?`([^`]+)`", line, flags=re.IGNORECASE)
                if m:
                    raw_src = m.group(1).strip()
                    break

        if raw_src:
            if raw_src.startswith("/"):
                # Normalise host-specific absolute paths: relative POSIX when inside
                # drive_dir, otherwise the portable basename (zero host paths in references.json).
                abs_src = Path(raw_src).resolve()
                try:
                    source_pdf = abs_src.relative_to(drive_dir.resolve()).as_posix()
                except ValueError:
                    source_pdf = abs_src.name
            else:
                source_pdf = Path(raw_src).as_posix()

        # 3. Categorisation heuristic (derived from source folder and generic keywords)
        stem = md_file.stem.lower()
        src_lower = f"/{(source_pdf or '').lower().lstrip('/')}"

        if "postcard" in stem or "/postcards/" in src_lower:
            category = "postcards"
        elif "map" in stem or "/maps/" in src_lower:
            category = "maps"
        elif "player_guide" in stem:
            category = "player_guide"
        elif any(k in stem for k in ["analysis", "research"]) or "/research/" in src_lower:
            category = "research_aesthetic"
        elif "/cores/" in src_lower or any(k in stem for k in ["core", "rules", "setting"]):
            category = "core_setting"
        elif any(k in src_lower for k in ["/supplements/", "/suplements/"]) or "supplement" in stem:
            category = "supplement"
        elif any(k in src_lower for k in ["/modules/", "/scenarios/"]) or any(k in stem for k in ["module", "scenario"]):
            category = "module"
        else:
            category = "module"

        # 4. Parse Headings & Sections
        sections = []
        for idx, line in enumerate(body_lines, start=fm_prefix.count("\n") + 1):
            m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
            if m:
                sections.append({
                    "level": len(m.group(1)),
                    "heading": m.group(2).strip(),
                    "line": idx
                })

        slug = md_file.relative_to(digests_dir).with_suffix("").as_posix()
        digest_path = md_file.relative_to(drive_dir).as_posix()

        entry: Dict[str, Any] = {
            "slug": slug,
            "title": title,
            "category": category,
            "tier": 3,
            "source_pdf": source_pdf,
            "digest_path": digest_path,
            "digest_exists": True,
            "sections": sections,
        }
        for opt_key in ("entity_type", "pages", "tags", "source"):
            if opt_key in frontmatter and frontmatter[opt_key] is not None:
                entry[opt_key] = frontmatter[opt_key]

        sources.append(entry)

    # Write output to repo idempotently (preserve timestamp if sources unchanged)
    campaign_name = repo_root.name
    out_file = repo_root / ".agents" / "context" / "references.json"
    generated_time = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")

    if out_file.exists():
        try:
            existing = json.loads(out_file.read_text(encoding="utf-8"))
            if existing.get("sources") == sources:
                generated_time = existing.get("generated", generated_time)
        except Exception:
            pass

    payload = {
        "generated": generated_time,
        "tier": 3,
        "campaign": campaign_name,
        "note": f"Tier 3 reference routing index — influence only, never automatic {campaign_name.title()} canon.",
        "total_sources": len(sources),
        "sources": sources
    }

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[INDEX] Successfully compiled {len(sources)} reference sources from {digests_dir} to {out_file}")


def slugify(text: str) -> str:
    """Convert text into a clean snake_case slug."""
    text = re.sub(r"[\s\-]+", "_", text.strip())
    text = re.sub(r"[^\w_]", "", text)
    return text.lower()


def format_title_from_stem(stem: str) -> str:
    """Format a human-readable title from a PDF filename stem."""
    s = re.sub(r"[-_]v\d+.*$", "", stem, flags=re.IGNORECASE)
    s = re.sub(r"[-_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s.title()


def extract_pdf_outline(reader: Any, max_depth: int = 1) -> List[Tuple[str, int, int]]:
    """Extract outline items up to max_depth with computed page ranges (title, start_page, end_page)."""
    if not getattr(reader, "outline", None):
        return []

    def parse_items(items: Any, current_depth: int, target_depth: int) -> List[Tuple[str, int]]:
        res: List[Tuple[str, int]] = []
        for it in items:
            if isinstance(it, list):
                if current_depth < target_depth:
                    res.extend(parse_items(it, current_depth + 1, target_depth))
            else:
                try:
                    p = reader.get_destination_page_number(it) + 1
                    t = getattr(it, "title", str(it)).strip()
                    if t:
                        res.append((t, p))
                except Exception:
                    pass
        return res

    raw_items = parse_items(reader.outline, 1, max_depth)

    # Adaptive expansion: if top-level outline has fewer than 3 items and deeper nodes exist, expand to depth 2
    if len(raw_items) < 3 and max_depth == 1:
        deeper = parse_items(reader.outline, 1, 2)
        if len(deeper) >= 3:
            raw_items = deeper

    if not raw_items:
        return []

    # Deduplicate preserving order
    seen: set = set()
    dedup: List[Tuple[str, int]] = []
    for t, p in raw_items:
        if (t, p) not in seen:
            seen.add((t, p))
            dedup.append((t, p))

    sorted_items = sorted(dedup, key=lambda x: x[1])
    total_pages = len(reader.pages)
    ranges: List[Tuple[str, int, int]] = []
    for idx, (title, start_p) in enumerate(sorted_items):
        if idx + 1 < len(sorted_items):
            next_p = sorted_items[idx + 1][1]
            end_p = max(start_p, next_p - 1)
        else:
            end_p = max(start_p, total_pages)
        ranges.append((title, start_p, end_p))

    return ranges


def scaffold_digest(
    repo_root: Path,
    drive_dir: Path,
    pdf_path: str,
    custom_slug: Optional[str] = None,
    category: Optional[str] = None,
    depth: int = 1,
    force: bool = False,
    source_pdf: Optional[str] = None
) -> Path:
    """Scaffold a new Tier 3 Markdown digest from an explicit PDF path using pypdf outline metadata."""
    if pypdf is None:
        raise ImportError(
            "pypdf is required for digest scaffolding. Please install it using 'pip install pypdf'."
        )

    # Resolve the explicit PDF path; never scan drive_dir for candidates.
    resolved = _resolve_pdf_path(drive_dir, pdf_path)

    rel_path = _portable_source_pdf(resolved, drive_dir, source_pdf)

    if custom_slug:
        slug = slugify(custom_slug)
    else:
        clean_stem = re.sub(r"[-_]v\d+.*$", "", resolved.stem, flags=re.IGNORECASE)
        slug = slugify(clean_stem)

    digests_dir = drive_dir / "_gm-materials" / "digests"
    out_file = digests_dir / f"{slug}.md"

    if out_file.exists() and not force:
        raise FileExistsError(
            f"Digest already exists at {out_file}. Pass --force to overwrite."
        )

    reader = pypdf.PdfReader(str(resolved))
    total_pages = len(reader.pages)

    doc_title = None
    if reader.metadata and reader.metadata.title:
        candidate_title = str(reader.metadata.title).strip()
        if candidate_title and not candidate_title.lower().endswith(".pdf"):
            doc_title = candidate_title

    if not doc_title:
        doc_title = format_title_from_stem(resolved.stem)

    if not category:
        parent_name = resolved.parent.name.lower()
        if "core" in parent_name or "core" in slug:
            category = "core_setting"
        elif "module" in parent_name or "incursion" in slug or "adventure" in slug:
            category = "module"
        elif "suplement" in parent_name or "supplement" in parent_name:
            category = "supplement"
        else:
            category = "supplement"

    ranges = extract_pdf_outline(reader, max_depth=depth)
    contents_lines: List[str] = []
    if ranges:
        for t, s, e in ranges:
            page_cite = f"p. {s}" if s == e else f"pp. {s}–{e}"
            contents_lines.append(f"- **{t}** [{page_cite}]: Summary of sections and content.")
    else:
        p_split = min(10, total_pages)
        contents_lines.append(f"- **Overview & Introduction** [pp. 1–{p_split}]: Premise, core rules, and themes.")
        if total_pages > p_split:
            contents_lines.append(f"- **Main Rules & Tables** [pp. {p_split + 1}–{total_pages}]: Reference procedures and generators.")

    campaign_title = repo_root.name.replace("-", " ").replace("_", " ").title()

    lines = [
        f"# {doc_title} — Reference Digest",
        "",
        "> [!NOTE]",
        f"> Tier 3 Canon (Influence & Reference Only). Source: `{rel_path}`. Nothing here is automatic {campaign_title} campaign canon unless formally adopted in Tier 1 notes or Tier 2 rulings.",
        "",
        "## Contents & Page Map",
        "",
        *contents_lines,
        "",
        "## Key Procedures & Mechanics",
        "",
        "- Key procedure or table summary.",
        ""
    ]

    out_content = ensure_heading_blank_lines("\n".join(lines))
    digests_dir.mkdir(parents=True, exist_ok=True)
    out_file.write_text(out_content, encoding="utf-8")
    print(f"[SCAFFOLD] Successfully created digest scaffold at {out_file} (extracted {len(ranges)} sections at depth {depth})")

    compile_references(repo_root, drive_dir)
    return out_file


def _portable_source_pdf(resolved: Path, drive_dir: Path, source_pdf: Optional[str] = None) -> str:
    """Portable identifier: explicit override, drive-relative POSIX path, or basename."""
    if source_pdf:
        return source_pdf
    try:
        return resolved.relative_to(drive_dir.resolve()).as_posix()
    except ValueError:
        return resolved.name


def _resolve_pdf_path(drive_dir: Path, pdf_path: str) -> Path:
    """Resolve an explicit PDF path (CWD-relative first, then drive_dir-relative); never scan for candidates."""
    raw = Path(pdf_path).expanduser()
    if raw.is_absolute():
        resolved = raw.resolve()
    else:
        cwd_candidate = raw if raw.exists() else None
        if cwd_candidate is not None:
            resolved = cwd_candidate.resolve()
        else:
            resolved = (drive_dir / raw).expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Explicit PDF path '{pdf_path}' does not exist or is not a file.")
    return resolved


def _page_text(reader: Any, page_no: int, cache: Dict[int, Tuple[str, int]]) -> str:
    """Return layout-mode UTF-8 text for a 1-based page number; cache maps page to (text, utf8_byte_len)."""
    if page_no not in cache:
        try:
            text = reader.pages[page_no - 1].extract_text(extraction_mode="layout") or ""
        except TypeError:
            text = reader.pages[page_no - 1].extract_text() or ""
        except Exception:
            text = ""
        cache[page_no] = (text, len(text.encode("utf-8")))
    return cache[page_no][0]


def _span_bytes(reader: Any, cache: Dict[int, Tuple[str, int]], start: int, end: int) -> int:
    total = 0
    for p in range(start, end + 1):
        _page_text(reader, p, cache)
        # Include the '--- Page N ---\n' marker plus trailing newline added at emit time,
        # so planned windows never exceed max_bytes once markers are wrapped in.
        total += cache[p][1] + len(f"--- Page {p} ---\n".encode("utf-8")) + 1
    return total


def _split_window(
    title: str,
    start: int,
    end: int,
    chunk_pages: int,
    max_bytes: int,
    reader: Any,
    cache: Dict[int, Tuple[str, int]],
) -> List[Tuple[str, int, int]]:
    """Split an outline span into (title, start_page, end_page) windows whose text fits *max_bytes*.

    Spans larger than *chunk_pages* are first split into sequential chunk-sized windows;
    any still-oversized window is halved recursively down to single pages. A single
    oversized page is kept whole here and line-split at emit time.
    """
    if end < start:
        return []
    if start == end or _span_bytes(reader, cache, start, end) <= max_bytes:
        return [(title, start, end)]
    out: List[Tuple[str, int, int]] = []
    if end - start + 1 > chunk_pages:
        p = start
        while p <= end:
            e = min(end, p + chunk_pages - 1)
            out.extend(_split_window(title, p, e, chunk_pages, max_bytes, reader, cache))
            p = e + 1
    else:
        mid = (start + end) // 2
        out.extend(_split_window(title, start, mid, chunk_pages, max_bytes, reader, cache))
        out.extend(_split_window(title, mid + 1, end, chunk_pages, max_bytes, reader, cache))
    return out


def plan_extract_windows(
    reader: Any,
    max_depth: int,
    chunk_pages: int,
    max_bytes: int,
    skip_text_sizing: bool = False,
) -> Tuple[List[Tuple[str, int, int]], Dict[int, Tuple[str, int]]]:
    """Flatten the outline into page-span windows sized below *max_bytes*; outline-less PDFs get one whole-book span."""
    total = len(reader.pages)
    spans = extract_pdf_outline(reader, max_depth=max_depth) or [("Whole Book", 1, total)]
    if spans and spans[0][1] > 1:
        # Pages before the first outline bookmark (cover, front matter) are still extracted.
        spans = [("Front Matter", 1, spans[0][1] - 1)] + spans
    cache: Dict[int, Tuple[str, int]] = {}
    if skip_text_sizing:
        return spans, cache
    windows: List[Tuple[str, int, int]] = []
    for title, start, end in spans:
        windows.extend(_split_window(title, start, end, chunk_pages, max_bytes, reader, cache))
    return windows, cache


def _cut_prefix(text: str, max_bytes: int) -> int:
    """Largest character count of *text* whose UTF-8 encoding fits in *max_bytes*."""
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if len(text[:mid].encode("utf-8")) <= max_bytes:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _split_single_page(body: str, page_no: int, max_bytes: int) -> List[str]:
    """Line-split a single oversized page into <= *max_bytes* parts, accounting upfront for '--- Page N (part K) ---' markers."""
    marked: List[str] = []
    cur = ""
    k = 1

    def part_room(part_idx: int) -> Tuple[str, int]:
        marker = f"--- Page {page_no} (part {part_idx}) ---\n"
        room = max_bytes - len(marker.encode("utf-8"))
        if room < 4:
            raise ValueError(f"max_bytes ({max_bytes}) too small to fit page part marker and UTF-8 text")
        return marker, room

    for line in body.splitlines(keepends=True):
        while line:
            marker, room = part_room(k)
            if len((cur + line).encode("utf-8")) <= room:
                cur += line
                line = ""
            elif cur:
                marked.append(marker + cur)
                cur = ""
                k += 1
            else:
                cut = _cut_prefix(line, room)
                marked.append(marker + line[:cut])
                line = line[cut:]
                k += 1
    if cur or not marked:
        marker, _ = part_room(k)
        marked.append(marker + cur)
    return marked


def _parse_page_ranges(spec: str, total_pages: Optional[int] = None) -> set:
    """Parse a page-range spec like '2,5-8,12' into a validated set of 1-based page numbers."""
    pages: set = set()
    for raw_part in spec.split(","):
        part = raw_part.strip()
        if not part:
            continue
        if not re.match(r"^\d+(?:-\d+)?$", part):
            raise ValueError(f"Invalid --pages token '{part}' in '{spec}'; expected 'N' or 'A-B'.")
        if "-" in part:
            a_str, b_str = part.split("-", 1)
            a, b = int(a_str), int(b_str)
            if a < 1 or b < a:
                raise ValueError(f"Invalid --pages range '{part}' in '{spec}'; expected 1 <= A <= B.")
            if total_pages is not None and b > total_pages:
                raise ValueError(f"Page range '{part}' exceeds PDF page count ({total_pages}).")
            pages.update(range(a, b + 1))
        else:
            p = int(part)
            if p < 1:
                raise ValueError(f"Invalid --pages number '{part}' in '{spec}'; expected >= 1.")
            if total_pages is not None and p > total_pages:
                raise ValueError(f"Page {p} exceeds PDF page count ({total_pages}).")
            pages.add(p)
    if not pages:
        raise ValueError(f"Empty --pages specification '{spec}'.")
    return pages


def extract_pdf(
    pdf_path: str,
    drive_dir: Path,
    out_dir: Optional[str] = None,
    format: str = "auto",
    max_depth: int = 1,
    chunk_pages: int = 10,
    pdf_slice_pages: int = 5,
    max_bytes: int = 38000,
    min_chars_per_page: int = 80,
    page_spec: Optional[str] = None,
    source_pdf: Optional[str] = None,
) -> Path:
    """Extract bounded page-tagged slices from an explicit PDF into *out_dir* plus a manifest.json.

    format="text" emits layout-mode UTF-8 slices with '--- Page N ---' markers; format="pdf"
    emits PdfWriter page-range slices; format="auto" falls back to .pdf per page when the
    extracted character density drops below *min_chars_per_page*. With *page_spec* (e.g.
    "209-211,261"), those pages are forced to the requested format while all other pages keep
    their prior (or auto) decisions, and the manifest is rebuilt in monotonic page order.
    """
    if pypdf is None:
        raise ImportError("pypdf is required for PDF extraction. Please install it using 'pip install pypdf'.")
    resolved = _resolve_pdf_path(drive_dir, pdf_path)
    portable_src = _portable_source_pdf(resolved, drive_dir, source_pdf)
    slug = slugify(re.sub(r"[-_]v\d+.*$", "", resolved.stem, flags=re.IGNORECASE))
    target_dir = Path(out_dir) if out_dir else Path(tempfile.gettempdir()) / "oude-extract" / slug
    manifest_path = target_dir / "manifest.json"

    reader = pypdf.PdfReader(str(resolved))
    total_pages = len(reader.pages)
    page_filter = _parse_page_ranges(page_spec, total_pages=total_pages) if page_spec else None

    target_dir.mkdir(parents=True, exist_ok=True)
    if page_filter is None:
        for old in list(target_dir.glob("*.txt")) + list(target_dir.glob("*.pdf")):
            old.unlink()
        if manifest_path.exists():
            manifest_path.unlink()

    # On --pages override runs, carry over per-page format decisions from the prior manifest
    # so earlier overrides are preserved instead of reverting to auto.
    prior: Dict[int, Tuple[str, Optional[str]]] = {}
    prior_format_requested: Optional[str] = None
    if page_filter is not None and manifest_path.exists():
        old_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        prior_format_requested = old_manifest.get("format_requested")
        for s in old_manifest.get("slices", []):
            for p in range(s["start_page"], s["end_page"] + 1):
                prior[p] = (s["format"], s.get("auto_fallback_reason"))

    skip_text_sizing = format == "pdf" and (
        page_filter is None or (bool(prior) and not any(fmt == "text" for fmt, _ in prior.values()))
    )
    windows, cache = plan_extract_windows(
        reader, max_depth, chunk_pages, max_bytes, skip_text_sizing=skip_text_sizing
    )
    forced = set(page_filter) if page_filter is not None else set()

    def resolve_page_format(p: int) -> Tuple[str, Optional[str]]:
        if page_filter is not None and p not in forced:
            if p in prior:
                return prior[p]
            # Unforced pages without a prior manifest default to auto density checks.
            if len(_page_text(reader, p, cache)) < min_chars_per_page:
                return "pdf", (
                    f"low text density: page {p} has {len(_page_text(reader, p, cache))} chars "
                    f"below {min_chars_per_page} chars/page threshold"
                )
            return "text", None
        if format == "auto":
            if len(_page_text(reader, p, cache)) < min_chars_per_page:
                return "pdf", (
                    f"low text density: page {p} has {len(_page_text(reader, p, cache))} chars "
                    f"below {min_chars_per_page} chars/page threshold"
                )
            return "text", None
        return format, None

    slices: List[Dict[str, Any]] = []
    index = 0
    for title, start, end in windows:
        runs: List[Tuple[str, int, int]] = []
        reasons_by_page: Dict[int, str] = {}
        for p in range(start, end + 1):
            fmt, reason = resolve_page_format(p)
            if reason:
                reasons_by_page[p] = reason
            if runs and runs[-1][0] == fmt and p == runs[-1][2] + 1:
                runs[-1] = (fmt, runs[-1][1], p)
            else:
                runs.append((fmt, p, p))

        for fmt, run_start, run_end in runs:
            if fmt == "pdf":
                p = run_start
                while p <= run_end:
                    e = min(run_end, p + pdf_slice_pages - 1)
                    index += 1
                    fname = f"{index:03d}_{slugify(title)}_pp{p}-{e}.pdf"
                    writer = pypdf.PdfWriter()
                    for pg in range(p, e + 1):
                        writer.add_page(reader.pages[pg - 1])
                    with open(target_dir / fname, "wb") as fh:
                        writer.write(fh)
                    sub_chars = (
                        sum(len(_page_text(reader, pg, cache)) for pg in range(p, e + 1))
                        if not skip_text_sizing
                        else 0
                    )
                    slice_reason = next(
                        (reasons_by_page[pg] for pg in range(p, e + 1) if reasons_by_page.get(pg)),
                        None,
                    )
                    slices.append({
                        "index": index,
                        "title": title,
                        "start_page": p,
                        "end_page": e,
                        "format": "pdf",
                        "path": fname,
                        "byte_size": (target_dir / fname).stat().st_size,
                        "char_count": sub_chars,
                        "auto_fallback_reason": slice_reason,
                    })
                    p = e + 1
            else:
                run_text = "".join(
                    f"--- Page {p} ---\n{_page_text(reader, p, cache)}\n"
                    for p in range(run_start, run_end + 1)
                )
                byte_size = len(run_text.encode("utf-8"))
                if byte_size > max_bytes and run_start == run_end:
                    for part in _split_single_page(_page_text(reader, run_start, cache), run_start, max_bytes):
                        index += 1
                        fname = f"{index:03d}_{slugify(title)}_p{run_start}_part.txt"
                        (target_dir / fname).write_text(part, encoding="utf-8")
                        slices.append({
                            "index": index,
                            "title": f"{title} (part)",
                            "start_page": run_start,
                            "end_page": run_start,
                            "format": "text",
                            "path": fname,
                            "byte_size": len(part.encode("utf-8")),
                            "char_count": len(part),
                            "auto_fallback_reason": None,
                        })
                    continue
                index += 1
                fname = f"{index:03d}_{slugify(title)}.txt"
                (target_dir / fname).write_text(run_text, encoding="utf-8")
                slices.append({
                    "index": index,
                    "title": title,
                    "start_page": run_start,
                    "end_page": run_end,
                    "format": "text",
                    "path": fname,
                    "byte_size": byte_size,
                    "char_count": len(run_text),
                    "auto_fallback_reason": None,
                })

    if page_filter is not None:
        referenced = {s["path"] for s in slices}
        for stale in list(target_dir.glob("*.txt")) + list(target_dir.glob("*.pdf")):
            if stale.name not in referenced:
                stale.unlink()
    manifest = {
        "source_pdf": portable_src,
        "slug": slug,
        "total_pages": total_pages,
        "format_requested": (prior_format_requested or "auto") if page_filter is not None else format,
        "min_chars_per_page": min_chars_per_page,
        "slices": slices,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    text_n = sum(1 for s in slices if s["format"] == "text")
    pdf_n = len(slices) - text_n
    fb_n = sum(1 for s in slices if s.get("auto_fallback_reason"))
    print(f"[EXTRACT] {len(slices)} slice(s) ({text_n} text, {pdf_n} pdf, {fb_n} auto-fallback) from {resolved.name} ({total_pages} pages) into {target_dir}")
    print(f"[EXTRACT] Manifest written to {manifest_path}")
    return manifest_path


VALID_ENTITY_TYPES = {"index", "faction", "location", "person", "creature", "artefact", "mechanic", "table", "other"}
LINK_EXCLUDED_DIRS = {".git", "_site", "vendor"}
DIGEST_LINK_RE = re.compile(r'(!?)\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)')


def validate_digests(repo_root: Path, digest_dir: Path, manifest: Optional[str] = None) -> int:
    """Validate digest notes against hard invariants; return 0 on pass, 1 on any failure.

    Hard invariants: YAML-mapping frontmatter with non-empty 'source' and 'title', 'tier' == 3,
    'entity_type' in VALID_ENTITY_TYPES; a blank line immediately after every Markdown heading
    (outside fenced code blocks); every relative Markdown link resolves to an existing file inside
    the repository root (or *digest_dir* when validating external staging) and outside
    LINK_EXCLUDED_DIRS. Soft sizing stays non-fatal [INFO] output.
    """
    repo_root = repo_root.resolve()
    digest_dir = digest_dir.resolve()
    if not digest_dir.is_dir():
        print(f"[FAIL] {digest_dir}: digest directory does not exist")
        return 1
    md_files = sorted(digest_dir.rglob("*.md"), key=lambda p: p.as_posix())
    if not md_files:
        print(f"[FAIL] {digest_dir}: no markdown digest files found")
        return 1
    errors: List[str] = []
    total_lines = 0
    for md_file in md_files:
        resolved_md = md_file.resolve()
        rel = resolved_md.relative_to(repo_root).as_posix() if repo_root in resolved_md.parents else str(md_file)
        content = md_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        total_lines += len(lines)
        loaded, fm_prefix, _, fm_err = _parse_frontmatter(content)
        if fm_err:
            errors.append(f"{rel}:1: {fm_err}")
        elif loaded is not None:
            if not (isinstance(loaded.get("source"), str) and loaded["source"].strip()):
                errors.append(f"{rel}:1: frontmatter 'source' must be a non-empty string")
            if loaded.get("tier") != 3:
                errors.append(f"{rel}:1: frontmatter 'tier' must equal 3")
            if loaded.get("entity_type") not in VALID_ENTITY_TYPES:
                errors.append(f"{rel}:1: frontmatter 'entity_type' must be one of {sorted(VALID_ENTITY_TYPES)}")
            if not (isinstance(loaded.get("title"), str) and loaded["title"].strip()):
                errors.append(f"{rel}:1: frontmatter 'title' must be a non-empty string")

        fm_end_line = fm_prefix.count("\n")
        in_fence = False
        for line_no, line in enumerate(lines, start=1):
            if line_no <= fm_end_line:
                continue
            stripped = line.lstrip()
            if stripped.startswith("```") or stripped.startswith("~~~"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            if re.match(r"^#{1,6}\s+\S", line) and line_no < len(lines) and lines[line_no].strip() != "":
                errors.append(f"{rel}:{line_no}: heading not followed by a blank line")
            for m in DIGEST_LINK_RE.finditer(line):
                raw_target = m.group(3)
                if (
                    not raw_target
                    or raw_target.startswith(("http://", "https://", "mailto:", "#"))
                    or "{{" in raw_target
                    or "}}" in raw_target
                ):
                    continue
                target = unquote(raw_target.split("#", 1)[0].split("?", 1)[0])
                if not target:
                    continue
                link_resolved = (md_file.parent / target).resolve()
                # Links may resolve inside the repository root or inside the digest directory
                # itself (e.g. <out-dir>/staged/<source>/ validated outside the repo).
                inside_repo = repo_root in link_resolved.parents or link_resolved == repo_root
                inside_digest = digest_dir in link_resolved.parents or link_resolved == digest_dir
                if not (inside_repo or inside_digest):
                    errors.append(f"{rel}:{line_no}: link '{raw_target}' escapes the digest directory and repository root")
                    continue
                base = repo_root if inside_repo else digest_dir
                if any(part in LINK_EXCLUDED_DIRS for part in link_resolved.relative_to(base).parts):
                    errors.append(f"{rel}:{line_no}: link '{raw_target}' targets an excluded directory ({sorted(LINK_EXCLUDED_DIRS)})")
                    continue
                if not link_resolved.exists():
                    errors.append(f"{rel}:{line_no}: broken relative link '{raw_target}'")

    print(f"[INFO] {len(md_files)} digest note(s), {total_lines} total line(s) in {digest_dir}")
    if manifest:
        mpath = Path(manifest)
        if mpath.exists():
            data = json.loads(mpath.read_text(encoding="utf-8"))
            reasons: Dict[str, int] = {}
            for s in data.get("slices", []):
                reason = s.get("auto_fallback_reason")
                if reason:
                    key = reason.split(":", 1)[0].strip()
                    reasons[key] = reasons.get(key, 0) + 1
            if reasons:
                print(f"[INFO] auto-fallback slice counts: {json.dumps(reasons, ensure_ascii=False)}")
    for err in errors:
        print(f"[FAIL] {err}")
    if errors:
        print(f"[VALIDATE] {len(errors)} hard-invariant failure(s) in {digest_dir}")
        return 1
    print(f"[VALIDATE] OK — {len(md_files)} note(s) passed in {digest_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Compile Tier 3 reference index, scaffold digests, extract PDF slices, or validate digests.")
    parser.add_argument("--repo-root", "--repo-dir", dest="repo_root", type=str, default=None, help="Path to campaign repository (defaults to CWD)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Path to the campaign materials directory")
    parser.add_argument("--clean-headings", action="store_true", help="Ensure empty blank line after headings in digests")
    parser.add_argument("--scaffold", type=str, default=None, metavar="PDF_PATH", help="Scaffold a new Tier 3 Markdown digest from an explicit PDF path")
    parser.add_argument("--source-pdf", type=str, default=None, help="Portable identifier recorded as source_pdf for a scaffolded digest")
    parser.add_argument("--slug", type=str, default=None, help="Custom slug/filename for scaffolded digest")
    parser.add_argument("--category", type=str, default=None, help="Category for scaffolded digest (core_setting, supplement, module, rules, bestiary)")
    parser.add_argument("--depth", type=int, default=1, help="Maximum outline depth to extract (default: 1 for top-level chapters)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing digest file during scaffolding")
    parser.add_argument("--extract", type=str, default=None, metavar="PDF_PATH", help="Extract bounded page-tagged slices from an explicit PDF plus manifest.json")
    parser.add_argument("--format", choices=["auto", "text", "pdf"], default="auto", help="Slice format for --extract (default: auto with low-density pdf fallback)")
    parser.add_argument("--out-dir", type=str, default=None, help="Output directory for --extract slices (default: <tempdir>/oude-extract/<slug>)")
    parser.add_argument("--max-depth", type=int, default=1, help="Maximum outline depth for --extract (default: 1)")
    parser.add_argument("--chunk-pages", type=int, default=10, help="Page window size for oversized outline spans under --extract (default: 10)")
    parser.add_argument("--pdf-slice-pages", type=int, default=5, help="Pages per emitted .pdf slice under --extract (default: 5)")
    parser.add_argument("--max-bytes", type=int, default=38000, help="Maximum bytes per text slice under --extract (default: 38000)")
    parser.add_argument("--min-chars-per-page", type=int, default=80, help="Auto-fallback threshold for --extract --format auto (default: 80)")
    parser.add_argument("--pages", type=str, default=None, metavar="RANGES", help="Restrict --extract to page ranges (e.g. '209-211,261'); merges into an existing manifest, replacing those pages' slices")
    parser.add_argument("--validate", nargs="?", const="", default=None, metavar="DIGEST_DIR", help="Validate digest notes against hard invariants (default dir: <drive_dir>/_gm-materials/digests)")
    parser.add_argument("--manifest", type=str, default=None, help="manifest.json from --extract, used by --validate for auto-fallback telemetry")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    drive_dir = find_drive_dir(repo_root, args.drive_dir)

    if args.extract:
        extract_pdf(
            args.extract,
            drive_dir,
            out_dir=args.out_dir,
            format=args.format,
            max_depth=args.max_depth,
            chunk_pages=args.chunk_pages,
            pdf_slice_pages=args.pdf_slice_pages,
            max_bytes=args.max_bytes,
            min_chars_per_page=args.min_chars_per_page,
            page_spec=args.pages,
            source_pdf=args.source_pdf,
        )
    elif args.validate is not None:
        digest_dir = Path(args.validate) if args.validate else drive_dir / "_gm-materials" / "digests"
        if not digest_dir.is_absolute():
            digest_dir = repo_root / digest_dir
        raise SystemExit(validate_digests(repo_root, digest_dir, manifest=args.manifest))
    elif args.scaffold:
        scaffold_digest(
            repo_root,
            drive_dir,
            args.scaffold,
            custom_slug=args.slug,
            category=args.category,
            depth=args.depth,
            force=args.force,
            source_pdf=args.source_pdf
        )
    else:
        compile_references(repo_root, drive_dir, clean_headings=args.clean_headings)


if __name__ == "__main__":
    main()
