#!/usr/bin/env python3
"""
Fully local, setting-aware session notes orchestrator for tabletop RPG campaign vaults.

Pipeline stages handled:
1. Executes acoustic audio transcription via Metal GPU Whisper (whisper-cli) with dynamic glossary bias.
2. Ingests raw transcript into local disk air-gap (~/Private/rpg-sessions/<campaign>/).
3. Synthesises Archival GM Session Notes (8 canonical sections) in Google Drive (_sessions/) via local Ollama.
4. Leaves raw audio and speech text strictly local; synthesised notes are ready for Gemini in-voice chapter drafting.

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
    airgap_dir: Optional[str] = None,
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
    if airgap_dir:
        cmd.extend(["--airgap-dir", str(airgap_dir)])

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
    """Determine which local Ollama model to use for GM notes extraction."""
    if explicit_model:
        return explicit_model
    return "qwen2.5:14b"


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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run local Metal GPU transcription and Ollama archival session notes synthesis for campaign sessions."
    )
    parser.add_argument("input_file", help="Path to session audio/video recording (.mkv, .mp4, .wav, etc.) or pre-transcribed text file (.txt).")
    parser.add_argument("--repo-root", help="Explicit path to campaign repository root.")
    parser.add_argument("--airgap-dir", help="Override local air-gap storage directory (default: ~/Private/rpg-sessions/<campaign>).")
    parser.add_argument("--model", help="Explicit Ollama model override (default: qwen2.5:14b).")
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
    print("OUDE MECHANISMEN — LOCAL SESSION NOTES SCRIBE")
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
    print("\n==> [Stage 1/3] Running acoustic transcription and context discovery...")
    manifest = run_acoustic_pipeline(
        repo_root,
        input_file,
        skip_transcribe=args.skip_transcribe,
        language=args.language,
        airgap_dir=args.airgap_dir,
    )

    # 3. Stage 2: Context Ingestion & Model Selection
    print("\n==> [Stage 2/3] Ingesting campaign context and selecting model profile...")
    context = read_context_files(repo_root, manifest)
    model_name = resolve_model_name(args.model, manifest, context["agents_instructions"])
    print(f"    Selected Ollama Model: '{model_name}'")
    print(f"    Verbatim Transcript:  {len(context['transcript'].split())} words")
    print(f"    Dynamic Glossary:     {len(context['glossary'].splitlines())} lines")

    # 4. Stage 3: Synthesise Archival GM Session Notes (Google Drive)
    print(f"\n==> [Stage 3/3] Synthesising Archival GM Session Notes via '{model_name}'...")
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

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SESSION ARCHIVAL NOTES GENERATION COMPLETE")
    print(f"Elapsed Time: {elapsed / 60:.1f} minutes")
    print(f"Transcript:   {manifest['transcript_path']} (Tier 0 Air-Gap)")
    print(f"GM Notes:     {notes_path} (Tier 2 Google Drive)")
    print("All private table banter kept strictly in local air-gap.")
    print("Ready for canonical chapter drafting via Gemini in Antigravity chat.")
    print("=" * 70)


if __name__ == "__main__":
    main()
