---
name: scribe-session
description: Single-pass end-to-end transcription and synthesis workflow. Ingests raw session recordings (.mkv, .mp4, .wav, .m4a) or verbatim transcripts, transcribes via local Metal GPU Whisper with dynamic glossary prompting, and synthesises both structured GM archival notes in Google Drive and a canonical in-voice draft chapter file in the campaign repository.
argument-hint: path to session audio/video file or existing transcript (.txt)
---

# Scribe Session

An automated, single-pass pipeline to process a tabletop RPG session recording into canonical campaign documentation. It executes local Metal GPU speech-to-text with setting-aware glossary prompting, produces comprehensive archival GM session notes in Google Drive, and drafts a fully linked, setting-voiced chapter file in the campaign repository.

## Guiding Principles

- **Zero-Friction Ingestion:** Accepts any standard audio or video container (`.mkv`, `.mp4`, `.m4a`, `.wav`, `.mp3`) or pre-transcribed `.txt` file.
- **Dynamic Canon Grounding:** Dynamically queries `.agents/context/catalog.json`, `.agents/context/decisions.md`, and `.agents/AGENTS.md` to bias Whisper acoustic recognition and eliminate phonetic misspellings without manual glossary maintenance.
- **Dual Deliverables:**
  1. *Archival GM Session Notes:* Stored in Google Drive (`<drive_dir>/_sessions/<slug>_session_notes.md`) containing exhaustive chronological beats, faction shifts, inventory/trade ledgers, and candidate Tier 2 rulings.
  2. *Canonical Draft Chapter:* Stored in the campaign repository (`campaigns/<Campaign>/<chapter>.md`) containing calibrated in-voice prose, canonical YAML front matter, Dataview/hub backlinks, and relative directory links.
- **Three-Tier Storage Separation & Privacy Air-Gap:**
  1. *Tier 0 (Local Disk Air-Gap):* Raw audio recordings and verbatim speech transcripts reside strictly on local disk at `~/Private/rpg-sessions/<campaign>/`, completely excluded from both Git and Google Drive for player privacy.
  2. *Tier 2 Canon (Google Drive `_sessions/`):* Synthesised archival GM session notes (`<slug>_session_notes.md`), session prep (`<slug>_prep.md`), and acoustic glossaries (`<slug>_glossary.md`).
  3. *Tier 1 Canon (Campaign Repository):* Canonical draft chapter files (`campaigns/<arc>/<num>.md`) and character dossiers (`directory/`).

---

## Workflow Procedure

### Step 1: Air-Gapped Acoustic Transcription & Notes Extraction (Local Run)

Execute the local orchestrator script from the campaign workspace:

```bash
python3 .agents/scripts/scribe_session.py "<input_file>"
```

*(Note: If `<input_file>` is omitted, the script automatically auto-discovers the latest recording or transcript in `~/Private/rpg-sessions/<campaign>/`).*

This local execution:
1. Normalises the audio and transcribes via local Metal GPU Whisper (`whisper-cli`).
2. Saves the verbatim transcript strictly to the local disk air-gap at `~/Private/rpg-sessions/<campaign>/<slug>_transcript.txt` (Tier 0, never sent to cloud APIs or Git).
3. Compiles the session acoustic glossary in Google Drive (`<drive_dir>/_sessions/<slug>_glossary.md`).
4. Uses local Ollama (`qwen2.5:14b` or `mistral-nemo:12b`) to synthesise the structured **8-section Archival GM Session Notes** in Google Drive at `<drive_dir>/_sessions/<slug>_session_notes.md` (Tier 2 Canon), completely stripped of player banter and table chatter.

---

### Step 2: Context Loading in Antigravity Chat

Once local notes extraction completes, the Gemini agent loads the clean, non-Tier-0 context to draft the chapter:

1. **Archival GM Notes (Tier 2 Canon):** Read `<drive_dir>/_sessions/<slug>_session_notes.md`. *(Notice: The raw transcript is never ingested into chat).*
2. **Campaign Specification:** Inspect `.agents/AGENTS.md` for voice, cadence (sentence-per-line), vocabulary, and calibration examples.
3. **Active Table Rulings:** Inspect `.agents/context/decisions.md`.
4. **Session Glossary:** Inspect `<drive_dir>/_sessions/<slug>_glossary.md` for catalogued entities and spelling anchors.
5. **Previous Chapter File:** Inspect the previous chapter file to establish immediate narrative continuity, parentage, and calendar progression.

---

### Step 3: Archival GM Notes Structure (Reference)

The local model synthesises the raw transcript into the canonical **8-section archival structure**:

```markdown
# Session Notes: <Session Title>

> [!NOTE]
> Synthesised from raw session recording for `<Campaign Name>`.
> Slug: `<session_slug>` | Date: `<In-universe date>` | Location: `<Location/Region>`

## 1. Executive Summary

A punchy title and 2–3 sentence executive recap of the session's major events.

## 2. Chronological Plot Beats

Detailed bullet points of key decisions, roleplay scenes, travels, and revelations in chronological order.

## 3. NPCs & Factions

- Characters encountered, noting disposition changes and world lore revealed.
- Mark existing entities with their directory link (e.g. `[Kur](../../directory/Atles/Kur.md)`).
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
```

---

### Step 4: Canonical Chapter Drafting (Gemini Orchestration)

Gemini crafts the official in-voice chapter file at `campaigns/<subfolder>/<chapter>.md` based on the synthesised GM notes:

#### 1. YAML Front Matter

```yaml
---
layout: default
type: session
nav_exclude: false

parent: <Exact title of the campaign index, matching previous chapter>
title: <Evocative Episode Title>
<location_key>: <Region or Location Name>
nav_order: <YYYY-MM-DD or formatted timestamp matching previous chapter progression>
narration: 
footer_content: 

images:

---
```

#### 2. Scaffolding & Comment Block

Immediately follow front matter with the standard Liquid include and hub link:

```markdown
{% include header_chapter.md %}
{% comment %}
`=map(this.images, (x) => "![im|200](" + x + ")")`
```dataview
LIST without ID "["+ title + "](" + regexreplace(file.path, ".md", "") + ")" + ", from " + regexreplace(file.folder, "^[^\/]*\/", "") FROM ([[]]) OR outgoing([[]]) WHERE file.path != this.file.path SORT file.folder DESC
```
---

- [index](<relative_path_to_campaign_hub_page>)

{% endcomment %}
```

#### 3. Chapter Body & Voice Constraints

- **2 to 4 Subheaders:** Structure into 2–4 themed subsections using `## Heading`.
- **Markdown Spacing Rule:** Always leave an empty blank line immediately following any Markdown heading (`#`, `##`, `###`).
- **2 to 4 Paragraphs per Subheader:** Each subsection must contain between 2 and 4 distinct paragraphs, separated by blank lines.
- **2 to 4 Sentences per Paragraph:** Each paragraph must contain between 2 and 4 sentences. Place each sentence on its own line (one sentence per line) where practical.
- **Entity Cross-Linking:** Embed relative Markdown links (`[Entity](../../directory/...)`) on the first significant mention of every catalogued PC, NPC, location, or faction.
- **Setting Voice:** Strictly adhere to the cadence, vocabulary, and calibration examples defined under `## Campaign Specification` in `.agents/AGENTS.md`.
- **Language & Bilingual Mode:** British English spelling throughout. If `Chapter Output Format:` in `.agents/AGENTS.md` is bilingual (e.g. Portuguese / British English), generate the Portuguese section first, preceded by `English version below` and `{: .text-delta .text-right}`, followed by a horizontal divider `---` and the British English mirror section. Archival GM session notes in Google Drive remain synthesised in British English.

---

### Step 5: Character Condition Reconciliation & Build Verification

1. **Reconcile Character Front Matter:**
   Parse Section 5 (Combat, Hazards & Encounters) and Section 2 (Plot Beats) of the GM notes. Surgically update character dossiers in `directory/` by modifying only the front matter (`conditions:` list, and campaign-specific markers like `stress`, `bends`, or `charge`), leaving markdown bodies untouched.
2. **Refresh Semantic Catalogue:**
   ```bash
   ruby --disable-gems _plugins/data_extractor.rb
   ```
3. **Verify Jekyll Site Build:**
   ```bash
   bundle exec jekyll build
   ```
4. **Present Verification Dossier to GM:**
   - Link to Google Drive session notes (`_session_notes.md`).
   - Link to draft chapter file (`<chapter>.md`).
   - Visual diff of modified character front matter.
   - Candidate Tier 2 rulings for GM approval.
