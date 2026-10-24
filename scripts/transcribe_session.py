#!/usr/bin/env python3
"""
Setting-agnostic audio transcription and campaign context extractor for table RPG sessions.

Pipeline stages handled:
1. Resolves campaign context and Google Drive session directory from .agents/context/tier1_sources.yml.
2. Extracts a dynamic campaign glossary from .agents/context/catalog.json, decisions.md, and AGENTS.md.
3. Formulates a compact proper-noun prompt to bias Whisper speech recognition on Apple Metal.
4. Normalises audio containers (.mkv, .mp4, .m4a, .wav, etc.) to 16 kHz mono WAV via ffmpeg.
5. Transcribes audio via whisper-cli (whisper.cpp) using ggml-large-v3-turbo.bin.
6. Emits session metadata and next-chapter discovery parameters for Antigravity synthesis.

All outputs and logs strictly adhere to British English.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml


DEFAULT_MODEL_PATH = Path.home() / ".whisper-models" / "ggml-large-v3-turbo.bin"


def find_campaign_root(explicit_root: Optional[str] = None) -> Path:
    """Locate the target campaign repository root."""
    if explicit_root:
        p = Path(explicit_root).resolve()
        if (p / ".agents").is_dir() or (p / "_config.yml").is_file():
            return p
        raise FileNotFoundError(f"Specified repo root '{explicit_root}' does not appear to be a campaign repository.")

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "_config.yml").exists() or (candidate / ".agents").is_dir():
            return candidate

    raise FileNotFoundError(
        f"Could not locate a campaign repository from current directory '{cwd}'. "
        f"Please run from within a campaign vault or pass --repo-root."
    )


def find_drive_dir(repo_root: Path, explicit_drive_dir: Optional[str] = None) -> Path:
    """Resolve the campaign's Google Drive storage directory from tier1_sources.yml."""
    if explicit_drive_dir:
        p = Path(explicit_drive_dir).expanduser().resolve()
        if p.exists():
            return p
        raise FileNotFoundError(f"Explicit drive_dir '{explicit_drive_dir}' does not exist.")

    config_file = repo_root / ".agents" / "context" / "tier1_sources.yml"
    if config_file.exists():
        try:
            cfg = yaml.safe_load(config_file.read_text(encoding="utf-8")) or {}
            if "drive_dir" in cfg and cfg["drive_dir"]:
                p = Path(cfg["drive_dir"]).expanduser().resolve()
                if p.exists():
                    return p
                raise FileNotFoundError(
                    f"Configured 'drive_dir' path '{cfg['drive_dir']}' in {config_file} does not exist."
                )
        except Exception as e:
            if isinstance(e, FileNotFoundError):
                raise
            print(f"[WARN] Failed to read drive_dir from {config_file}: {e}", file=sys.stderr)

    raise FileNotFoundError(
        f"Could not locate Google Drive folder for campaign '{repo_root.name}'. "
        f"Please define 'drive_dir' in {config_file} or pass --drive-dir."
    )


def parse_campaign_defaults(repo_root: Path) -> Dict[str, Any]:
    """Parse structural and procedural conventions from .agents/AGENTS.md."""
    defaults: Dict[str, Any] = {
        "campaign_subfolder": "campaigns",
        "hub_pages": [],
        "chapter_naming": "ep_{num:03d}.md",
        "timestamp_format": "YYYY-MM-DD",
        "location_key": "region",
        "session_language": "en",
        "genre": None,
        "cadence": None,
        "vocabulary": None,
    }

    agents_file = repo_root / ".agents" / "AGENTS.md"
    if not agents_file.exists():
        return defaults

    text = agents_file.read_text(encoding="utf-8")

    # 1. Default Campaign Subfolder
    m_sub = re.search(r"Default Campaign Subfolder:\s*`?([^`\n]+)`?", text)
    if m_sub:
        defaults["campaign_subfolder"] = m_sub.group(1).strip().strip("/")

    # 2. Campaign Hub Page(s)
    m_hubs = re.findall(r"\[index\]\(([^)]+)\)", text)
    if m_hubs:
        defaults["hub_pages"] = m_hubs

    # 3. Chapter Naming Convention
    m_name = re.search(r"Chapter Naming Convention:\s*`?([^`\n]+)`?", text)
    if m_name:
        raw_pat = m_name.group(1).strip()
        if "ep_" in raw_pat:
            defaults["chapter_naming"] = "ep_{num:03d}.md"
        elif "chap" in raw_pat:
            defaults["chapter_naming"] = "chap{num:03d}.md"
        elif re.match(r"\d+\.md", raw_pat):
            defaults["chapter_naming"] = "{num:03d}.md"

    # 4. Chapter Timestamp Format
    m_time = re.search(r"Chapter Timestamp Format:\s*`?([^`\n]+)`?", text)
    if m_time:
        raw_time = m_time.group(1).strip()
        raw_time = re.sub(r"^nav_order:\s*", "", raw_time)
        raw_time = re.sub(r"\(.*?\)", "", raw_time).strip()
        defaults["timestamp_format"] = raw_time

    # 5. Location Front Matter Key
    m_loc = re.search(r"Location Front Matter Key:\s*`?([^`\n:]+)`?", text)
    if m_loc:
        raw_loc = m_loc.group(1).strip().split()[0].rstrip(":")
        defaults["location_key"] = raw_loc

    # 6. Session Audio Language
    m_lang = re.search(r"Session Audio Language:\s*`?([a-zA-Z_\-]+)`?", text)
    if m_lang:
        defaults["session_language"] = m_lang.group(1).strip().lower()

    # 7. Style & Tone
    m_genre = re.search(r"Genre:\s*([^\n]+)", text)
    if m_genre:
        defaults["genre"] = m_genre.group(1).strip()

    return defaults


def discover_next_chapter(repo_root: Path, defaults: Dict[str, Any]) -> Dict[str, Any]:
    """Scan existing campaign chapter files to identify sequential numbering and latest continuity."""
    subfolder = repo_root / defaults["campaign_subfolder"]
    res: Dict[str, Any] = {
        "subfolder": str(subfolder.relative_to(repo_root)) if subfolder.exists() else defaults["campaign_subfolder"],
        "previous_chapter_file": None,
        "previous_chapter_title": None,
        "previous_date": None,
        "previous_parent": None,
        "previous_region": None,
        "next_number": 1,
        "next_filename": "ep_001.md",
        "next_chapter_path": None,
    }

    if not subfolder.is_dir():
        return res

    # Gather markdown chapter files
    candidates = sorted([p for p in subfolder.glob("*.md") if p.name != "index.md"])
    if not candidates:
        naming_fmt = defaults.get("chapter_naming", "ep_{num:03d}.md")
        res["next_filename"] = naming_fmt.format(num=1)
        res["next_chapter_path"] = str(subfolder / res["next_filename"])
        return res

    # Extract numbers from existing files
    max_num = 0
    pattern_type = "ep"
    latest_file = candidates[-1]

    for p in candidates:
        m_ep = re.match(r"^ep_(\d+)", p.name)
        m_num = re.match(r"^(\d+)", p.name)
        m_chap = re.match(r"^chap(\d+)", p.name)

        if m_ep:
            val = int(m_ep.group(1))
            if val > max_num:
                max_num = val
                pattern_type = "ep"
                latest_file = p
        elif m_chap:
            val = int(m_chap.group(1))
            if val > max_num:
                max_num = val
                pattern_type = "chap"
                latest_file = p
        elif m_num:
            val = int(m_num.group(1))
            if val > max_num:
                max_num = val
                pattern_type = "num"
                latest_file = p

    next_num = max_num + 1
    if pattern_type == "ep":
        next_fn = f"ep_{next_num:03d}.md"
    elif pattern_type == "chap":
        next_fn = f"chap{next_num:03d}.md"
    else:
        next_fn = f"{next_num:03d}.md"

    res["previous_chapter_file"] = str(latest_file.relative_to(repo_root))
    res["next_number"] = next_num
    res["next_filename"] = next_fn
    res["next_chapter_path"] = str(subfolder / next_fn)

    # Read latest chapter front matter
    try:
        content = latest_file.read_text(encoding="utf-8")
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                fm = yaml.safe_load(parts[1]) or {}
                res["previous_chapter_title"] = fm.get("title")
                res["previous_date"] = str(fm.get("nav_order")) if fm.get("nav_order") else None
                res["previous_parent"] = fm.get("parent")
                res["previous_region"] = fm.get("region") or fm.get("location")
    except Exception as e:
        print(f"[WARN] Could not parse latest chapter front matter from {latest_file}: {e}", file=sys.stderr)

    return res


def build_dynamic_glossary(
    repo_root: Path,
    out_glossary_path: Path,
    session_slug: str,
    defaults: Optional[Dict[str, Any]] = None
) -> Tuple[str, List[str]]:
    """
    Compile a structured campaign glossary from .agents/context/catalog.json,
    decisions.md, and AGENTS.md.
    
    Returns:
        A tuple of (written_glossary_markdown, list_of_proper_nouns_for_whisper_prompt).
    """
    catalog_path = repo_root / ".agents" / "context" / "catalog.json"
    decisions_path = repo_root / ".agents" / "context" / "decisions.md"
    agents_path = repo_root / ".agents" / "AGENTS.md"

    entries: List[Dict[str, Any]] = []
    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                entries = json.load(f).get("entries", [])
        except Exception as e:
            print(f"[WARN] Failed to load catalog.json: {e}", file=sys.stderr)

    # Group entries by category
    people: List[Dict[str, Any]] = []
    locations: List[Dict[str, Any]] = []
    factions: List[Dict[str, Any]] = []
    sessions: List[Dict[str, Any]] = []
    other: List[Dict[str, Any]] = []

    proper_nouns_set = set()

    for e in entries:
        etype = (e.get("type") or "").lower()
        title = (e.get("title") or "").strip()
        path_str = e.get("path") or ""

        if title and not title.startswith("ep_") and not re.match(r"^\d{3}$", title):
            proper_nouns_set.add(title)

        if etype == "people":
            people.append(e)
        elif etype == "faction":
            factions.append(e)
        elif etype in ("location", "gazetteer") or path_str.startswith("directory/"):
            locations.append(e)
        elif etype == "session":
            sessions.append(e)
        else:
            other.append(e)

    # Prioritise entities and sessions connected to the active campaign
    camp_sub = (defaults or {}).get("campaign_subfolder", "campaigns").rstrip("/")
    camp_sessions = [s for s in sessions if (s.get("path") or "").startswith(camp_sub)]
    sessions_to_use = camp_sessions if camp_sessions else sessions

    hub_pages = (defaults or {}).get("hub_pages", [])
    clean_hub_dirs = []
    for hub in hub_pages:
        d = str(Path(hub).parent).replace("../", "").strip("/")
        if d:
            clean_hub_dirs.append(d)

    core_active_paths = set()
    other_campaign_paths = set()
    for e in entries:
        p = e.get("path") or ""
        if p.startswith(camp_sub + "/") or p == camp_sub:
            core_active_paths.add(p)
        elif p.startswith("campaigns/") and p != "campaigns/index.md":
            other_campaign_paths.add(p)
        for d in clean_hub_dirs:
            if p.startswith(d + "/") or p == d:
                core_active_paths.add(p)

    def is_connected_to_campaign(item: Dict[str, Any]) -> bool:
        p = item.get("path", "")
        if p in core_active_paths:
            return True
        out_links = set(item.get("links_out", []))
        in_links = set(item.get("links_in", []))
        if (out_links | in_links) & core_active_paths:
            return True
        return False

    # In multi-campaign vaults, restrict glossary & ASR prompt to active campaign entities
    if other_campaign_paths and core_active_paths:
        active_people = [x for x in people if is_connected_to_campaign(x)]
        active_locations = [x for x in locations if is_connected_to_campaign(x)]
        active_factions = [x for x in factions if is_connected_to_campaign(x)]
        if active_people:
            people = active_people
        if active_locations:
            locations = active_locations
        if active_factions:
            factions = active_factions

    people.sort(key=lambda x: (not is_connected_to_campaign(x), x.get("title", "")))
    locations.sort(key=lambda x: (not is_connected_to_campaign(x), x.get("title", "")))
    factions.sort(key=lambda x: (not is_connected_to_campaign(x), x.get("title", "")))

    # Decisions & active rulings
    decisions_text = ""
    if decisions_path.exists():
        decisions_text = decisions_path.read_text(encoding="utf-8").strip()

    # Format Markdown lines in British English with blank lines after headings
    lines = [
        f"# Campaign Context & Entity Glossary — {session_slug}",
        "",
        "> [!NOTE]",
        f"> Automatically compiled from canonical notes in `{repo_root.name}` for acoustic spelling reconciliation.",
        f"> Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.",
        "",
        "## 1. Player Characters & Key Personnel",
        "",
    ]

    if people:
        for p in people:
            title = p.get("title", "Unnamed")
            role = p.get("role") or "Unknown role"
            region = p.get("region") or p.get("location") or "Unspecified location"
            summary = p.get("summary") or ""
            link_path = p.get("path") or ""
            status = f" [{p.get('status')}]" if p.get("status") else ""
            lines.append(f"- **{title}**{status} (`{link_path}`)")
            lines.append(f"  - **Role & Locus:** {role} | {region}")
            if summary:
                lines.append(f"  - **Background:** {summary}")
        lines.append("")
    else:
        lines.extend(["No character notes catalogued in directory.\n", ""])

    lines.extend([
        "## 2. Directory Locations & Hubs",
        "",
    ])

    if locations:
        for loc in locations:
            title = loc.get("title", "Unnamed")
            link_path = loc.get("path") or ""
            summary = loc.get("summary") or ""
            parent = f" (Parent: {loc.get('parent')})" if loc.get("parent") else ""
            lines.append(f"- **{title}**{parent} (`{link_path}`)")
            if summary:
                lines.append(f"  - {summary}")
        lines.append("")
    else:
        lines.extend(["No gazetteer locations catalogued.\n", ""])

    lines.extend([
        "## 3. Factions & Organisations",
        "",
    ])

    if factions:
        for f in factions:
            title = f.get("title", "Unnamed")
            summary = f.get("summary") or ""
            lines.append(f"- **{title}** (`{f.get('path', '')}`)")
            if summary:
                lines.append(f"  - {summary}")
        lines.append("")
    else:
        lines.extend(["No standalone factions catalogued.\n", ""])

    lines.extend([
        "## 4. Recent Session Recaps (Chronological Continuity)",
        "",
    ])

    # Sort sessions by nav_order or path
    recent_sessions = sorted(sessions_to_use, key=lambda s: str(s.get("nav_order") or s.get("path")))[-4:]
    if recent_sessions:
        for s in recent_sessions:
            title = s.get("title", "Untitled Episode")
            date_str = s.get("nav_order") or "Unknown date"
            region = s.get("region") or s.get("location") or "Unknown region"
            summary = s.get("summary") or "No recap available."
            lines.append(f"- **{title}** ({date_str} @ {region})")
            lines.append(f"  - {summary}")
        lines.append("")
    else:
        lines.extend(["No previous sessions catalogued.\n", ""])

    if decisions_text:
        lines.extend([
            "## 5. Active Tier 2 Table Rulings & Decisions",
            "",
            decisions_text,
            "",
        ])

    glossary_content = "\n".join(lines).strip() + "\n"

    out_glossary_path.parent.mkdir(parents=True, exist_ok=True)
    out_glossary_path.write_text(glossary_content, encoding="utf-8")

    # Formulate compact proper nouns prompt for whisper-cli (<= 220 tokens / words)
    # Priority: PCs and characters, current locations, key factions
    priority_nouns: List[str] = []
    for p in people[:15]:
        name = p.get("title", "")
        # Remove parentheses or call-signs
        clean_name = re.sub(r"\(.*?\)", "", name).strip()
        if clean_name and clean_name not in priority_nouns:
            priority_nouns.append(clean_name)

    for loc in locations[:12]:
        name = loc.get("title", "")
        clean_name = re.sub(r"\(.*?\)", "", name).strip()
        if clean_name and clean_name not in priority_nouns:
            priority_nouns.append(clean_name)

    for f in factions[:6]:
        name = f.get("title", "")
        clean_name = re.sub(r"\(.*?\)", "", name).strip()
        if clean_name and clean_name not in priority_nouns:
            priority_nouns.append(clean_name)

    return glossary_content, priority_nouns


def normalise_audio(input_file: Path, output_wav: Path) -> None:
    """Downmix and normalise any input audio/video to 16 kHz 16-bit mono PCM WAV."""
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg binary not found. Please install via `brew install ffmpeg`.")

    cmd = [
        "ffmpeg",
        "-y",
        "-i", str(input_file),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(output_wav),
        "-loglevel", "error"
    ]

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"ffmpeg conversion failed: {res.stderr}")


def transcribe_audio(
    model_path: Path,
    wav_path: Path,
    output_base: Path,
    proper_nouns: List[str],
    language: Optional[str] = None
) -> Path:
    """Execute whisper-cli on Apple Metal GPU to produce a verbatim text transcript."""
    if not shutil.which("whisper-cli"):
        raise RuntimeError("whisper-cli binary not found. Please install via `brew install whisper-cpp`.")

    if not model_path.exists():
        raise FileNotFoundError(
            f"Whisper model not found at {model_path}. "
            f"Please download ggml-large-v3-turbo.bin to ~/.whisper-models/."
        )

    cmd = [
        "whisper-cli",
        "-m", str(model_path),
        "-f", str(wav_path),
        "-otxt",
        "-of", str(output_base)
    ]

    if language:
        cmd.extend(["-l", language])

    # Inject proper-noun prompt bias if available
    if proper_nouns:
        prompt_str = ", ".join(proper_nouns)
        cmd.extend(["--prompt", prompt_str])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"whisper-cli failed: {res.stderr or res.stdout}")

    out_txt = output_base.with_suffix(".txt")
    if not out_txt.exists():
        raise FileNotFoundError(f"Expected transcript file {out_txt} was not created.")

    return out_txt


def main():
    parser = argparse.ArgumentParser(
        description="Transcribe tabletop RPG session audio with local Metal GPU Whisper and generate campaign glossary."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        type=str,
        help="Path to input audio/video recording (.mkv, .mp4, .wav, .m4a) or transcript (.txt)"
    )
    parser.add_argument("--repo-root", type=str, default=None, help="Campaign repository root (defaults to CWD)")
    parser.add_argument("--drive-dir", type=str, default=None, help="Override Google Drive campaign folder")
    parser.add_argument("--session-slug", type=str, default=None, help="Custom slug (e.g. 2026-10-23_ep012)")
    parser.add_argument(
        "--language", "-l",
        type=str,
        default=None,
        help="Spoken language code for Whisper (e.g. pt, en, auto)"
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default=str(DEFAULT_MODEL_PATH),
        help="Path to ggml model binary (default: ~/.whisper-models/ggml-large-v3-turbo.bin)"
    )
    parser.add_argument("--archive-recording", action="store_true", help="Copy source recording to Google Drive _sessions/")
    parser.add_argument("--skip-transcribe", action="store_true", help="Skip ASR and reuse existing transcript in _sessions/")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON manifest")

    args = parser.parse_args()

    # 1. Resolve paths
    repo_root = find_campaign_root(args.repo_root)
    drive_dir = find_drive_dir(repo_root, args.drive_dir)
    sessions_dir = drive_dir / "_sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)

    input_path = Path(args.input_file).expanduser().resolve() if args.input_file else None
    is_text_input = bool(input_path and input_path.suffix.lower() in (".txt", ".md", ".vtt", ".srt"))
    skip_transcribe = args.skip_transcribe or is_text_input

    if not skip_transcribe and (not input_path or not input_path.exists()):
        print(f"Error: Input recording '{args.input_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # 2. Campaign defaults and next chapter discovery
    campaign_defaults = parse_campaign_defaults(repo_root)
    next_chapter_info = discover_next_chapter(repo_root, campaign_defaults)

    # 3. Determine session slug
    if args.session_slug:
        slug = args.session_slug
    else:
        date_prefix = datetime.now().strftime("%Y-%m-%d")
        ep_prefix = Path(next_chapter_info["next_filename"]).stem
        slug = f"{date_prefix}_{ep_prefix}"

    glossary_path = sessions_dir / f"{slug}_glossary.md"
    transcript_base = sessions_dir / f"{slug}_transcript"
    transcript_path = sessions_dir / f"{slug}_transcript.txt"
    notes_path = sessions_dir / f"{slug}_session_notes.md"

    # 4. Dynamic Glossary
    _, proper_nouns = build_dynamic_glossary(repo_root, glossary_path, slug, defaults=campaign_defaults)

    whisper_lang = args.language or campaign_defaults.get("session_language") or "en"

    # 5. Audio Normalisation & Metal Transcription / Transcript Ingestion
    if not skip_transcribe:
        if not input_path.exists():
            print(f"Error: Input recording '{input_path}' does not exist.", file=sys.stderr)
            sys.exit(1)
        temp_wav = Path(f"/tmp/{slug}_16k.wav")
        try:
            if not args.json:
                print(f"==> [1/2] Normalising audio container '{input_path.name}' to 16 kHz mono WAV...")
            normalise_audio(input_path, temp_wav)

            if not args.json:
                print(f"==> [2/2] Transcribing with whisper-cli on Apple Metal GPU (lang={whisper_lang}, prompting {len(proper_nouns)} proper nouns)...")
            transcribe_audio(Path(args.model_path), temp_wav, transcript_base, proper_nouns, language=whisper_lang)

            if args.archive_recording:
                dest_rec = sessions_dir / input_path.name
                if not dest_rec.exists():
                    if not args.json:
                        print(f"==> Archiving original recording to {dest_rec}...")
                    shutil.copy2(input_path, dest_rec)
        finally:
            if temp_wav.exists():
                temp_wav.unlink()
    else:
        # Pre-transcribed input or reuse of existing transcript
        is_generated_artifact = bool(
            input_path and (
                input_path in (transcript_path, glossary_path, notes_path)
                or input_path.name.endswith(("_glossary.md", "_session_notes.md"))
            )
        )
        if input_path and input_path.exists() and input_path.is_file() and not is_generated_artifact:
            if not args.json:
                print(f"==> Ingesting pre-transcribed text from '{input_path.name}' into {transcript_path}...")
            shutil.copy2(input_path, transcript_path)
        elif not transcript_path.exists() and not args.skip_transcribe:
            print(f"Error: Transcript file not found at '{input_path}' or '{transcript_path}'.", file=sys.stderr)
            sys.exit(1)

    manifest: Dict[str, Any] = {
        "status": "success",
        "campaign": repo_root.name,
        "repo_root": str(repo_root),
        "drive_dir": str(drive_dir),
        "session_slug": slug,
        "session_language": whisper_lang,
        "transcript_path": str(transcript_path),
        "glossary_path": str(glossary_path),
        "session_notes_path": str(notes_path),
        "campaign_defaults": campaign_defaults,
        "next_chapter_info": next_chapter_info,
        "proper_nouns_count": len(proper_nouns),
    }

    if args.json:
        print(json.dumps(manifest, indent=2, ensure_ascii=False))
    else:
        print("\n" + "=" * 60)
        print(f"Campaign: {repo_root.name}")
        print(f"Session Slug: {slug}")
        print(f"Transcript: {transcript_path}")
        print(f"Glossary:   {glossary_path}")
        print(f"Target Chapter: {next_chapter_info['next_chapter_path']}")
        print(f"Target Session Notes: {notes_path}")
        print("=" * 60)
        print("Ready for Stage 4 Antigravity synthesis via `scribe-session`.")


if __name__ == "__main__":
    main()
