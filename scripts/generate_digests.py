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
import yaml


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

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "_config.yml").exists() or (candidate / ".agents").is_dir():
            return candidate

    return cwd


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


def main():
    parser = argparse.ArgumentParser(description="Compile Tier 3 reference index from Google Drive Markdown digests.")
    parser.add_argument("--repo-root", "--repo-dir", dest="repo_root", type=str, default=None, help="Path to campaign repository (defaults to CWD)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Path to Google Drive campaign folder")
    parser.add_argument("--clean-headings", action="store_true", help="Ensure empty blank line after headings in digests")
    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_root)
    drive_dir = find_drive_dir(repo_root, args.drive_dir)

    compile_references(repo_root, drive_dir, clean_headings=args.clean_headings)


if __name__ == "__main__":
    main()
