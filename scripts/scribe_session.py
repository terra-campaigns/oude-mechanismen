#!/usr/bin/env python3
"""
Air-gapped local session audio transcriber and two-pass notes extractor for tabletop RPG campaign vaults.

Pipeline stages handled:
1. Executes acoustic audio transcription via Metal GPU Whisper (whisper-cli) with dynamic glossary bias into local disk air-gap (~/Private/rpg-sessions/<campaign>/).
2. Executes decomposed local two-pass de-personalised extraction via Ollama:
   - Pass 2A: Chronological & tactical facts (<slug>_tactical_facts.md in Google Drive _sessions/).
   - Pass 2B: Sensory & environmental textures (<slug>_sensory_textures.md in Google Drive _sessions/).

Outputs are de-personalised and stored in Google Drive, clearing the air-gap for Gemini in Antigravity chat to merge notes and draft chapter prose.
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
from typing import Any, Dict, List, Optional


def find_campaign_root(explicit_root: Optional[str] = None) -> Path:
    """Locate the target campaign repository root."""
    if explicit_root:
        p = Path(explicit_root).resolve()
        for candidate in [p, *p.parents]:
            if (candidate / ".agents").is_dir() or (candidate / "_config.yml").is_file():
                return candidate
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
    num_ctx: int = 32768,
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
    """Read transcript, glossary, and table rulings."""
    context: Dict[str, str] = {
        "transcript": "",
        "glossary": "",
        "decisions": "",
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

    return context


def extract_tactical_facts(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
) -> str:
    """
    Pass 2A: Prompt local Ollama model to extract chronological and tactical facts.
    Strictly de-personalises the transcript by stripping player banter and real-world names.
    Outputs structured Markdown saved to Google Drive (_sessions/<slug>_tactical_facts.md).
    """
    slug = manifest["session_slug"]
    campaign = manifest["campaign"]
    next_info = manifest.get("next_chapter_info", {})
    region = next_info.get("previous_region") or manifest.get("campaign_defaults", {}).get("location_key", "Unknown Region")
    date_str = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are the campaign tactical scribe for '{campaign}'.
Extract hard chronological and tactical facts from the provided raw session transcript.

Crucial Directives:
1. DE-PERSONALISATION MANDATE: Strip all out-of-character chatter, player real names, rules lookups, jokes, and player meta-dialogue. Refer ONLY to in-universe characters using canonical names from the glossary.
2. Chronological sequence: Record each tactical decision, movement, location change, and adversary encounter in strict chronological order.
3. Mechanical outcomes: Record adversaries faced, weapons/tactics employed, damage taken, hazards triggered, and dice check results.
4. Character status: Record all sustained physical wounds, trauma, psychological conditions, and status tracker changes for each character.
5. Economy & inventory: Record credits/currency gained, spent, or lost; ammunition spent; cargo trades; equipment damaged or acquired.
6. Table rulings: Record any explicit GM rulings, procedural interpretations, or custom naming conventions established during play.
7. Write strictly in British English spelling (e.g. armour, colour, categorised, synthesise).
8. Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
9. Output ONLY the complete Markdown document. Do not wrap in outer backticks or conversational chatter.

Required Structure:
# Session Tactical Facts: <Evocative Session Title>

> [!NOTE]
> De-personalised tactical & chronological facts for `{campaign}`.
> Slug: `{slug}` | Date: `{date_str}` | Location: `{region}`

## 1. Chronological Timeline & Tactical Sequence
- [Beat 1] Detailed chronological entry...
- [Beat 2] Detailed chronological entry...

## 2. Combat Encounters & Tactical Decisions
- Adversaries encountered, tactical actions taken, weapons used, and outcomes.

## 3. Physical Trauma, Wounds & Psychological Stress
- Detailed condition and wound updates for each involved character.

## 4. Technical Hazards, Environmental Damage & Malfunctions
- Malfunctions, structural integrity damage, environmental hazards triggered.

## 5. Economic Ledger: Loot, Cargo, Currency & Ammunition
- Precise credits/currency gained or spent, ammunition expended, salvage acquired.

## 6. Table Rulings & Candidate Canon Decisions
- Rulings, house rules, and custom conventions established at the table.

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
    raw_facts = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.2,
        log_prefix="    [Tactical Facts 2A] ",
    )
    return enforce_markdown_cleanliness(raw_facts)


def extract_sensory_textures(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
) -> str:
    """
    Pass 2B: Prompt local Ollama model to extract evocative sensory and atmospheric textures.
    Strictly de-personalises the transcript by capturing in-character dialogue and physical descriptions.
    Outputs structured Markdown saved to Google Drive (_sessions/<slug>_sensory_textures.md).
    """
    slug = manifest["session_slug"]
    campaign = manifest["campaign"]
    next_info = manifest.get("next_chapter_info", {})
    region = next_info.get("previous_region") or manifest.get("campaign_defaults", {}).get("location_key", "Unknown Region")
    date_str = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are the sensory archivist and environmental scribe for '{campaign}'.
Extract vivid environmental textures, atmospheric grit, in-character quotes, and physical details from the provided raw session transcript.

Crucial Directives:
1. DE-PERSONALISATION MANDATE: Strip all out-of-character player banter, real-world comments, and meta-jokes. Preserve rich in-character roleplay, character mannerisms, and physical environment descriptions.
2. Lighting & visual palette: Capture illumination details (e.g. flickering dying fluorescent tubes, dim CRT phosphor, void glare, emergency strobes).
3. Acoustics & sounds: Capture auditory texture (e.g. hydraulic hiss, distant bulkheads groaning, cooling fans whining, dead silence).
4. Odours & sensations: Capture tactile and olfactory details (e.g. rancid metallic copper, burnt insulation, ozone reek, freezing draughts, sticky fluids).
5. In-character dialogue: Capture memorable verbatim in-universe quotes, voice inflections, and verbal confrontations.
6. Tactile improvisations: Capture physical interactions with the environment (e.g. wedging an iron bar into rotary hatch gears to block pursuers).
7. Write strictly in British English spelling (e.g. odour, colour, grey, oxidised).
8. Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
9. Output ONLY the complete Markdown document. Do not wrap in outer backticks or conversational chatter.

Required Structure:
# Session Sensory & Environmental Textures: <Evocative Session Title>

> [!NOTE]
> De-personalised atmospheric & sensory textures for `{campaign}`.
> Slug: `{slug}` | Date: `{date_str}` | Location: `{region}`

## 1. Environmental Grime, Materials & Atmosphere
- Physical textures, room conditions, zero-G drift, stains, wear, and corrosion.

## 2. Lighting, Shadows & Visual Palette
- Illumination levels, screen glows, emergency lighting, shadows, and darkness.

## 3. Acoustics, Ambient Sounds & Mechanical Hum
- Auditory ambience, machinery sounds, reverberation, hull strain, and radio static.

## 4. Smells, Tastes & Atmospheric Quality
- Odours, air quality, chemical stenches, heat, and cold.

## 5. In-Character Roleplay, Dialogue Quotes & Mannerisms
- Iconic dialogue lines, physical expressions, non-verbal tensions, and character voice.

## 6. Environmental Improvisations & Tactile Solutions
- Spontaneous physical actions utilizing the surrounding terrain or equipment.

---
### Session Glossary:
{context['glossary'][:4000]}

---
### Verbatim Session Transcript:
{context['transcript']}
"""
    raw_textures = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.3,
        log_prefix="    [Sensory Textures 2B] ",
    )
    return enforce_markdown_cleanliness(raw_textures)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Air-gapped local session audio transcriber and two-pass notes extractor for campaign vaults."
    )
    parser.add_argument("input_file", help="Path to session audio/video recording (.mkv, .mp4, .wav, etc.) or pre-transcribed text file (.txt).")
    parser.add_argument("--repo-root", help="Explicit path to campaign repository root.")
    parser.add_argument("--airgap-dir", help="Override local air-gap storage directory (default: ~/Private/rpg-sessions/<campaign>).")
    parser.add_argument("--model", help="Explicit Ollama model override for all extraction passes (default: qwen2.5:14b).")
    parser.add_argument("--model-tactical", help="Explicit Ollama model override for Pass 2A tactical facts (default: qwen2.5:14b).")
    parser.add_argument("--model-sensory", help="Explicit Ollama model override for Pass 2B sensory textures (default: mistral-nemo:12b or qwen2.5:14b).")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--skip-transcribe", action="store_true", help="Skip Whisper acoustic transcription and reuse existing transcript.")
    parser.add_argument("--language", help="Whisper language code override (e.g. 'en', 'pt').")
    parser.add_argument("--dry-run", action="store_true", help="Perform extraction without writing output files.")
    parser.add_argument("--keep-alive", default="15m", help="Ollama model keep-alive duration (default: 15m).")

    args = parser.parse_args()

    repo_root = find_campaign_root(args.repo_root)
    input_file = Path(args.input_file).resolve()

    start_time = time.time()
    print("=" * 70)
    print("OUDE MECHANISMEN — AIR-GAPPED SESSION NOTES EXTRACTOR")
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
    print("\n==> [Stage 1] Running acoustic transcription and context discovery...")
    manifest = run_acoustic_pipeline(
        repo_root,
        input_file,
        skip_transcribe=args.skip_transcribe,
        language=args.language,
        airgap_dir=args.airgap_dir,
    )

    context = read_context_files(repo_root, manifest)
    tactical_model = args.model_tactical or args.model or "qwen2.5:14b"
    sensory_model = args.model_sensory or args.model or "qwen2.5:14b"

    # 3. Stage 2: Decomposed Local Two-Pass Extraction (Pass 2A & Pass 2B)
    print("\n==> [Stage 2] Executing Decomposed Local Two-Pass Extraction...")
    print(f"    Verbatim Transcript:  {len(context['transcript'].split())} words (Air-Gapped Tier 0)")
    print(f"    Dynamic Glossary:     {len(context['glossary'].splitlines())} lines")

    # Pass 2A: Tactical Facts Extraction
    print(f"\n    --> [Pass 2A] Extracting Chronological & Tactical Facts via '{tactical_model}'...")
    tactical_facts_text = extract_tactical_facts(
        args.ollama_url,
        tactical_model,
        manifest,
        context,
    )
    tactical_p = Path(manifest["tactical_facts_path"])
    if not args.dry_run:
        tactical_p.parent.mkdir(parents=True, exist_ok=True)
        tactical_p.write_text(tactical_facts_text, encoding="utf-8")
        print(f"        [Saved] {tactical_p} ({len(tactical_facts_text.split())} words)")
    else:
        print(f"        [Dry-Run] Skipped writing {tactical_p}")

    # Pass 2B: Sensory Textures Extraction
    print(f"\n    --> [Pass 2B] Extracting Sensory & Atmospheric Textures via '{sensory_model}'...")
    sensory_textures_text = extract_sensory_textures(
        args.ollama_url,
        sensory_model,
        manifest,
        context,
    )
    sensory_p = Path(manifest["sensory_textures_path"])
    if not args.dry_run:
        sensory_p.parent.mkdir(parents=True, exist_ok=True)
        sensory_p.write_text(sensory_textures_text, encoding="utf-8")
        print(f"        [Saved] {sensory_p} ({len(sensory_textures_text.split())} words)")
    else:
        print(f"        [Dry-Run] Skipped writing {sensory_p}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("LOCAL EXTRACTION COMPLETE")
    print(f"Elapsed Time:    {elapsed / 60:.1f} minutes")
    print(f"Tier 0 Air-Gap:  {manifest['transcript_path']}")
    print(f"Tactical Facts:  {manifest['tactical_facts_path']} (Tier 2 Drive)")
    print(f"Sensory Textures:{manifest['sensory_textures_path']} (Tier 2 Drive)")
    print("\nAir-gap privacy boundary cleared.")
    print("Ready for Gemini in Antigravity chat to merge notes and draft chapter prose.")
    print("=" * 70)


if __name__ == "__main__":
    main()
