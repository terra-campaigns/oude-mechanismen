---
name: scribe-session
description: Decomposed, air-gapped transcription and synthesis workflow. Ingests raw session recordings (.mkv, .mp4, .wav) or transcripts, transcribes via local Metal GPU Whisper into local air-gap, extracts de-personalised tactical facts (Pass 2A) and sensory textures (Pass 2B) via local Ollama into Google Drive, synthesises canonical 8-section GM notes via Gemini chat (Pass 2C, Objective In-World Observer), drafts canonical chapter prose (Pass 3, 2-4 rule, sentence-per-line), and reconciles character front-matter conditions.
argument-hint: path to session audio/video file or existing transcript (.txt)
---

# Scribe Session

An air-gapped, decomposed pipeline to process a tabletop RPG session recording into canonical campaign documentation. It executes local Metal GPU speech-to-text with setting-aware glossary prompting, produces de-personalised tactical facts and sensory textures via local Ollama into Google Drive, merges them into authoritative 8-section archival GM notes via Gemini in chat, drafts calibrated in-voice chapter prose, and reconciles character conditions.

## Guiding Principles

- **Zero-Friction Ingestion:** Accepts any standard audio or video container (`.mkv`, `.mp4`, `.m4a`, `.wav`, `.mp3`) or pre-transcribed `.txt` file.
- **Dynamic Canon Grounding:** Dynamically queries `.agents/context/catalog.json`, `.agents/context/decisions.md`, and `.agents/AGENTS.md` to bias Whisper acoustic recognition and eliminate phonetic misspellings without manual glossary maintenance.
- **Three-Tier Storage Separation & Privacy Air-Gap:**
  1. *Tier 0 (Local Disk Air-Gap):* Raw audio recordings and verbatim speech transcripts reside strictly on local disk at `~/Private/rpg-sessions/<campaign>/`, completely excluded from both Git and Google Drive for player privacy.
  2. *Tier 2 Canon (`<drive_dir>/_gm-materials/session-summaries/` & `<drive_dir>/_gm-materials/session-preps/`):* De-personalised tactical facts (`<slug>_tactical_facts.md`), sensory textures (`<slug>_sensory_textures.md`), synthesised archival GM session notes (`<slug>_session_notes.md`), session prep (`_gm-materials/session-preps/<slug>_prep.md`), and acoustic glossaries (`<slug>_glossary.md`).
  3. *Tier 1 Canon (Campaign Repository):* Canonical draft chapter files (`campaigns/<arc>/<num>.md`) and character dossiers (`directory/`).
- **Gemini Chat Orchestration & Frontier Quality Gates:** The pipeline is kickstarted through Gemini chat (`scribe-session`). Gemini coordinates local execution, ingests clean de-personalised Tier 2 records, and drafts the canonical chapter and archival notes.
- **Objective In-World Observer Perspective:** All archival GM notes are narrated from the perspective of an invisible, objective in-world observer witnessing events within the universe. Zero player meta-talk, zero table out-of-character banter, zero boxed read-aloud prose.
- **The 2-4 Prose Architecture:** 2 to 4 subsections (`## Heading`), 2 to 4 paragraphs per subsection, 2 to 4 sentences per paragraph, and strictly **one sentence per line** within each paragraph.
- **Clear Local-vs-Cloud Division:** Local Python scripts (`transcribe_session.py` and `scribe_session.py`) deterministically manage Tier 0/Tier 2 storage paths, dynamic glossary compilation, and on-device de-personalisation, while Gemini in chat merges Tier 2 notes, authors canonical chapter scaffolding and prose, and reconciles character front-matter conditions.

---

## Workflow Procedure

### Step 1: Local Air-Gapped Transcription & Two-Pass Extraction

Execute the engine's local extraction command from the target campaign workspace:

```bash
oude scribe "<input_file>"
```

*(Or direct script fallback: `python3 "${OUDE_MECHANISMEN_DIR:-$HOME/Repos/oude-mechanismen}/scripts/scribe_session.py" "<input_file>"`).*

*(Note: If `<input_file>` is omitted, `oude scribe` automatically discovers the latest recording or transcript in `~/Private/rpg-sessions/<campaign>/`.)*

This local execution:
1. Normalises audio to 16 kHz mono WAV and transcribes via Apple Metal GPU Whisper (`whisper-cli`) using the dynamic proper-noun glossary prompt.
2. Saves the verbatim transcript strictly to `~/Private/rpg-sessions/<campaign>/<slug>_transcript.txt` (Tier 0 Air-Gap, never uploaded or ingested into cloud chat).
3. Compiles the session acoustic glossary in `<drive_dir>/_gm-materials/session-summaries/<slug>_glossary.md`.
4. **Pass 2A (Tactical Facts Extraction):** Local Ollama (`qwen2.5:14b`) extracts chronological timeline, combat actions, damage, mechanical rolls, sustained wounds/stress, and inventory/credits ledger -> saves `<drive_dir>/_gm-materials/session-summaries/<slug>_tactical_facts.md` (Tier 2 Canon, de-personalised).
5. **Pass 2B (Sensory Textures Extraction):** Local Ollama (`qwen2.5:14b`) extracts environmental grime, lighting, acoustics, smells, in-character quotes, and physical improvisations -> saves `<drive_dir>/_gm-materials/session-summaries/<slug>_sensory_textures.md` (Tier 2 Canon, de-personalised).

At completion, the privacy air-gap is cleanly cleared. Only de-personalised records land in `_gm-materials/session-summaries/`.

---

### Step 2: Ingest De-personalised Notes in Antigravity Chat

The Gemini agent in chat reads the non-Tier-0 materials from `<drive_dir>/_gm-materials/session-summaries/`:

1. **De-personalised Tactical Facts:** Read `<drive_dir>/_gm-materials/session-summaries/<slug>_tactical_facts.md`.
2. **De-personalised Sensory Textures:** Read `<drive_dir>/_gm-materials/session-summaries/<slug>_sensory_textures.md`.
3. **Session Acoustic Glossary:** Read `<drive_dir>/_gm-materials/session-summaries/<slug>_glossary.md`.
4. **Active Table Decisions (Tier 2):** Read `.agents/context/decisions.md`.
5. **Campaign Specification:** Inspect `.agents/AGENTS.md` for style, cadence, vocabulary, and calibration examples.
6. **Past Chapter Files:** Inspect the past 2–3 chapters (or as many as needed) to ground voice, style calibration, calendar progression, and narrative continuity.

---

### Step 3: Archival GM Notes Synthesis (Pass 2C & Frontier Quality Gate 1)

Gemini in chat merges Pass 2A and Pass 2B into the canonical **8-section Archival GM Notes**:

- **Perspective:** Objective In-World Observer (cool, clinical detachment; zero player meta-talk; zero table chatter).
- **Structure:**
  1. `# Session Notes: <Evocative Title>` with metadata banner (`slug`, `date`, `location`).
  2. `## 1. Executive Summary`: 2–3 sentence overview of major narrative events and consequences.
  3. `## 2. Chronological Plot Beats`: Comprehensive chronological timeline merging tactical sequence with sensory anchors and verbatim dialogue.
  4. `## 3. NPCs & Factions`: Entities encountered, attitude shifts, affiliation updates, cross-linked to `directory/`.
  5. `## 4. Quests, Contracts & Objectives`: Corporate/patron directives, debts incurred/repaid, milestones.
  6. `## 5. Combat, Hazards & Encounters`: Adversaries, tactical decisions, environmental hazards, sustained physical trauma and psychological stress.
  7. `## 6. Loot, Trade & Inventory Ledger`: Credits, salvage, ammunition expended, gear damaged/acquired.
  8. `## 7. Table Rulings & Candidate Tier 2 Decisions`: GM rulings and custom procedures to propose for `.agents/context/decisions.md`.
  9. `## 8. Unresolved Hooks & Next Steps`: Active cliffhangers and immediate player intentions.
- **Frontier Quality Gate 1:** Audit notes against previous sessions for continuity of ongoing debts and character states. Automated refinement loop (up to 3 iterations) if plot points or ledger entries are incomplete.
- **Save File:** Write finalised notes to `<drive_dir>/_gm-materials/session-summaries/<slug>_session_notes.md` (Tier 2).

---

### Step 4: Canonical Chapter Drafting (Pass 3 & Frontier Quality Gate 2)

Gemini in chat drafts the canonical chapter file at `campaigns/<subfolder>/<chapter>.md` based on the synthesised GM notes:

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

#### 3. Chapter Body & Cadence Invariants

- **The 2-4 Architectural Rule:**
  - 2 to 4 subsections (`## Heading`).
  - 2 to 4 paragraphs per subsection.
  - 2 to 4 sentences per paragraph.
  - **Sentence-per-line:** Every sentence placed on its own line (separated by single newlines) within each paragraph.
- **Markdown Spacing Rule:** Always leave an empty blank line immediately following any Markdown heading (`#`, `##`, `###`).
- **Tone & Cadence:** Derived strictly from `## Campaign Specification` (cadence, vocabulary, calibration examples) in the target campaign's `.agents/AGENTS.md`. Never hardcode setting-specific tropes.
- **Zero Boxed Read-Aloud Text:** Never generate boxed text (`> Table Read-Aloud`) or scripted GM monologues.
- **Entity Cross-Linking:** Embed relative Markdown links (`[Entity](../../directory/...)`) on first mention of catalogued entities.
- **Bilingual Mirror Translation (when configured):**
  - Primary language prose (e.g. Portuguese) drafted first adhering to the 2-4 rule.
  - Horizontal divider `---`.
  - British English mirror translation below `---`, strictly preserving the paragraph count and sentence-per-line cadence.
- **Frontier Quality Gate 2:** Mathematically audit heading count, paragraph counts, sentence counts, and relative link resolution. Up to 3 refinement iterations if cadence drifts.

---

### Step 5: Character Condition Reconciliation (Pass 4)

1. **Reconcile Character Dossiers:**
   Parse Section 5 (Combat, Hazards & Encounters) and Section 2 (Plot Beats) of the session notes for newly sustained wounds, trauma, and tracker updates.
2. **Surgically Update Front Matter:**
   Update character dossiers in `directory/<hub>/<character>.md`:
   - Updates `conditions:` list (appending non-duplicate conditions, removing cleared conditions).
   - Synchronises declared campaign markers (`stress`, `bends`, `charge`, `status`) in YAML front matter.
   - Leaves biographical markdown bodies, equipment tables, and notes completely untouched.
3. **Present Diff to GM:** Display the reconciled YAML conditions diff for confirmation.

---

### Step 6: Build Verification & Git Feature Branch Staging (Pass 5)

1. **Refresh Semantic Catalogue:**
   ```bash
   ruby --disable-gems _plugins/data_extractor.rb
   ```
2. **Verify Site Build:**
   ```bash
   bundle exec jekyll build
   ```
3. **Stage Feature Branch:**
   Checkout dedicated feature branch `efsalvarenga/session-<num>-<slug>`, stage modified chapter and character files, and present the completion dossier to the GM.
4. **Post-Merge & PR Closure Cleanup:**
   Once the pull request is merged (or closed) on GitHub:
   ```bash
   git checkout main && git pull
   git branch -d <feature-branch>
   git fetch --prune
   ```
   Never retain stale merged feature branches locally or on remote.
