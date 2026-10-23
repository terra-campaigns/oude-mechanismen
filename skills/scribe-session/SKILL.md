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
- **Storage Separation:** Audio recordings, transcripts, and GM notes reside in Google Drive, keeping the Git repository strictly for published Tier 1 Markdown.

---

## Workflow Procedure

### Step 1: Pre-Processing & Acoustic Transcription

Execute the shared orchestrator script from the campaign workspace:

```bash
python3 .agents/scripts/transcribe_session.py "<input_file>" --json
```

*(Note: Pre-transcribed `.txt` files are automatically detected and ingested without running audio transcription).*

Parse the resulting JSON manifest to capture:
- `session_slug`: Date and episode identifier (e.g. `2026-10-23_ep012`).
- `transcript_path`: Verbatim speech text in Google Drive (`_sessions/<slug>_transcript.txt`).
- `glossary_path`: Compiled campaign glossary in Google Drive (`_sessions/<slug>_glossary.md`).
- `session_notes_path`: Destination path for structured notes (`_sessions/<slug>_session_notes.md`).
- `campaign_defaults`: Naming pattern, timestamp format, and location key from `AGENTS.md`.
- `next_chapter_info`: Resolved next chapter filename (`next_filename`), path (`next_chapter_path`), previous date, and continuity anchor.

---

### Step 2: Context Loading

Before synthesising prose, read the following context:

1. **Campaign Voice & Conventions:** Inspect `.agents/AGENTS.md` for `## Campaign Specification` (genre, cadence, vocabulary, and calibration examples).
2. **Active Table Rulings:** Inspect `.agents/context/decisions.md`.
3. **Session Glossary:** Inspect the generated `<glossary_path>` for catalogued PCs, recurring NPCs, gazetteer locations, and factions.
4. **Previous Chapter File:** Inspect `next_chapter_info["previous_chapter_file"]` to establish immediate narrative continuity, parentage, and calendar progression.
5. **Verbatim Transcript:** Read `<transcript_path>`.

---

### Step 3: Deliverable 1 — Archival GM Session Notes

Synthesise the raw transcript into comprehensive structured notes, written to `<session_notes_path>` in Google Drive:

- Strip out-of-character table banter, dice maths, and rules debates.
- Reconcile phonetic spelling errors using the glossary (e.g. distinguishing character names from common nouns).
- Write in **British English**, ensuring an empty blank line immediately follows every Markdown heading.

Structure the document with these exact 8 sections:

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

### Step 4: Deliverable 2 — Canonical Draft Chapter

Draft the official in-voice chapter file at `next_chapter_info["next_chapter_path"]` (e.g. `campaigns/<Campaign>/ep_012.md` or `005.md`):

#### 1. YAML Front Matter

Use the exact keys established for the campaign:

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

### Step 5: Verification & Catalogue Refresh

1. Refresh the Tier 1 semantic catalogue:
   ```bash
   ruby --disable-gems _plugins/data_extractor.rb
   ```
2. Verify that all relative links resolve to existing files.
3. Leave all created files unstaged in Git for user review.
4. Present a concise summary to the user:
   - Link to the Google Drive session notes (`_session_notes.md`).
   - Link to the repository draft chapter (`<chapter>.md`).
   - Highlight any newly discovered NPCs or locations (suggesting `add-character` for creation).
   - Highlight any candidate Tier 2 rulings (suggesting review for `.agents/context/decisions.md`).
