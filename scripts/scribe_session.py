#!/usr/bin/env python3
"""
Air-gapped local session audio transcriber and two-pass notes extractor for tabletop RPG campaign vaults.

Pipeline stages handled:
1. Executes acoustic audio transcription via Metal GPU Whisper (whisper-cli) with dynamic glossary bias into local disk air-gap (~/Private/rpg-sessions/<campaign>/).
2. Executes decomposed local two-pass de-personalised extraction via Ollama:
   - Pass 2A: Chronological & tactical facts (<slug>_tactical_facts.md in _gm-materials/session-summaries/).
   - Pass 2B: Sensory & environmental textures (<slug>_sensory_textures.md in _gm-materials/session-summaries/).

Outputs are de-personalised and stored in _gm-materials/session-summaries/, clearing the air-gap for Gemini in Antigravity chat to merge notes and draft chapter prose.
All outputs, prompts, and logs strictly adhere to British English.
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROMPT_BOUNDARY_RE = re.compile(
    r"(?:^|\n)(?:---\s*\n)?###\s+(?:Session Glossary|Active Decisions|Verbatim Session Transcript)\b",
    re.IGNORECASE,
)

OLLAMA_STOP_SEQUENCES: List[str] = [
    "\n---\n### Session Glossary:",
    "\n---\n### Active Decisions",
    "\n---\n### Verbatim Session Transcript:",
    "### Session Glossary:",
    "### Verbatim Session Transcript:",
]


def find_campaign_root(explicit_root: Optional[str] = None) -> Path:
    """Locate the target campaign repository root."""
    if explicit_root:
        p = Path(explicit_root).expanduser().resolve()
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
    stop: Optional[List[str]] = None,
    log_prefix: str = "    ",
) -> str:
    """Send an inference request to Ollama with streaming progress output."""
    endpoint = f"{url.rstrip('/')}/api/generate"
    options: Dict[str, Any] = {
        "num_ctx": num_ctx,
        "temperature": temperature,
    }
    if stop:
        options["stop"] = stop

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "keep_alive": keep_alive,
        "options": options,
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
    print(f"{log_prefix}Connecting to local model '{model}' (ctx={num_ctx}, keep_alive={keep_alive})...", flush=True)

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
    """Ensure an empty blank line immediately follows any Markdown heading outside fenced code blocks."""
    lines = text.splitlines()
    cleaned: List[str] = []
    in_fence = False

    for i, line in enumerate(lines):
        cleaned.append(line)
        if re.match(r"^\s*(```|~~~)", line):
            in_fence = not in_fence
            continue
        if not in_fence and re.match(r"^#{1,6}\s", line):
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                cleaned.append("")

    return "\n".join(cleaned).strip() + "\n"


def strip_prompt_echo(raw_text: str, pass_label: str = "extraction") -> str:
    """
    Strip any echoed prompt boundary sections (Glossary, Active Decisions, or Verbatim Transcript)
    so Tier 0 verbatim dialogue can never leak into Tier 2 Google Drive notes, and reject empty output.
    """
    clean_text = PROMPT_BOUNDARY_RE.split(raw_text, maxsplit=1)[0].strip()
    if not clean_text:
        raise RuntimeError(f"Local model returned empty output during {pass_label}.")
    return clean_text


def resolve_session_metadata(manifest: Dict[str, Any]) -> Tuple[str, str]:
    """
    Resolve recording date and last-known campaign locus from the discovery manifest
    without mistaking schema field names (location_key) for places or stamping stale chapter dates.
    """
    slug = str(manifest.get("session_slug", ""))
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[_\b]|$)", slug)
    recorded_date = date_match.group(1) if date_match else datetime.now(timezone.utc).strftime("%Y-%m-%d")

    next_info = manifest.get("next_chapter_info") or {}
    last_locus = next_info.get("previous_region") or "Unspecified Locus"
    return recorded_date, last_locus


def run_acoustic_pipeline(
    repo_root: Path,
    input_file: Optional[Path] = None,
    skip_transcribe: bool = False,
    language: Optional[str] = None,
    airgap_dir: Optional[str] = None,
    session_slug: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute transcribe_session.py to acquire acoustic transcript and discovery manifest."""
    script_candidates = [
        Path(__file__).resolve().parent / "transcribe_session.py",
        repo_root / ".agents" / "scripts" / "transcribe_session.py",
        repo_root.parent / "oude-mechanismen" / "scripts" / "transcribe_session.py",
    ]
    script_path = next((p for p in script_candidates if p.exists()), None)
    if not script_path:
        raise FileNotFoundError("Could not locate 'transcribe_session.py' in engine or campaign repository.")

    venv_python = repo_root / ".agents" / "venv" / "bin" / "python3"
    python_bin = str(venv_python) if venv_python.exists() else sys.executable

    cmd = [python_bin, str(script_path)]
    if input_file is not None:
        cmd.append(str(input_file))
    cmd.extend(["--json", "--repo-root", str(repo_root)])

    if skip_transcribe:
        cmd.append("--skip-transcribe")
    if language:
        cmd.extend(["--language", language])
    if airgap_dir:
        cmd.extend(["--airgap-dir", str(airgap_dir)])
    if session_slug:
        cmd.extend(["--session-slug", str(session_slug)])

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


def build_tactical_prompt(manifest: Dict[str, Any], context: Dict[str, str]) -> str:
    """Construct the setting-agnostic Pass 2A tactical facts extraction prompt."""
    slug = manifest.get("session_slug", "unknown_session")
    campaign = manifest.get("campaign", "campaign")
    recorded_date, last_locus = resolve_session_metadata(manifest)
    genre = (manifest.get("campaign_defaults") or {}).get("genre")
    genre_line = f"\nCampaign Genre Context: {genre}" if genre else ""

    return f"""You are the campaign tactical scribe for '{campaign}'.{genre_line}
Extract hard chronological and tactical facts from the provided raw session transcript.

Crucial Directives:
1. DE-PERSONALISATION MANDATE: Strip all out-of-character chatter, player real names, rules lookups, jokes, and player meta-dialogue. Refer ONLY to in-universe characters using canonical names from the glossary.
2. Chronological sequence: Record each tactical decision, movement, location change, and adversary encounter in strict chronological order.
3. Mechanical outcomes: Record adversaries faced, weapons/tactics employed, damage taken, hazards triggered, and dice check results.
4. Character status: Record all sustained physical wounds, trauma, psychological conditions, and status tracker changes for each character.
5. Economy & inventory: Record currency/trade goods gained, spent, or lost; ammunition or charges expended; equipment damaged or acquired.
6. Table rulings: Record any explicit GM rulings, procedural interpretations, or custom naming conventions established during play.
7. Write strictly in British English spelling (e.g. armour, colour, categorised, synthesise).
8. Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
9. Output ONLY the complete Markdown document. Do not echo the glossary or transcript sections, and do not wrap in outer backticks.

Required Structure:
# Session Tactical Facts: <Evocative Session Title>

> [!NOTE]
> De-personalised tactical & chronological facts for `{campaign}`.
> Slug: `{slug}` | Recorded: `{recorded_date}` | Last Known Locus: `{last_locus}`

## 1. Chronological Timeline & Tactical Sequence

- [Beat 1] Detailed chronological entry...
- [Beat 2] Detailed chronological entry...

## 2. Combat Encounters & Tactical Decisions

- Adversaries encountered, tactical actions taken, weapons or tools used, and outcomes.

## 3. Physical Trauma, Wounds & Psychological Stress

- Detailed condition and tracker updates for each involved character.

## 4. Technical Hazards, Environmental Damage & Malfunctions

- Environmental perils, structural or equipment failures, and triggered hazards.

## 5. Economic Ledger: Loot, Cargo, Currency & Ammunition

- Precise currency or trade value gained/spent, consumables expended, and items acquired or lost.

## 6. Table Rulings & Candidate Canon Decisions

- Rulings, house rules, and custom conventions established at the table.

---
### Session Glossary:
{context.get('glossary', '')[:4000]}

---
### Active Decisions (Tier 2 Canon):
{context.get('decisions', '')[:2000]}

---
### Verbatim Session Transcript:
{context.get('transcript', '')}
"""


def build_sensory_prompt(manifest: Dict[str, Any], context: Dict[str, str]) -> str:
    """Construct the setting-agnostic Pass 2B sensory and environmental textures extraction prompt."""
    slug = manifest.get("session_slug", "unknown_session")
    campaign = manifest.get("campaign", "campaign")
    recorded_date, last_locus = resolve_session_metadata(manifest)
    genre = (manifest.get("campaign_defaults") or {}).get("genre")
    genre_line = f"\nCampaign Genre Context: {genre}" if genre else ""

    return f"""You are the sensory archivist and environmental scribe for '{campaign}'.{genre_line}
Extract vivid environmental textures, atmospheric details, in-character quotes, and physical actions from the provided raw session transcript.

Crucial Directives:
1. DE-PERSONALISATION MANDATE: Strip all out-of-character player banter, real-world comments, and meta-jokes. Preserve rich in-character roleplay, character mannerisms, and physical environment descriptions grounded strictly in what actually occurred in the transcript.
2. Lighting & visual palette: Capture illumination details, colours, visibility, weather, architecture, and shadow conditions described during play.
3. Acoustics & sounds: Capture ambient sounds, environmental acoustics, creature or machinery noises, echoes, and silences.
4. Odours & sensations: Capture olfactory, thermal, and tactile sensations experienced by the characters.
5. In-character dialogue: Capture memorable verbatim in-universe quotes (preserving the spoken language of the quote), voice inflections, and interpersonal tensions.
6. Tactile improvisations: Capture concrete physical interactions where characters improvised with surrounding terrain, structures, or tools. Do NOT invent examples not present in the transcript.
7. Write all analytical descriptions strictly in British English spelling (e.g. odour, colour, grey, oxidised, utilising).
8. Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
9. Output ONLY the complete Markdown document. Do not echo the glossary or transcript sections, and do not wrap in outer backticks.

Required Structure:
# Session Sensory & Environmental Textures: <Evocative Session Title>

> [!NOTE]
> De-personalised atmospheric & sensory textures for `{campaign}`.
> Slug: `{slug}` | Recorded: `{recorded_date}` | Last Known Locus: `{last_locus}`

## 1. Environmental Grime, Materials & Atmosphere

- Surface materials, spatial conditions, wear, weather, and physical atmosphere.

## 2. Lighting, Shadows & Visual Palette

- Illumination sources, colour tones, visibility, shadows, and darkness.

## 3. Acoustics, Ambient Sounds & Reverberation

- Auditory ambience, environmental or mechanical sounds, voices, and silence.

## 4. Smells, Tastes & Atmospheric Quality

- Odours, air quality, temperature shifts, and physical sensations.

## 5. In-Character Roleplay, Dialogue Quotes & Mannerisms

- Memorable in-character dialogue lines, physical expressions, and non-verbal tensions.

## 6. Environmental Improvisations & Tactile Solutions

- Spontaneous physical actions utilising surrounding terrain, structures, or equipment.

---
### Session Glossary:
{context.get('glossary', '')[:4000]}

---
### Verbatim Session Transcript:
{context.get('transcript', '')}
"""


def extract_tactical_facts(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
    keep_alive: str = "15m",
) -> str:
    """
    Pass 2A: Prompt local Ollama model to extract chronological and tactical facts.
    Strictly de-personalises the transcript by stripping player banter and real-world names.
    Outputs structured Markdown saved to _gm-materials/session-summaries/<slug>_tactical_facts.md.
    """
    prompt = build_tactical_prompt(manifest, context)
    raw_facts = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.2,
        keep_alive=keep_alive,
        stop=OLLAMA_STOP_SEQUENCES,
        log_prefix="    [Tactical Facts 2A] ",
    )
    clean_facts = strip_prompt_echo(raw_facts, pass_label="Pass 2A tactical facts")
    return enforce_markdown_cleanliness(clean_facts)


def extract_sensory_textures(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
    keep_alive: str = "15m",
) -> str:
    """
    Pass 2B: Prompt local Ollama model to extract evocative sensory and atmospheric textures.
    Strictly de-personalises the transcript by capturing in-character dialogue and physical descriptions.
    Outputs structured Markdown saved to _gm-materials/session-summaries/<slug>_sensory_textures.md.
    """
    prompt = build_sensory_prompt(manifest, context)
    raw_textures = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.3,
        keep_alive=keep_alive,
        stop=OLLAMA_STOP_SEQUENCES,
        log_prefix="    [Sensory Textures 2B] ",
    )
    clean_textures = strip_prompt_echo(raw_textures, pass_label="Pass 2B sensory textures")
    return enforce_markdown_cleanliness(clean_textures)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Air-gapped local session audio transcriber and two-pass notes extractor for campaign vaults."
    )
    parser.add_argument(
        "input_file",
        nargs="?",
        default=None,
        help="Path to session audio/video recording (.mkv, .mp4, .wav, etc.) or pre-transcribed text file (.txt). Auto-discovers latest file in air-gap if omitted.",
    )
    parser.add_argument("--repo-root", help="Explicit path to campaign repository root.")
    parser.add_argument("--session-slug", help="Custom session slug (e.g. 2026-11-01_003 or 2026-11-01_003_pilot).")
    parser.add_argument("--airgap-dir", help="Override local air-gap storage directory (default: ~/Private/rpg-sessions/<campaign>).")
    parser.add_argument("--model", help="Explicit Ollama model override for all extraction passes (default: qwen2.5:14b).")
    parser.add_argument("--model-tactical", help="Explicit Ollama model override for Pass 2A tactical facts (default: qwen2.5:14b).")
    parser.add_argument("--model-sensory", help="Explicit Ollama model override for Pass 2B sensory textures (default: qwen2.5:14b).")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--skip-transcribe", action="store_true", help="Skip Whisper acoustic transcription and reuse existing transcript.")
    parser.add_argument("--language", help="Whisper language code override (e.g. 'en', 'pt').")
    parser.add_argument("--dry-run", action="store_true", help="Perform extraction without writing output files.")
    parser.add_argument("--keep-alive", default="15m", help="Ollama model keep-alive duration (default: 15m).")

    args = parser.parse_args()

    repo_root = find_campaign_root(args.repo_root)
    input_file = Path(args.input_file).expanduser().resolve() if args.input_file else None

    start_time = time.time()
    print("=" * 70)
    print("OUDE MECHANISMEN — AIR-GAPPED SESSION NOTES EXTRACTOR")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Campaign:  {repo_root.name}")
    print(f"Input:     {input_file.name if input_file else '(auto-discover from air-gap)'}")
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
        session_slug=args.session_slug,
    )

    context = read_context_files(repo_root, manifest)
    if not context["transcript"]:
        print(f"Error: Verbatim transcript at '{manifest['transcript_path']}' is missing or empty.", file=sys.stderr)
        sys.exit(1)

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
        keep_alive=args.keep_alive,
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
        keep_alive=args.keep_alive,
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
    print(f"Tactical Facts:  {manifest['tactical_facts_path']} (Tier 2 _gm-materials/session-summaries/)")
    print(f"Sensory Textures:{manifest['sensory_textures_path']} (Tier 2 _gm-materials/session-summaries/)")
    print("\nAir-gap privacy boundary cleared.")
    print("Ready for Gemini in Antigravity chat to merge notes and draft chapter prose.")
    print("=" * 70)


if __name__ == "__main__":
    main()
