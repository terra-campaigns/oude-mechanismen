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


def find_drive_dir(repo_root: Path, explicit_drive_dir: str = None) -> Path:
    if explicit_drive_dir:
        p = Path(explicit_drive_dir).expanduser()
        if p.exists():
            return p

    # Check tier1_sources.yml
    config_file = repo_root / ".agents" / "context" / "tier1_sources.yml"
    if config_file.exists():
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            if "drive_dir" in cfg and cfg["drive_dir"]:
                p = Path(cfg["drive_dir"]).expanduser()
                if p.exists():
                    return p
        except Exception as e:
            print(f"[WARN] Failed to read drive_dir from {config_file}: {e}", file=sys.stderr)

    # Standard Google Drive paths for this machine
    repo_name = repo_root.name
    candidate = Path.home() / "Library" / "CloudStorage" / "GoogleDrive-estevao.alvarenga@gmail.com" / "My Drive" / "RPG" / "campaigns" / repo_name
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Could not locate Google Drive campaign folder for '{repo_name}'. "
        f"Specify 'drive_dir' in .agents/context/tier1_sources.yml or pass --drive-dir."
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

        # 3. Categorisation heuristic
        stem = md_file.stem.lower()
        if any(k in stem for k in ["core", "rules", "setting"]):
            category = "core_setting"
        elif any(k in stem for k in ["analysis", "research"]):
            category = "research_aesthetic"
        elif "map" in stem:
            category = "maps"
        elif "postcard" in stem:
            category = "postcards"
        elif any(k in stem for k in ["supplement", "synthetic", "metamorphica"]):
            category = "supplement"
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

    # Write output to repo
    campaign_name = repo_root.name
    payload = {
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tier": 3,
        "campaign": campaign_name,
        "note": f"Tier 3 reference routing index — influence only, never automatic {campaign_name.title()} canon.",
        "total_sources": len(sources),
        "sources": sources
    }

    out_file = repo_root / ".agents" / "context" / "references.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"[INDEX] Successfully compiled {len(sources)} reference sources from {digests_dir} to {out_file}")


def main():
    parser = argparse.ArgumentParser(description="Compile Tier 3 reference index from Google Drive Markdown digests.")
    parser.add_argument("--repo-root", type=str, default=None, help="Path to campaign repository (defaults to CWD)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Path to Google Drive campaign folder")
    parser.add_argument("--clean-headings", action="store_true", help="Ensure empty blank line after headings in digests")
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve() if args.repo_root else Path.cwd()
    drive_dir = find_drive_dir(repo_root, args.drive_dir)

    compile_references(repo_root, drive_dir, clean_headings=args.clean_headings)


if __name__ == "__main__":
    main()
