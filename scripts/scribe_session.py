#!/usr/bin/env python3
"""
Fully local, setting-aware session scribing orchestrator for tabletop RPG campaign vaults.

Pipeline stages handled:
1. Executes acoustic audio transcription via Metal GPU Whisper (whisper-cli) with dynamic glossary bias.
2. Ingests raw transcript, campaign glossary, table decisions, continuity anchors, and AGENTS.md conventions.
3. Selects the appropriate local Ollama model (scribe-14b or scribe-14b-bilingual) based on campaign settings.
4. Generates Archival GM Session Notes (8 canonical sections) in Google Drive.
5. Generates the Canonical Draft Chapter in the campaign repository with setting voice and cross-links.
6. Refreshes the Tier 1 semantic catalogue via data_extractor.rb.

All outputs, prompts, and logs strictly adhere to British English.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def find_campaign_root(explicit_root: Optional[str] = None) -> Path:
    """Locate the target campaign repository root."""
    if explicit_root:
        p = Path(explicit_root).resolve()
        if (p / ".agents").is_dir() or (p / "_config.yml").is_file():
            return p
        raise FileNotFoundError(f"Specified repo root '{explicit_root}' is not a valid campaign repository.")

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "_config.yml").exists() or (candidate / ".agents").is_dir():
            return candidate

    raise FileNotFoundError(
        f"Could not locate a campaign repository from current directory '{cwd}'. "
        f"Please run from within a campaign vault or pass --repo-root."
    )


def check_ollama_status(url: str) -> bool:
    """Check if the local Ollama daemon is reachable."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def query_ollama_stream(
    url: str,
    model: str,
    prompt: str,
    system: Optional[str] = None,
    num_ctx: int = 24576,
    temperature: float = 0.25,
    keep_alive: str = "15m",
    log_prefix: str = "    ",
) -> str:
    """Send an inference request to Ollama with streaming progress output."""
    endpoint = f"{url.rstrip('/')}/api/generate"
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": keep_alive,
        "options": {
            "num_ctx": num_ctx,
            "temperature": temperature,
        },
    }
    if system:
        payload["system"] = system

    req = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    full_response: List[str] = []
    line_buf = ""
    print(f"{log_prefix}Connecting to local model '{model}' (ctx={num_ctx})...", flush=True)

    try:
        with urllib.request.urlopen(req, timeout=1800) as resp:
            for raw_chunk in resp:
                if not raw_chunk:
                    continue
                try:
                    data = json.loads(raw_chunk.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                token = data.get("response", "")
                if token:
                    full_response.append(token)
                    line_buf += token
                    if "\n" in line_buf:
                        sys.stdout.write(f"{log_prefix}{line_buf}")
                        sys.stdout.flush()
                        line_buf = ""

                if data.get("done", False):
                    break

        if line_buf:
            sys.stdout.write(f"{log_prefix}{line_buf}\n")
            sys.stdout.flush()

    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama inference error connecting to {endpoint}: {e}")

    return "".join(full_response).strip()


def enforce_markdown_cleanliness(text: str) -> str:
    """Ensure an empty blank line immediately follows any Markdown heading."""
    lines = text.splitlines()
    cleaned: List[str] = []
    for i, line in enumerate(lines):
        cleaned.append(line)
        if re.match(r"^#{1,6}\s", line):
            # Check if next line is not blank
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                cleaned.append("")
    return "\n".join(cleaned).strip() + "\n"


def run_acoustic_pipeline(
    repo_root: Path,
    input_file: Path,
    skip_transcribe: bool = False,
    language: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute transcribe_session.py to acquire acoustic transcript and discovery manifest."""
    script_candidates = [
        repo_root / ".agents" / "scripts" / "transcribe_session.py",
        Path(__file__).resolve().parent / "transcribe_session.py",
        repo_root.parent / "oude-mechanismen" / "scripts" / "transcribe_session.py",
    ]
    script_path = next((p for p in script_candidates if p.exists()), None)
    if not script_path:
        raise FileNotFoundError("Could not locate 'transcribe_session.py' in repository or engine.")

    cmd = [sys.executable, str(script_path), str(input_file), "--json", "--repo-root", str(repo_root)]
    if skip_transcribe:
        cmd.append("--skip-transcribe")
    if language:
        cmd.extend(["--language", language])

    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RuntimeError(
            f"transcribe_session.py failed with return code {res.returncode}:\n{res.stderr.strip()}"
        )

    try:
        return json.loads(res.stdout.strip())
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse manifest from transcribe_session.py:\n{res.stdout}\nError: {e}")


def read_context_files(
    repo_root: Path,
    manifest: Dict[str, Any],
) -> Dict[str, str]:
    """Read transcript, glossary, table rulings, continuity, and AGENTS.md conventions."""
    context: Dict[str, str] = {
        "transcript": "",
        "glossary": "",
        "decisions": "",
        "previous_chapter": "",
        "agents_instructions": "",
    }

    transcript_p = Path(manifest["transcript_path"])
    if transcript_p.exists():
        context["transcript"] = transcript_p.read_text(encoding="utf-8").strip()

    glossary_p = Path(manifest["glossary_path"])
    if glossary_p.exists():
        context["glossary"] = glossary_p.read_text(encoding="utf-8").strip()

    decisions_p = repo_root / ".agents" / "context" / "decisions.md"
    if decisions_p.exists():
        context["decisions"] = decisions_p.read_text(encoding="utf-8").strip()

    agents_p = repo_root / ".agents" / "AGENTS.md"
    if agents_p.exists():
        context["agents_instructions"] = agents_p.read_text(encoding="utf-8").strip()

    prev_chapter_file = manifest.get("next_chapter_info", {}).get("previous_chapter_file")
    if prev_chapter_file:
        prev_p = repo_root / prev_chapter_file
        if prev_p.exists():
            context["previous_chapter"] = prev_p.read_text(encoding="utf-8").strip()

    return context


def resolve_model_name(
    explicit_model: Optional[str],
    manifest: Dict[str, Any],
    agents_text: str,
) -> str:
    """Determine whether to use scribe-14b or scribe-14b-bilingual."""
    if explicit_model:
        return explicit_model

    session_lang = manifest.get("session_language", "en").lower()
    is_bilingual = bool(
        "Bilingual" in agents_text
        or session_lang.startswith("pt")
        or "Portuguese" in agents_text
    )

    if is_bilingual:
        return "scribe-14b-bilingual"
    return "scribe-14b"


def synthesise_archival_notes(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
) -> str:
    """Prompt local model to produce the 8 canonical GM archival notes sections."""
    slug = manifest["session_slug"]
    campaign = manifest["campaign"]
    next_info = manifest.get("next_chapter_info", {})
    region = next_info.get("previous_region") or manifest["campaign_defaults"].get("location_key", "Unknown Region")
    date_str = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are the campaign archivist for '{campaign}'.
Synthesise the provided raw session transcript into comprehensive, structured archival GM session notes.

Context & Rules:
1. Strip all out-of-character chatter, banter, dice maths, and rules lookups.
2. Reconcile phonetic spelling errors using the provided glossary.
3. Write strictly in British English spelling (e.g. colour, flavour, categorised, synthesise).
4. Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
5. Output ONLY the complete Markdown document. Do not wrap in outer backticks or conversational chatter.

Required Structure:
# Session Notes: <Evocative Session Title>

> [!NOTE]
> Synthesised from raw session recording for `{campaign}`.
> Slug: `{slug}` | Date: `{date_str}` | Location: `{region}`

## 1. Executive Summary
A punchy title and 2–3 sentence executive recap of the session's major events.

## 2. Chronological Plot Beats
Detailed bullet points of key decisions, roleplay scenes, travels, and revelations in chronological order.

## 3. NPCs & Factions
- Characters encountered, noting disposition changes and lore revealed.
- Reference known directory links from the glossary where applicable.
- Mark newly introduced entities as `[New Entity — Candidate for add-character]`.

## 4. Quests, Contracts & Objectives
New hooks acquired, corporate/patron obligations updated, debts incurred, and completed milestones.

## 5. Combat, Hazards & Encounters
Adversaries faced, environmental malfunctions/hazards triggered, tactical decisions, and mechanical outcomes.

## 6. Loot, Trade & Inventory Ledger
Credits, currency, or salvage gained, spent, or lost; cargo trades; equipment wear; debt payments.

## 7. Table Rulings & Candidate Tier 2 Decisions
Any explicit GM rulings, procedural interpretations, or custom naming conventions established during play that should be considered for `.agents/context/decisions.md`.

## 8. Unresolved Hooks & Next Steps
Immediate cliffhangers, party intentions, and open threads for the upcoming session.

---
### Session Glossary:
{context['glossary'][:4000]}

---
### Active Decisions (Tier 2 Canon):
{context['decisions'][:2000]}

---
### Verbatim Session Transcript:
{context['transcript']}
"""
    raw_notes = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.25,
        log_prefix="    [Notes] ",
    )
    return enforce_markdown_cleanliness(raw_notes)


def synthesise_draft_chapter(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
    notes_markdown: str,
) -> str:
    """Prompt local model to produce the canonical in-voice draft chapter file."""
    campaign = manifest["campaign"]
    defaults = manifest["campaign_defaults"]
    next_info = manifest.get("next_chapter_info", {})
    target_path = Path(next_info.get("next_chapter_path", "campaigns/chapter.md"))
    parent_title = next_info.get("previous_parent") or campaign
    location_key = defaults.get("location_key", "region")
    location_val = next_info.get("previous_region") or "Unknown"
    date_val = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    hubs = defaults.get("hub_pages", [])
    hub_links_str = "\n".join(f"- [index]({h})" for h in hubs) if hubs else "- [index](index.md)"

    is_bilingual = bool("bilingual" in model.lower())

    prompt = f"""You are the chronicler drafting the canonical campaign chapter for '{campaign}'.
Draft the official chapter file based on the synthesised GM notes.

Target File: `{target_path.name}`
Parent Index: `{parent_title}`
Front Matter Location Key: `{location_key}: {location_val}`
Front Matter nav_order: `{date_val}`

Formatting Constraints:
1. Canonical Front Matter:
---
layout: default
type: session
nav_exclude: false

parent: {parent_title}
title: <Evocative Episode Title>
{location_key}: {location_val}
nav_order: {date_val}
footer_content: 

images:

---

2. Immediate Scaffolding Block:
{{% include header_chapter.md %}}
{{% comment %}}
`=map(this.images, (x) => "![im|200](" + x + ")")`
```dataview
LIST without ID "["+ title + "](" + regexreplace(file.path, ".md", "") + ")" + ", from " + regexreplace(file.folder, "^[^\\/]*\\/", "") FROM ([[]]) OR outgoing([[]]) WHERE file.path != this.file.path SORT file.folder DESC
```
---

{hub_links_str}

{{% endcomment %}}

3. Chapter Body Constraints:
- Structure into 2 to 4 themed subsections using `## Heading`.
- Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
- Each subsection must contain between 2 and 4 distinct paragraphs, separated by blank lines.
- Each paragraph must contain between 2 and 4 sentences. Place each sentence on its own line (one sentence per line) where practical.
- Embed relative Markdown links (`[Entity](../../directory/...)`) on the first mention of catalogued PCs, NPCs, factions, and locations from the glossary.
- Voice & Tone: Strictly follow the cadence, register, and style conventions described in the Campaign Specification below.
"""

    if is_bilingual:
        prompt += """
- Bilingual Delivery:
  - Generate the Brazilian Portuguese prose first, preceded by:
    English version below
    {: .text-delta .text-right}
  - Follow immediately with a horizontal rule: `---`
  - Provide the equivalent British English mirror translation below the divider.
"""
    else:
        prompt += """
- Language: Strictly British English spelling throughout (colour, armour, synthesise).
"""

    prompt += f"""
---
### Campaign Specification (Voice & Cadence):
{context['agents_instructions'][:3000]}

---
### Session Glossary:
{context['glossary'][:4000]}

---
### Synthesised GM Session Notes:
{notes_markdown}
"""

    raw_chapter = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.25,
        log_prefix="    [Chapter] ",
    )
    return enforce_markdown_cleanliness(raw_chapter)


def refresh_catalogue(repo_root: Path) -> None:
    """Run data_extractor.rb to re-index the campaign catalogue."""
    extractor = repo_root / "_plugins" / "data_extractor.rb"
    if extractor.exists():
        print("==> Refreshing Tier 1 semantic catalogue via data_extractor.rb...")
        try:
            subprocess.run(
                ["ruby", "--disable-gems", str(extractor)],
                cwd=str(repo_root),
                capture_output=True,
                check=False,
            )
            print("    [OK] Catalogue refreshed successfully.")
        except Exception as e:
            print(f"    [WARN] Catalogue refresh failed: {e}", file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local Metal GPU transcription and overnight Ollama synthesis for campaign sessions."
    )
    parser.add_argument("input_file", help="Path to session audio/video recording (.mkv, .mp4, .wav, etc.) or pre-transcribed text file (.txt).")
    parser.add_argument("--repo-root", help="Explicit path to campaign repository root.")
    parser.add_argument("--model", help="Explicit Ollama model override (e.g. scribe-14b, scribe-14b-bilingual).")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--skip-transcribe", action="store_true", help="Skip Whisper acoustic transcription and reuse existing transcript.")
    parser.add_argument("--language", help="Whisper language code override (e.g. 'en', 'pt').")
    parser.add_argument("--dry-run", action="store_true", help="Perform synthesis without writing output files.")
    parser.add_argument("--keep-alive", default="15m", help="Ollama model keep-alive duration (default: 15m).")

    args = parser.parse_args()

    repo_root = find_campaign_root(args.repo_root)
    input_file = Path(args.input_file).resolve()

    start_time = time.time()
    print("=" * 70)
    print("OUDE MECHANISMEN — LOCAL OVERNIGHT SESSION SCRIBE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Campaign:  {repo_root.name}")
    print(f"Input:     {input_file.name}")
    print("=" * 70)

    # 1. Verify Ollama accessibility
    if not check_ollama_status(args.ollama_url):
        print(f"Error: Local Ollama daemon is not responding at {args.ollama_url}.", file=sys.stderr)
        print("Please ensure Ollama is running (`brew services start ollama` or `ollama serve`).", file=sys.stderr)
        sys.exit(1)

    # 2. Stage 1: Acoustic Transcription & Manifest Extraction
    print("\n==> [Stage 1/4] Running acoustic transcription and context discovery...")
    manifest = run_acoustic_pipeline(
        repo_root,
        input_file,
        skip_transcribe=args.skip_transcribe,
        language=args.language,
    )

    # 3. Stage 2: Context Ingestion & Model Selection
    print("\n==> [Stage 2/4] Ingesting campaign context and selecting model profile...")
    context = read_context_files(repo_root, manifest)
    model_name = resolve_model_name(args.model, manifest, context["agents_instructions"])
    print(f"    Selected Ollama Model: '{model_name}'")
    print(f"    Verbatim Transcript:  {len(context['transcript'].split())} words")
    print(f"    Dynamic Glossary:     {len(context['glossary'].splitlines())} lines")

    # 4. Stage 3: Synthesise Archival GM Session Notes (Google Drive)
    print(f"\n==> [Stage 3/4] Synthesising Archival GM Session Notes via '{model_name}'...")
    notes_markdown = synthesise_archival_notes(
        args.ollama_url,
        model_name,
        manifest,
        context,
    )

    notes_path = Path(manifest["session_notes_path"])
    if not args.dry_run:
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text(notes_markdown, encoding="utf-8")
        print(f"\n    [Saved] {notes_path} ({len(notes_markdown.split())} words)")
    else:
        print(f"\n    [Dry-Run] Skipped writing to {notes_path}")

    # 5. Stage 4: Synthesise Canonical Draft Chapter (Git Vault)
    print(f"\n==> [Stage 4/4] Drafting Canonical Chapter via '{model_name}'...")
    chapter_markdown = synthesise_draft_chapter(
        args.ollama_url,
        model_name,
        manifest,
        context,
        notes_markdown,
    )

    target_chapter_path = Path(manifest["next_chapter_info"]["next_chapter_path"])
    if not args.dry_run:
        target_chapter_path.parent.mkdir(parents=True, exist_ok=True)
        target_chapter_path.write_text(chapter_markdown, encoding="utf-8")
        print(f"\n    [Saved] {target_chapter_path} ({len(chapter_markdown.split())} words)")
        refresh_catalogue(repo_root)
    else:
        print(f"\n    [Dry-Run] Skipped writing to {target_chapter_path}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SESSION SCRIBING COMPLETE")
    print(f"Elapsed Time: {elapsed / 60:.1f} minutes")
    print(f"GM Notes:     {notes_path}")
    print(f"Chapter:      {target_chapter_path}")
    print("All files kept locally. Zero data transmitted externally.")
    print("=" * 70)


if __name__ == "__main__":
    main()
