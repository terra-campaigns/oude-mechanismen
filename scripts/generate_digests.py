#!/usr/bin/env python3
"""
Compile Tier 3 reference routing index (.agents/context/references.json) from
Markdown digests in the campaign's Google Drive _digests/ directory.

Setting-agnostic: contains zero campaign lore. Discovers sources dynamically.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
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


def find_drive_dir(repo_root: Path, explicit_drive_dir: str = None) -> Path:
    if explicit_drive_dir:
        p = Path(explicit_drive_dir).expanduser()
        if p.exists():
            return p
        raise FileNotFoundError(f"Explicit drive_dir '{explicit_drive_dir}' does not exist.")

    # Check tier1_sources.yml
    config_file = repo_root / ".agents" / "context" / "tier1_sources.yml"
    if config_file.exists():
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            if "drive_dir" in cfg and cfg["drive_dir"]:
                p = Path(cfg["drive_dir"]).expanduser()
                if p.exists():
                    return p
                raise FileNotFoundError(
                    f"Configured 'drive_dir' path '{cfg['drive_dir']}' does not exist. "
                    f"Please verify {config_file}."
                )
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            print(f"[WARN] Failed to read drive_dir from {config_file}: {e}", file=sys.stderr)

    raise FileNotFoundError(
        f"Could not locate reference digests for campaign '{repo_root.name}'. "
        f"Please define 'drive_dir' in {config_file} or pass --drive-dir."
    )


def compile_references(repo_root: Path, drive_dir: Path, clean_headings: bool = False):
    digests_dir = drive_dir / "_digests"
    if not digests_dir.exists():
        print(f"[WARN] No _digests directory found at {digests_dir}")
        return

    md_files = sorted(digests_dir.glob("*.md"))
    if not md_files:
        print(f"[WARN] No Markdown digest files found in {digests_dir}")
        return

    sources = []
    rpg_root = drive_dir.parents[1] if len(drive_dir.parents) >= 2 else drive_dir.parent

    for md_file in md_files:
        content = md_file.read_text(encoding="utf-8")
        if clean_headings:
            cleaned = ensure_heading_blank_lines(content)
            if cleaned != content:
                md_file.write_text(cleaned, encoding="utf-8")
                content = cleaned

        lines = content.splitlines()
        title = md_file.stem
        source_pdf = None

        # 1. Parse Title
        for line in lines[:5]:
            m = re.match(r"^#\s+(.+?)(?:\s*—\s*Reference Digest)?$", line)
            if m:
                title = m.group(1).strip()
                break

        # 2. Parse Source PDF
        for line in lines[:10]:
            m = re.search(r"Source:\s*(?:Google Drive\s*)?`([^`]+)`", line)
            if m:
                raw_src = m.group(1).strip()
                if raw_src.startswith("/"):
                    source_pdf = raw_src
                elif (drive_dir / raw_src).exists():
                    source_pdf = str(drive_dir / raw_src)
                elif (rpg_root / raw_src).exists():
                    source_pdf = str(rpg_root / raw_src)
                else:
                    source_pdf = str(drive_dir / raw_src)
                break

        # 3. Categorisation heuristic (derived from source folder and generic keywords)
        stem = md_file.stem.lower()
        src_lower = (source_pdf or "").lower()

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
        for idx, line in enumerate(lines, start=1):
            m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
            if m:
                sections.append({
                    "level": len(m.group(1)),
                    "heading": m.group(2).strip(),
                    "line": idx
                })

        sources.append({
            "slug": md_file.stem,
            "title": title,
            "category": category,
            "tier": 3,
            "source_pdf": source_pdf,
            "digest_path": str(md_file),
            "digest_exists": True,
            "sections": sections
        })

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


def find_pdf(drive_dir: Path, query: str) -> Optional[Path]:
    """Find a PDF by relative path, filename, or unique substring in Google Drive."""
    p = Path(query)
    if p.is_absolute() and p.exists():
        return p
    if (drive_dir / query).exists():
        return drive_dir / query

    q_norm = query.lower().strip()
    candidates: List[Path] = []
    for f in drive_dir.rglob("*.pdf"):
        if f.name.lower() == q_norm or str(f.relative_to(drive_dir)).lower() == q_norm:
            return f
        if q_norm in f.name.lower():
            candidates.append(f)

    if len(candidates) == 1:
        return candidates[0]
    elif len(candidates) > 1:
        exact = [c for c in candidates if c.stem.lower() == q_norm]
        if len(exact) == 1:
            return exact[0]
        c_list = "\n".join(f"  - {c.relative_to(drive_dir)}" for c in candidates)
        raise ValueError(
            f"Ambiguous PDF query '{query}'. Multiple matches found:\n{c_list}\nPlease specify a more exact relative path."
        )

    return None


def extract_pdf_outline(reader: Any) -> List[Tuple[str, int, int]]:
    """Extract top-level outline items with computed page ranges (title, start_page, end_page)."""
    if not getattr(reader, "outline", None):
        return []

    def flatten(items: Any) -> List[Tuple[str, int]]:
        res: List[Tuple[str, int]] = []
        for it in items:
            if isinstance(it, list):
                res.extend(flatten(it))
            else:
                try:
                    p = reader.get_destination_page_number(it) + 1
                    t = getattr(it, "title", str(it)).strip()
                    if t:
                        res.append((t, p))
                except Exception:
                    pass
        return res

    raw_items = flatten(reader.outline)
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
    pdf_query: str,
    custom_slug: Optional[str] = None,
    category: Optional[str] = None,
    force: bool = False
) -> Path:
    """Scaffold a new Tier 3 Markdown digest from a Google Drive PDF using pypdf outline metadata."""
    if pypdf is None:
        raise ImportError(
            "pypdf is required for digest scaffolding. Please install it using 'pip install pypdf'."
        )

    pdf_path = find_pdf(drive_dir, pdf_query)
    if not pdf_path:
        raise FileNotFoundError(f"Could not locate PDF matching '{pdf_query}' in {drive_dir}")

    try:
        rel_path = str(pdf_path.relative_to(drive_dir))
    except ValueError:
        rpg_root = drive_dir.parents[1] if len(drive_dir.parents) >= 2 else drive_dir.parent
        try:
            rel_path = str(pdf_path.relative_to(rpg_root))
        except ValueError:
            rel_path = str(pdf_path)

    if custom_slug:
        slug = slugify(custom_slug)
    else:
        clean_stem = re.sub(r"[-_]v\d+.*$", "", pdf_path.stem, flags=re.IGNORECASE)
        slug = slugify(clean_stem)

    digests_dir = drive_dir / "_digests"
    out_file = digests_dir / f"{slug}.md"

    if out_file.exists() and not force:
        raise FileExistsError(
            f"Digest already exists at {out_file}. Pass --force to overwrite."
        )

    reader = pypdf.PdfReader(str(pdf_path))
    total_pages = len(reader.pages)

    doc_title = None
    if reader.metadata and reader.metadata.title:
        candidate_title = str(reader.metadata.title).strip()
        if candidate_title and not candidate_title.lower().endswith(".pdf"):
            doc_title = candidate_title

    if not doc_title:
        doc_title = format_title_from_stem(pdf_path.stem)

    if not category:
        parent_name = pdf_path.parent.name.lower()
        if "core" in parent_name or "core" in slug:
            category = "core_setting"
        elif "module" in parent_name or "incursion" in slug or "adventure" in slug:
            category = "module"
        elif "suplement" in parent_name or "supplement" in parent_name:
            category = "supplement"
        else:
            category = "supplement"

    ranges = extract_pdf_outline(reader)
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
    print(f"[SCAFFOLD] Successfully created digest scaffold at {out_file}")

    compile_references(repo_root, drive_dir)
    return out_file


def main():
    parser = argparse.ArgumentParser(description="Compile Tier 3 reference index or scaffold new digests from Google Drive.")
    parser.add_argument("--repo-root", "--repo-dir", dest="repo_root", type=str, default=None, help="Path to campaign repository (defaults to CWD)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Path to Google Drive campaign folder")
    parser.add_argument("--clean-headings", action="store_true", help="Ensure empty blank line after headings in digests")
    parser.add_argument("--scaffold", type=str, default=None, metavar="PDF_QUERY", help="Scaffold a new Tier 3 Markdown digest from a PDF in Google Drive")
    parser.add_argument("--slug", type=str, default=None, help="Custom slug/filename for scaffolded digest")
    parser.add_argument("--category", type=str, default=None, help="Category for scaffolded digest (core_setting, supplement, module, rules, bestiary)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing digest file during scaffolding")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    drive_dir = find_drive_dir(repo_root, args.drive_dir)

    if args.scaffold:
        scaffold_digest(
            repo_root,
            drive_dir,
            args.scaffold,
            custom_slug=args.slug,
            category=args.category,
            force=args.force
        )
    else:
        compile_references(repo_root, drive_dir, clean_headings=args.clean_headings)


if __name__ == "__main__":
    main()
