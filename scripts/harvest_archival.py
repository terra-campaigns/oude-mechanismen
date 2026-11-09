#!/usr/bin/env python3
"""
Archival Scriptorium — Non-AI Asset Harvester.

Discovers, verifies, and integrates genuine public domain historical cultural imagery
from open-access museum collections (Wikimedia Commons, The Metropolitan Museum of Art)
into tabletop RPG campaign vaults.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

USER_AGENT = (
    "OudeMechanismenHarvester/0.3.0 "
    "(https://github.com/terra-campaigns/oude-mechanismen; contact@terra-campaigns)"
)


@dataclass
class ArchivalCandidate:
    """Represents a discovered historical asset candidate."""

    candidate_id: str                      # Deterministic hash of source URL
    title: str                             # Original title of the artwork / artefact
    creator: str                           # Artist, engraver, or "Unknown"
    date_created: str                      # e.g. "ca. 1780", "16th century", "Edo period"
    institution: str                       # e.g. "The Metropolitan Museum of Art", "Wikimedia Commons"
    source_page_url: str                   # Canonical permalink to object page
    raw_image_url: str                     # Direct URL to high-resolution asset
    licence: str                           # e.g. "Public Domain", "CC0", "CC BY 4.0"
    is_public_domain: bool                 # Programmatically verified flag
    raw_file_path: Optional[Path] = None   # Local path in .agents/tmp/
    styled_variants: Dict[str, Path] = field(default_factory=dict) # Preset -> styled asset path
    matched_query: str = ""                # The search query that yielded this object


def validate_licence_string(licence_str: Optional[str]) -> bool:
    """Case-insensitive normalisation and regex validation for CC0/CC-BY/PD licences."""
    if not licence_str or not str(licence_str).strip():
        return False

    norm = str(licence_str).strip().lower()

    # Reject non-commercial, no-derivatives, and all rights reserved
    restrictive_markers = [
        "all rights reserved",
        "in copyright",
        "copyrighted",
        "-nc",
        "-nd",
        "non-commercial",
        "noncommercial",
        "no-derivatives",
        "noderivatives",
        "fair use",
    ]
    if any(marker in norm for marker in restrictive_markers):
        return False

    # Accept CC0, CC BY, CC BY-SA, PD variants, and Public Domain Mark
    if re.search(r"^(cc0|cc[ -]?zero|cc[ -]?by|pd|public domain|no copyright)", norm):
        return True

    if re.search(r"\b(pd-art|pd-old|pd-us|pd-scan|public domain mark)\b", norm):
        return True

    return False


def is_ai_provenance(categories: Union[List[str], str], description: str = "") -> bool:
    """Case-insensitive lexical scan for generative AI markers in metadata."""
    if isinstance(categories, list):
        cat_str = " ".join(str(c) for c in categories)
    else:
        cat_str = str(categories or "")

    combined = f"{cat_str} {description}".lower()

    ai_markers = [
        "ai-generated",
        "ai generated",
        "midjourney",
        "stable diffusion",
        "dall-e",
        "generative ai",
        "novelai",
        "disco diffusion",
    ]

    return any(marker in combined for marker in ai_markers)


def calculate_relative_image_path(note_path: Path, repo_root: Path, image_rel_path: str) -> str:
    """Calculate relative path from note directory to image asset for Jekyll data_extractor."""
    target_abs = (repo_root / image_rel_path).resolve()
    note_dir = note_path.resolve().parent
    rel = os.path.relpath(target_abs, start=note_dir)
    return rel.replace("\\", "/")


def format_footer_html(candidate: ArchivalCandidate) -> str:
    """Generate theme-compliant HTML attribution string for footer_content."""
    safe_title = candidate.title.replace('"', "&quot;")
    date_part = f" ({candidate.date_created})" if candidate.date_created else ""
    return (
        f'Image adapted from <a href="{candidate.source_page_url}" target="_blank" '
        f'rel="noopener noreferrer">{safe_title}</a>{date_part}, '
        f'{candidate.institution}. {candidate.licence}.'
    )


def generate_deterministic_fallback_queries(note_metadata: dict) -> List[str]:
    """Derive fallback queries when local Ollama is offline."""
    title = str(note_metadata.get("title", "")).strip()
    parent = str(note_metadata.get("parent", "")).strip()

    queries = []
    if title:
        queries.append(title)
        queries.append(f"{title} engraving")
    if parent:
        queries.append(f"{parent} artifact")
    elif title:
        queries.append(f"{title} artifact")

    return queries or ["antique engraving", "historical artifact", "museum plate"]


def patch_note_frontmatter(content: str, rel_image_path: str, footer_html: str) -> str:
    """Surgically update front matter without disturbing existing comments or body text."""
    escaped_footer = footer_html.replace("'", "''")
    footer_line = f"footer_content: '{escaped_footer}'"

    # Match front matter
    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", content, re.DOTALL)
    if not fm_match:
        return f"---\nimages:\n  - {rel_image_path}\n{footer_line}\n---\n\n{content}"

    fm_text = fm_match.group(1)
    body_text = fm_match.group(2)

    # 1. Update or insert footer_content
    if re.search(r"^footer_content:.*$", fm_text, re.MULTILINE):
        fm_text = re.sub(r"^footer_content:.*$", footer_line, fm_text, flags=re.MULTILINE)
    else:
        fm_text = f"{fm_text.rstrip()}\n{footer_line}"

    # 2. Update images: array
    badge_pattern = r"^[ \t]*-[ \t]*[/a-zA-Z0-9_\-\.]*imgs/badges/[a-zA-Z0-9_\-\.]+\.png.*$"
    if re.search(badge_pattern, fm_text, re.MULTILINE):
        fm_text = re.sub(badge_pattern, f"  - {rel_image_path}", fm_text, count=1, flags=re.MULTILINE)
    elif re.search(r"^images:[ \t]*$", fm_text, re.MULTILINE):
        fm_text = re.sub(
            r"^(images:[ \t]*\r?\n)",
            f"\\1  - {rel_image_path}\n",
            fm_text,
            count=1,
            flags=re.MULTILINE,
        )
    else:
        fm_text = f"{fm_text.rstrip()}\nimages:\n  - {rel_image_path}"

    return f"---\n{fm_text.strip()}\n---\n\n{body_text.lstrip()}"


def parse_met_object_payload(data: dict) -> Optional[ArchivalCandidate]:
    """Extract candidate from Met Museum object JSON, enforcing isPublicDomain."""
    if not data or not data.get("isPublicDomain"):
        return None

    raw_image_url = data.get("primaryImage") or data.get("primaryImageSmall")
    if not raw_image_url or not str(raw_image_url).strip():
        return None

    obj_id = data.get("objectID", "")
    cand_id = hashlib.sha256(f"met_{obj_id}_{raw_image_url}".encode("utf-8")).hexdigest()[:16]

    title = data.get("title") or "Untitled Artwork"
    creator = data.get("artistDisplayName") or "Unknown"
    date_created = data.get("objectDate") or "Date unknown"
    institution = "The Metropolitan Museum of Art"
    source_url = data.get("objectURL") or f"https://www.metmuseum.org/art/collection/search/{obj_id}"

    return ArchivalCandidate(
        candidate_id=cand_id,
        title=title,
        creator=creator,
        date_created=date_created,
        institution=institution,
        source_page_url=source_url,
        raw_image_url=raw_image_url,
        licence="Public Domain (Met Open Access)",
        is_public_domain=True,
    )


def parse_wikimedia_imageinfo(data: dict) -> List[ArchivalCandidate]:
    """Parse Wikimedia query response into candidate list, handling dictionary metadata."""
    candidates = []
    if not data or "query" not in data or "pages" not in data["query"]:
        return candidates

    pages = data["query"]["pages"]
    for page_id, page in pages.items():
        if "imageinfo" not in page or not page["imageinfo"]:
            continue

        info = page["imageinfo"][0]
        raw_image_url = info.get("url")
        source_url = info.get("descriptionurl") or raw_image_url
        width = info.get("width", 0)
        height = info.get("height", 0)

        # Minimum resolution threshold
        if width < 800 and height < 800:
            continue

        extmeta = info.get("extmetadata", {})

        def get_meta_value(key: str) -> str:
            val = extmeta.get(key, {})
            if isinstance(val, dict):
                return str(val.get("value", "")).strip()
            return str(val or "").strip()

        licence_val = get_meta_value("LicenseShortName")
        categories_val = get_meta_value("Categories")
        desc_val = get_meta_value("ImageDescription")

        # Anti-AI and rights validation
        if is_ai_provenance(categories_val, desc_val):
            continue

        if not validate_licence_string(licence_val):
            continue

        title = get_meta_value("ObjectName") or page.get("title", "").replace("File:", "").replace(".jpg", "")
        creator = get_meta_value("Artist") or "Unknown"
        creator = re.sub(r"<[^>]+>", "", creator).strip() or "Unknown"
        date_created = get_meta_value("DateTime") or "Date unknown"

        cand_id = hashlib.sha256(f"wiki_{page_id}_{raw_image_url}".encode("utf-8")).hexdigest()[:16]

        candidates.append(
            ArchivalCandidate(
                candidate_id=cand_id,
                title=title,
                creator=creator,
                date_created=date_created,
                institution="Wikimedia Commons",
                source_page_url=source_url,
                raw_image_url=raw_image_url,
                licence=licence_val or "Public Domain",
                is_public_domain=True,
            )
        )

    return candidates


def query_ollama_search_terms(
    note_metadata: dict,
    model: str = "qwen2.5:14b",
    timeout_s: float = 5.0,
    endpoint: str = "http://localhost:11434/api/generate",
) -> List[str]:
    """Prompt local Ollama for 3 pre-20th-century historical museum search queries."""
    title = note_metadata.get("title", "Unknown Entity")
    parent = note_metadata.get("parent", "")
    snippet = note_metadata.get("body_snippet", "")

    prompt = (
        "You are an expert museum curator and historical archivist for tabletop RPG campaign worldbuilding.\n"
        "Given the following fantasy or sci-fi campaign entity, provide exactly three pre-20th-century historical "
        "museum or library archive search terms (e.g. '18th-century automaton engraving', 'medieval bestiary dragon', "
        "'Renaissance celestial sphere map', 'antique bronze astrolabe', 'Edo period iron kettle').\n"
        "Translate abstract fantasy concepts into concrete physical artefacts, engravings, or cultural objects that "
        "exist in historical collections.\n\n"
        f"Entity Title: {title}\n"
        f"Context/Category: {parent}\n"
        f"Description snippet: {snippet}\n\n"
        "Instructions:\n"
        "1. Output MUST strictly use British English.\n"
        "2. Output MUST be ONLY a valid JSON array of 3 strings (e.g. [\"term 1\", \"term 2\", \"term 3\"]).\n"
        "3. Do not include markdown formatting or commentary."
    )

    req_data = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {"temperature": 0.3},
    }

    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(req_data).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_response = data.get("response", "").strip()

            # Clean potential markdown fences
            clean = re.sub(r"^```(?:json)?\s*", "", raw_response, flags=re.MULTILINE)
            clean = re.sub(r"\s*```$", "", clean, flags=re.MULTILINE).strip()

            parsed = json.loads(clean)
            if isinstance(parsed, list) and len(parsed) >= 1:
                return [str(q).strip() for q in parsed[:3] if str(q).strip()]
    except Exception:
        # Fall back gracefully on timeout, offline model, or JSON parse error
        pass

    return generate_deterministic_fallback_queries(note_metadata)


def search_met_museum(
    query: str,
    max_candidates: int = 6,
    timeout_s: float = 5.0,
) -> List[ArchivalCandidate]:
    """Query The Metropolitan Museum of Art Open Access API."""
    encoded_q = urllib.parse.quote(query)
    search_url = (
        f"https://collectionapi.metmuseum.org/public/collection/v1/search"
        f"?hasImages=true&isPublicDomain=true&q={encoded_q}"
    )

    candidates = []
    try:
        req = urllib.request.Request(search_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            search_data = json.loads(resp.read().decode("utf-8"))

        object_ids = search_data.get("objectIDs") or []
        for obj_id in object_ids[:max_candidates]:
            obj_url = f"https://collectionapi.metmuseum.org/public/collection/v1/objects/{obj_id}"
            try:
                obj_req = urllib.request.Request(obj_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(obj_req, timeout=timeout_s) as obj_resp:
                    obj_data = json.loads(obj_resp.read().decode("utf-8"))
                    cand = parse_met_object_payload(obj_data)
                    if cand:
                        cand.matched_query = query
                        candidates.append(cand)
            except Exception:
                continue
    except Exception:
        pass

    return candidates


def search_wikimedia_commons(
    query: str,
    max_candidates: int = 6,
    timeout_s: float = 5.0,
) -> List[ArchivalCandidate]:
    """Query Wikimedia Commons Action API with compliant User-Agent."""
    encoded_q = urllib.parse.quote(query)
    wiki_url = (
        f"https://commons.wikimedia.org/w/api.php?action=query&generator=search"
        f"&gsrnamespace=6&gsrlimit={max_candidates}&gsrsearch={encoded_q}+filetype:bitmap"
        f"&prop=imageinfo&iiprop=url|size|extmetadata&format=json"
    )

    try:
        req = urllib.request.Request(wiki_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            candidates = parse_wikimedia_imageinfo(data)
            for c in candidates:
                c.matched_query = query
            return candidates
    except Exception:
        return []


def download_candidate_image(
    candidate: ArchivalCandidate,
    dest_dir: Path,
    timeout_s: float = 10.0,
) -> Optional[Path]:
    """Download candidate image to local temporary directory and verify file integrity."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw_path = dest_dir / f"{candidate.candidate_id}_raw.jpg"

    try:
        req = urllib.request.Request(candidate.raw_image_url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            content = resp.read()

        if len(content) < 1024:
            return None

        with open(raw_path, "wb") as f:
            f.write(content)

        # Basic image validity check
        try:
            from PIL import Image
            with Image.open(raw_path) as img:
                img.verify()
        except ImportError:
            # If PIL is not installed, verify standard magic numbers
            if not (content.startswith(b"\xff\xd8") or content.startswith(b"\x89PNG")):
                raw_path.unlink(missing_ok=True)
                return None
        except Exception:
            raw_path.unlink(missing_ok=True)
            return None

        candidate.raw_file_path = raw_path
        return raw_path
    except Exception:
        if raw_path.exists():
            raw_path.unlink(missing_ok=True)
        return None


def style_candidate_variants(
    candidate: ArchivalCandidate,
    dest_dir: Path,
    aesthetics_cfg_path: Optional[Path] = None,
) -> Dict[str, Path]:
    """Apply art_filter presets to raw candidate asset, returning preset -> styled path dictionary."""
    if not candidate.raw_file_path or not candidate.raw_file_path.exists():
        return {}

    # Locate art_filter.py
    engine_root = Path(__file__).resolve().parent.parent
    art_filter_path = engine_root / "skills" / "illustrate-entry" / "scripts" / "art_filter.py"

    if not art_filter_path.exists():
        return {}

    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        # Dynamically import art_filter
        import importlib.util
        spec = importlib.util.spec_from_file_location("art_filter", str(art_filter_path))
        if not spec or not spec.loader:
            return {}
        art_filter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(art_filter)

        from PIL import Image
        cfg = art_filter.load_config(str(aesthetics_cfg_path) if aesthetics_cfg_path else None)
        presets = cfg.get("presets", art_filter.DEFAULT_FALLBACK_PRESETS)

        with Image.open(candidate.raw_file_path) as raw_img:
            comp_img = raw_img.convert("RGB")

            for preset_name, preset_cfg in presets.items():
                try:
                    styled = art_filter.process_image(
                        comp_img,
                        preset_name,
                        preset_cfg,
                        focal_points=None,
                        separate_matte=False,
                    )
                    out_path = dest_dir / f"{candidate.candidate_id}_{preset_name}.jpg"
                    styled.save(out_path, format="JPEG", quality=90)
                    candidate.styled_variants[preset_name] = out_path
                except Exception:
                    continue

    except Exception:
        pass

    return candidate.styled_variants


def cleanup_temp_candidates(
    candidates: List[ArchivalCandidate],
    chosen_candidate: Optional[ArchivalCandidate] = None,
    tmp_dir: Optional[Path] = None,
) -> None:
    """Clean up rejected candidate downloads and rendered variants from disk."""
    for cand in candidates:
        if chosen_candidate and cand.candidate_id == chosen_candidate.candidate_id:
            # Clean only raw file if styled variant was moved
            if cand.raw_file_path and cand.raw_file_path.exists():
                cand.raw_file_path.unlink(missing_ok=True)
            continue

        if cand.raw_file_path and cand.raw_file_path.exists():
            cand.raw_file_path.unlink(missing_ok=True)

        for variant_path in cand.styled_variants.values():
            if variant_path and variant_path.exists():
                variant_path.unlink(missing_ok=True)


def parse_note_metadata(note_path: Path) -> dict:
    """Extract title, parent, and body snippet from a markdown note."""
    if not note_path.exists():
        return {}

    content = note_path.read_text(encoding="utf-8", errors="replace")
    title = note_path.stem
    parent = note_path.parent.name

    fm_match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", content, re.DOTALL)
    snippet = ""
    if fm_match:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)
        t_match = re.search(r"^title:[ \t]*[\"']?(.*?)[\"']?$", fm_text, re.MULTILINE)
        if t_match:
            title = t_match.group(1).strip()
        p_match = re.search(r"^parent:[ \t]*[\"']?(.*?)[\"']?$", fm_text, re.MULTILINE)
        if p_match:
            parent = p_match.group(1).strip()
        # Clean Dataview and headings from snippet
        clean_body = re.sub(r"```dataview.*?```", "", body, flags=re.DOTALL)
        clean_body = re.sub(r"#+.*", "", clean_body)
        words = clean_body.strip().split()
        snippet = " ".join(words[:50])
    else:
        words = content.strip().split()
        snippet = " ".join(words[:50])

    return {"title": title, "parent": parent, "body_snippet": snippet}


def harvest_candidates_for_note(
    note_path: Path,
    repo_root: Path,
    max_candidates: int = 3,
    tmp_dir: Optional[Path] = None,
    aesthetics_cfg: Optional[Path] = None,
) -> List[ArchivalCandidate]:
    """Execute complete harvesting lifecycle for a target note."""
    if not tmp_dir:
        tmp_dir = repo_root / ".agents" / "tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)

    meta = parse_note_metadata(note_path)
    queries = query_ollama_search_terms(meta)

    seen_ids = set()
    collected = []

    for q in queries:
        # Search Wikimedia Commons
        wiki_hits = search_wikimedia_commons(q, max_candidates=4)
        for cand in wiki_hits:
            if cand.candidate_id not in seen_ids:
                seen_ids.add(cand.candidate_id)
                collected.append(cand)

        # Search The Met Museum
        met_hits = search_met_museum(q, max_candidates=3)
        for cand in met_hits:
            if cand.candidate_id not in seen_ids:
                seen_ids.add(cand.candidate_id)
                collected.append(cand)

        if len(collected) >= max_candidates * 2:
            break

    # Prioritise and download top candidates
    final_candidates = []
    for cand in collected:
        raw_path = download_candidate_image(cand, tmp_dir)
        if raw_path:
            style_candidate_variants(cand, tmp_dir, aesthetics_cfg_path=aesthetics_cfg)
            final_candidates.append(cand)
        if len(final_candidates) >= max_candidates:
            break

    return final_candidates


def main():
    parser = argparse.ArgumentParser(description="Harvest authentic public domain artwork for campaign entries.")
    parser.add_argument("--entity", "-e", required=True, help="Path to target markdown note.")
    parser.add_argument("--repo-dir", "-r", help="Path to campaign repository root.")
    parser.add_argument("--max-candidates", "-m", type=int, default=3, help="Maximum candidates to return.")
    parser.add_argument("--json", action="store_true", help="Output candidates manifest as JSON.")
    args = parser.parse_args()

    note_path = Path(args.entity).resolve()
    if not note_path.exists():
        print(f"Error: Target entity note '{args.entity}' does not exist.", file=sys.stderr)
        sys.exit(1)

    repo_root = Path(args.repo_dir).resolve() if args.repo_dir else note_path.parent
    while repo_root != repo_root.parent and not ((repo_root / "_config.yml").exists() or (repo_root / ".agents").exists()):
        repo_root = repo_root.parent

    candidates = harvest_candidates_for_note(note_path, repo_root, max_candidates=args.max_candidates)

    if args.json:
        out = [
            {
                "id": c.candidate_id,
                "title": c.title,
                "creator": c.creator,
                "date": c.date_created,
                "institution": c.institution,
                "licence": c.licence,
                "source_url": c.source_page_url,
                "raw_file": str(c.raw_file_path) if c.raw_file_path else None,
                "styled_variants": {k: str(v) for k, v in c.styled_variants.items()},
            }
            for c in candidates
        ]
        print(json.dumps(out, indent=2))
    else:
        if not candidates:
            print(f"No public domain archival assets found for '{note_path.name}'.")
            return

        print(f"Discovered {len(candidates)} public domain candidates for '{note_path.name}':\n")
        for i, c in enumerate(candidates, 1):
            print(f"[{i}] {c.title} ({c.date_created}) — {c.creator}")
            print(f"    Institution: {c.institution} | Licence: {c.licence}")
            print(f"    Source: {c.source_page_url}")
            if c.styled_variants:
                print(f"    Styled Variants: {', '.join(c.styled_variants.keys())}")
            print()


if __name__ == "__main__":
    main()
