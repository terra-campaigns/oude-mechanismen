#!/usr/bin/env python3
"""
Fully local, setting-aware session notes orchestrator for tabletop RPG campaign vaults.

Pipeline stages handled:
- Stage 0: Pre-flight repository reconnaissance (Git status, chapter collisions, prep detection, catalogue health).
- Stage 1: Acoustic audio transcription via Metal GPU Whisper (whisper-cli) with dynamic glossary bias into local disk air-gap (~/Private/rpg-sessions/<campaign>/).
- Stage 2: Decomposed local two-pass extraction via Ollama:
  - Pass 2A: Chronological & tactical facts (<slug>_tactical_facts.md in Google Drive _sessions/).
  - Pass 2B: Sensory & environmental textures (<slug>_sensory_textures.md in Google Drive _sessions/).
- Stage 3: Local notes merge (optional fallback) or handoff to Gemini in Antigravity chat for Objective In-World Observer synthesis and chapter drafting.
- Stage 4: Campaign-parameterised character condition reconciliation in character YAML front matter.

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

import yaml


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
            # Check if next line is not blank
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                cleaned.append("")
    return "\n".join(cleaned).strip() + "\n"


def stage_0_recon(
    repo_root: Path,
    force: bool = False,
    campaign_defaults: Optional[Dict[str, Any]] = None,
    next_chapter_info: Optional[Dict[str, Any]] = None,
    drive_dir: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Perform Stage 0 pre-flight repository reconnaissance.
    Inspects:
    1. Active Git branch (git branch --show-current).
    2. Working tree cleanliness (git status --short).
    3. Target chapter numbering and collision check.
    4. Pending prep notes in Drive (_sessions/*_prep.md) or campaign subfolder.
    5. Catalogue index freshness and validity (.agents/context/catalog.json).
    """
    # 1. Git branch
    res_b = subprocess.run(["git", "branch", "--show-current"], cwd=repo_root, capture_output=True, text=True)
    branch = res_b.stdout.strip() if res_b.returncode == 0 and res_b.stdout.strip() else "detached/unknown"

    # 2. Git working tree status
    res_s = subprocess.run(["git", "status", "--short"], cwd=repo_root, capture_output=True, text=True)
    dirty_files = [line.strip() for line in res_s.stdout.splitlines() if line.strip()]
    is_clean = len(dirty_files) == 0

    is_blocked = False
    block_reason = ""

    if not is_clean and not force:
        # Check if uncommitted files are in content directories
        campaign_sub = (campaign_defaults or {}).get("campaign_subfolder", "campaigns")
        content_dirty = [f for f in dirty_files if any(p in f for p in [campaign_sub, "directory", "systems"])]
        if content_dirty:
            is_blocked = True
            block_reason = f"Uncommitted changes detected in campaign content ({len(content_dirty)} files). Use --force to proceed."
        else:
            is_blocked = True
            block_reason = f"Working tree has {len(dirty_files)} uncommitted modifications. Commit, stash, or pass --force to proceed."

    # 3. Target chapter numbering collision check
    target_rel_path = ""
    collision_detected = False
    collision_status = "Clean (No collision)"

    if next_chapter_info:
        target_rel_path = next_chapter_info.get("next_chapter_file", "")
    elif campaign_defaults:
        subfolder = repo_root / campaign_defaults.get("campaign_subfolder", "campaigns")
        if subfolder.exists():
            existing = sorted(list(subfolder.glob("*.md")))
            target_rel_path = f"{campaign_defaults.get('campaign_subfolder', 'campaigns')}/next.md"

    if target_rel_path:
        target_full_path = repo_root / target_rel_path
        if target_full_path.exists() and target_full_path.stat().st_size > 0:
            collision_detected = True
            collision_status = f"COLLISION DETECTED ({target_full_path.name} already exists on disk)"
            if not force:
                is_blocked = True
                block_reason = f"Target chapter file already exists: {target_rel_path}. Use --force to overwrite."

    # 4. Pending prep notes
    pending_prep = "None detected"
    if drive_dir:
        prep_files = list((drive_dir / "_sessions").glob("*_prep.md"))
        if prep_files:
            latest_prep = max(prep_files, key=lambda f: f.stat().st_mtime)
            pending_prep = str(latest_prep.name)
    if pending_prep == "None detected":
        subfolder_p = repo_root / (campaign_defaults or {}).get("campaign_subfolder", "campaigns")
        if subfolder_p.exists():
            local_preps = list(subfolder_p.glob("prep_*.md"))
            if local_preps:
                pending_prep = str(local_preps[0].name)

    # 5. Catalogue freshness
    cat_path = repo_root / ".agents" / "context" / "catalog.json"
    if cat_path.exists():
        try:
            cat_data = json.loads(cat_path.read_text(encoding="utf-8"))
            cat_status = f"catalog.json valid ({len(cat_data)} entries)"
        except Exception:
            cat_status = "catalog.json malformed"
    else:
        cat_status = "catalog.json missing"

    # Status verdict
    verdict = "GREEN — Pre-flight baseline ready" if not is_blocked else f"BLOCKED: {block_reason}"

    # Print 5-line Pre-Flight Reconnaissance Card
    print("=" * 70)
    print("STAGE 0: PRE-FLIGHT REPOSITORY RECONNAISSANCE")
    print("=" * 70)
    print(f"Branch:         {branch} ({'Clean' if is_clean else f'Dirty: {len(dirty_files)} uncommitted files'})")
    print(f"Target Chapter: {target_rel_path or 'Unresolved'} ({collision_status})")
    print(f"Pending Prep:   {pending_prep}")
    print(f"Catalogue:      {cat_status}")
    print(f"Pre-Flight:     {verdict}")
    print("=" * 70)

    recon_summary: Dict[str, Any] = {
        "branch": branch,
        "is_clean": is_clean,
        "dirty_files": dirty_files,
        "target_chapter": target_rel_path,
        "collision_detected": collision_detected,
        "pending_prep": pending_prep,
        "catalogue_status": cat_status,
        "is_blocked": is_blocked,
        "block_reason": block_reason,
    }

    if is_blocked and not force:
        raise RuntimeError(f"Stage 0 Reconnaissance Blocked: {block_reason}")

    return recon_summary


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
    default_model: str = "qwen2.5:14b",
) -> str:
    """Determine which local Ollama model to use for extraction."""
    if explicit_model:
        return explicit_model
    return default_model


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
    region = next_info.get("previous_region") or manifest["campaign_defaults"].get("location_key", "Unknown Region")
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
    region = next_info.get("previous_region") or manifest["campaign_defaults"].get("location_key", "Unknown Region")
    date_str = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    prompt = f"""You are the sensory archivist and environmental scribe for '{campaign}'.
Extract vivid environmental textures, atmospheric grit, in-character quotes, and physical details from the provided raw session transcript.

Crucial Directives:
1. DE-PERSONALISATION MANDATE: Strip all out-of-character player banter, real-world comments, and meta-jokes. Preserve rich in-character roleplay, character mannerisms, and physical environment descriptions.
2. Lighting & visual palette: Capture illumination details (e.g. flickering dying fluorescent tubes, dim amber CRT phosphor, blinding void glare, emergency strobes).
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
### Campaign Tone & Calibration:
{context['agents_instructions'][:2000]}

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


def synthesise_archival_notes(
    ollama_url: str,
    model: str,
    manifest: Dict[str, Any],
    context: Dict[str, str],
    tactical_facts: Optional[str] = None,
    sensory_textures: Optional[str] = None,
) -> str:
    """
    Prompt local model to synthesise the 8 canonical GM archival notes sections.
    Narrated from the Objective In-World Observer perspective (zero player meta-talk).
    Can ingest prior tactical facts (2A) and sensory textures (2B) when available.
    """
    slug = manifest["session_slug"]
    campaign = manifest["campaign"]
    next_info = manifest.get("next_chapter_info", {})
    region = next_info.get("previous_region") or manifest["campaign_defaults"].get("location_key", "Unknown Region")
    date_str = next_info.get("previous_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")

    synthesis_source = ""
    if tactical_facts and sensory_textures:
        synthesis_source = f"""### De-personalised Tactical Facts (Pass 2A):
{tactical_facts}

---
### De-personalised Sensory Textures (Pass 2B):
{sensory_textures}"""
    else:
        synthesis_source = f"""### Verbatim Session Transcript:
{context['transcript']}"""

    prompt = f"""You are the campaign archivist for '{campaign}'.
Synthesise the provided session materials into comprehensive, authoritative archival GM session notes.

Perspective & Cadence Directive:
- OBJECTIVE IN-WORLD OBSERVER: Narrate strictly from the viewpoint of an invisible, objective in-world observer witnessing events within the universe.
- ZERO PLAYER META-TALK: Strip all out-of-character chatter, player real names, rules banter, and table jokes.
- NO BOXED READ-ALOUD TEXT: Never format boxed descriptive text (> Table Read-Aloud) or conversational monologues.
- Reconcile phonetic spelling errors using the provided glossary.
- Write strictly in British English spelling (e.g. colour, flavour, categorised, synthesise).
- Leave an empty blank line immediately following EVERY Markdown heading (#, ##, ###).
- Output ONLY the complete Markdown document. Do not wrap in outer backticks or conversational chatter.

Required Structure:
# Session Notes: <Evocative Session Title>

> [!NOTE]
> Synthesised from session records for `{campaign}`.
> Slug: `{slug}` | Date: `{date_str}` | Location: `{region}`

## 1. Executive Summary
A punchy title and 2–3 sentence executive recap of the session's major events and consequences.

## 2. Chronological Plot Beats
Detailed bullet points of key decisions, scenes, travels, and revelations in chronological order, integrating concrete sensory anchors.

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
{synthesis_source}
"""
    raw_notes = query_ollama_stream(
        ollama_url,
        model,
        prompt,
        temperature=0.25,
        log_prefix="    [Archival Notes 2C] ",
    )
    return enforce_markdown_cleanliness(raw_notes)


def update_character_front_matter(
    character_file: Path,
    new_conditions: Optional[List[str]] = None,
    cleared_conditions: Optional[List[str]] = None,
    tracker_updates: Optional[Dict[str, Any]] = None,
    dry_run: bool = False,
) -> Tuple[bool, str]:
    """
    Surgically update a character dossier's YAML front matter.
    Preserves comments and markdown body text below the second '---'.
    """
    if not character_file.exists():
        return False, f"File not found: {character_file}"

    text = character_file.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return False, f"File does not have YAML front matter: {character_file}"

    parts = text.split("---", 2)
    if len(parts) < 3:
        return False, f"Could not locate closing front matter delimiter: {character_file}"

    fm_raw = parts[1]
    body = parts[2]

    try:
        fm = yaml.safe_load(fm_raw) or {}
    except Exception as e:
        return False, f"Failed to parse front matter YAML: {e}"

    modified = False
    diffs: List[str] = []

    # 1. Update conditions list
    current_conditions = fm.get("conditions")
    if current_conditions is None:
        current_conditions = []
    elif isinstance(current_conditions, str):
        current_conditions = [current_conditions]
    elif not isinstance(current_conditions, list):
        current_conditions = list(current_conditions)

    if new_conditions:
        for cond in new_conditions:
            cond_clean = cond.strip()
            if cond_clean and not any(cond_clean.lower() == existing.lower() for existing in current_conditions):
                current_conditions.append(cond_clean)
                modified = True
                diffs.append(f"+ condition: {cond_clean}")

    if cleared_conditions:
        cleared_lower = [c.strip().lower() for c in cleared_conditions if c.strip()]
        new_list = [c for c in current_conditions if c.strip().lower() not in cleared_lower]
        if len(new_list) != len(current_conditions):
            removed = [c for c in current_conditions if c.strip().lower() in cleared_lower]
            current_conditions = new_list
            modified = True
            for r in removed:
                diffs.append(f"- condition: {r}")

    if modified or "conditions" in fm:
        fm["conditions"] = current_conditions

    # 2. Update tracker updates (e.g. stress, bends, charge, status)
    if tracker_updates:
        for k, v in tracker_updates.items():
            if fm.get(k) != v:
                old_v = fm.get(k)
                fm[k] = v
                modified = True
                diffs.append(f"~ {k}: {old_v} -> {v}")

    if not modified:
        return False, "No modifications needed."

    new_fm_yaml = yaml.dump(fm, sort_keys=False, allow_unicode=True, default_flow_style=False).strip()
    new_text = f"---\n{new_fm_yaml}\n---{body}"

    if not dry_run:
        character_file.write_text(new_text, encoding="utf-8")

    diff_summary = f"{character_file.name}:\n  " + "\n  ".join(diffs)
    return True, diff_summary


def reconcile_character_conditions(
    repo_root: Path,
    notes_or_facts_text: str,
    character_updates: Optional[List[Dict[str, Any]]] = None,
    dry_run: bool = False,
) -> List[Dict[str, Any]]:
    """
    Reconcile character conditions and declared state trackers across character files in directory/.
    Accepts explicit character_updates or parses bullet points matching character titles.
    """
    results: List[Dict[str, Any]] = []
    directory_root = repo_root / "directory"
    if not directory_root.exists():
        return results

    # Discover known character dossiers
    character_map: Dict[str, Path] = {}
    for md_path in directory_root.rglob("*.md"):
        if md_path.name == "index.md":
            continue
        try:
            content = md_path.read_text(encoding="utf-8", errors="ignore")
            if content.startswith("---"):
                parts = content.split("---", 2)
                fm = yaml.safe_load(parts[1]) or {}
                name = fm.get("title") or md_path.stem
                character_map[name.lower()] = md_path
        except Exception:
            continue

    if not character_updates:
        # Simple extraction parser over text: looks for lines matching '- <Name>: <Condition / Updates>'
        character_updates = []
        for line in notes_or_facts_text.splitlines():
            line_str = line.strip()
            m = re.match(r"^[-*]\s*([A-Za-z0-9_]+)\s*:\s*(.+)$", line_str)
            if m:
                name_candidate = m.group(1).strip()
                desc = m.group(2).strip()
                if name_candidate.lower() in character_map:
                    character_updates.append({
                        "name": name_candidate,
                        "new_conditions": [desc],
                        "tracker_updates": {},
                    })

    for update in character_updates:
        name = update.get("name", "").strip().lower()
        if name in character_map:
            char_file = character_map[name]
            changed, diff_summary = update_character_front_matter(
                char_file,
                new_conditions=update.get("new_conditions"),
                cleared_conditions=update.get("cleared_conditions"),
                tracker_updates=update.get("tracker_updates"),
                dry_run=dry_run,
            )
            results.append({
                "character": update.get("name"),
                "file": str(char_file.relative_to(repo_root)),
                "modified": changed,
                "diff": diff_summary,
            })

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Air-gapped local session notes orchestrator for tabletop RPG campaign vaults."
    )
    parser.add_argument("input_file", help="Path to session audio/video recording (.mkv, .mp4, .wav, etc.) or pre-transcribed text file (.txt).")
    parser.add_argument("--repo-root", help="Explicit path to campaign repository root.")
    parser.add_argument("--airgap-dir", help="Override local air-gap storage directory (default: ~/Private/rpg-sessions/<campaign>).")
    parser.add_argument("--model", help="Explicit Ollama model override for all passes (default: qwen2.5:14b).")
    parser.add_argument("--model-tactical", help="Explicit Ollama model override for Pass 2A tactical facts (default: qwen2.5:14b).")
    parser.add_argument("--model-sensory", help="Explicit Ollama model override for Pass 2B sensory textures (default: mistral-nemo:12b or qwen2.5:14b).")
    parser.add_argument("--ollama-url", default="http://localhost:11434", help="Ollama API base URL (default: http://localhost:11434).")
    parser.add_argument("--skip-transcribe", action="store_true", help="Skip Whisper acoustic transcription and reuse existing transcript.")
    parser.add_argument("--language", help="Whisper language code override (e.g. 'en', 'pt').")
    parser.add_argument("--stage", choices=["0", "1", "2", "3", "4", "all"], default="all", help="Execute specific pipeline stage only.")
    parser.add_argument("--force", action="store_true", help="Bypass Stage 0 Git working tree and chapter collision blocking warnings.")
    parser.add_argument("--merge-notes", action="store_true", help="Execute local 8-section notes synthesis (Pass 2C fallback) after two-pass extraction.")
    parser.add_argument("--reconcile", action="store_true", help="Execute character conditions reconciliation on directory/ character front matter.")
    parser.add_argument("--dry-run", action="store_true", help="Perform synthesis without writing output files.")
    parser.add_argument("--keep-alive", default="15m", help="Ollama model keep-alive duration (default: 15m).")

    args = parser.parse_args()

    repo_root = find_campaign_root(args.repo_root)
    input_file = Path(args.input_file).resolve()

    start_time = time.time()
    print("=" * 70)
    print("OUDE MECHANISMEN — AIR-GAPPED SESSION SCRIBING ENGINE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print(f"Campaign:  {repo_root.name}")
    print(f"Input:     {input_file.name}")
    print("=" * 70)

    # 1. Stage 0: Pre-Flight Repository Reconnaissance
    print("\n==> [Stage 0] Performing Pre-Flight Repository Reconnaissance...")
    recon = stage_0_recon(repo_root, force=args.force)
    if args.stage == "0":
        print("\nStage 0 Pre-Flight Reconnaissance completed.")
        sys.exit(0)

    # 2. Verify Ollama accessibility if running Stage 2 or 3
    if args.stage in ["2", "3", "all"]:
        if not check_ollama_status(args.ollama_url):
            print(f"Error: Local Ollama daemon is not responding at {args.ollama_url}.", file=sys.stderr)
            print("Please ensure Ollama is running (`brew services start ollama` or `ollama serve`).", file=sys.stderr)
            sys.exit(1)

    # 3. Stage 1: Acoustic Transcription & Manifest Extraction
    print("\n==> [Stage 1] Running acoustic transcription and context discovery...")
    manifest = run_acoustic_pipeline(
        repo_root,
        input_file,
        skip_transcribe=args.skip_transcribe or (args.stage not in ["1", "all"]),
        language=args.language,
        airgap_dir=args.airgap_dir,
    )
    if args.stage == "1":
        print("\nStage 1 Acoustic Transcription completed.")
        sys.exit(0)

    # Ingest context
    context = read_context_files(repo_root, manifest)
    tactical_model = args.model_tactical or args.model or "qwen2.5:14b"
    sensory_model = args.model_sensory or args.model or "qwen2.5:14b"

    tactical_facts_text = ""
    sensory_textures_text = ""

    # 4. Stage 2: Decomposed Two-Pass Extraction (Pass 2A & Pass 2B)
    if args.stage in ["2", "all"]:
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

    # 5. Stage 3 (Optional Local Notes Merge): Combine 2A + 2B locally into 8-section notes
    notes_path = Path(manifest["session_notes_path"])
    if args.merge_notes or args.stage == "3":
        print(f"\n==> [Stage 3] Synthesising Archival GM Session Notes (Local Merge)...")
        notes_markdown = synthesise_archival_notes(
            args.ollama_url,
            tactical_model,
            manifest,
            context,
            tactical_facts=tactical_facts_text or None,
            sensory_textures=sensory_textures_text or None,
        )
        if not args.dry_run:
            notes_path.parent.mkdir(parents=True, exist_ok=True)
            notes_path.write_text(notes_markdown, encoding="utf-8")
            print(f"    [Saved] {notes_path} ({len(notes_markdown.split())} words)")
        else:
            print(f"    [Dry-Run] Skipped writing {notes_path}")

    # 6. Stage 4: Character Conditions Reconciliation
    if args.reconcile or args.stage == "4":
        print("\n==> [Stage 4] Reconciling Character Conditions in directory/ YAML front matter...")
        recon_input = tactical_facts_text or context["transcript"]
        reconciled = reconcile_character_conditions(repo_root, recon_input, dry_run=args.dry_run)
        if reconciled:
            for item in reconciled:
                if item["modified"]:
                    print(f"    [Updated] {item['file']}:\n      {item['diff']}")
                else:
                    print(f"    [Unchanged] {item['file']}")
        else:
            print("    No condition updates identified.")

    elapsed = time.time() - start_time
    print("\n" + "=" * 70)
    print("SESSION SCRIBING PIPELINE STAGE COMPLETE")
    print(f"Elapsed Time:    {elapsed / 60:.1f} minutes")
    print(f"Tier 0 Air-Gap:  {manifest['transcript_path']}")
    print(f"Tactical Facts:  {manifest['tactical_facts_path']} (Tier 2 Drive)")
    print(f"Sensory Textures:{manifest['sensory_textures_path']} (Tier 2 Drive)")
    if args.merge_notes:
        print(f"GM Notes:        {notes_path} (Tier 2 Drive)")
    print("\nAir-gap privacy boundary cleared.")
    print("Ready for Gemini in Antigravity chat to merge notes (Pass 2C) and draft chapter (Pass 3).")
    print("=" * 70)


if __name__ == "__main__":
    main()
