# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **Three-Tier Storage Separation & Privacy Air-Gap**:
  - Implemented local disk air-gap resolution (`~/Private/rpg-sessions/<campaign>/`) in `scripts/transcribe_session.py` and `scripts/scribe_session.py`, completely excluding raw table audio and verbatim speech transcripts from Git and Google Drive for player privacy.
  - Formalised Google Drive `<drive_dir>/_sessions/` (`<slug>_session_notes.md`, `<slug>_prep.md`, `<slug>_glossary.md`) as active Tier 2 Canon across `AGENTS.md`, `templates/AGENTS.md.template`, and `skills/lookup-context/SKILL.md`.
  - Added `--airgap-dir` CLI override and `RPG_SESSIONS_DIR` environment variable support.
  - Added automated unit and integration test suite in `tests/test_transcribe_session.py`.

- **Stage 0 Pre-Flight Repository Reconnaissance**:
  - Implemented empirical pre-flight check in `scripts/scribe_session.py` (`stage_0_recon()`) and `skills/scribe-session/SKILL.md` (Step 0) inspecting Git branch, working tree status (`git status --short`), chapter numbering collision detection, pending prep discovery, and catalogue index validation.
  - Added `--force` bypass flag for dirty working tree overrides.

- **Decomposed Local Two-Pass Extraction (Pass 2A & Pass 2B)**:
  - Decomposed Ollama extraction over Tier 0 transcripts into Pass 2A (tactical facts, combat actions, damage, mechanical rolls, wounds, and economy ledger) and Pass 2B (sensory textures, environmental grime, acoustics, lighting, odours, and in-character quotes).
  - Emitted `<slug>_tactical_facts.md` and `<slug>_sensory_textures.md` to Google Drive `_sessions/` in completely de-personalised Markdown, clearing the privacy air-gap for Gemini chat orchestration.

- **Objective In-World Observer Notes Synthesis (Pass 2C) & In-Voice Chapter Drafting (Pass 3)**:
  - Updated `skills/scribe-session/SKILL.md` to codify Gemini chat orchestration: merging de-personalised 2A and 2B files into canonical 8-section notes in Google Drive (`<slug>_session_notes.md`) under the Objective In-World Observer perspective (zero player meta-talk, zero boxed read-aloud prose).
  - Codified in-voice chapter drafting adhering to the **2-4 Framework** (2–4 headings, 2–4 paragraphs per heading, 2–4 sentences per paragraph, and one sentence per line) with Gene Wolfe anchor-and-veil cadence, 80/20 clarity-to-obscurity, and bilingual mirror translation.

- **Campaign-Parameterised Character Condition Reconciler (Pass 4)**:
  - Implemented `update_character_front_matter()` and `reconcile_character_conditions()` in `scripts/scribe_session.py` to surgically update `conditions:` lists and declared campaign state markers (e.g. `stress`, `bends`, `charge`, `status`) in `directory/` character YAML front matter, leaving markdown body text byte-for-byte untouched.
  - Documented tracker parameterisation in `templates/AGENTS.md.template`.

- **Unattended Local Model Benchmark Runner**:
  - Created standalone benchmark harness in `scripts/benchmark_models.py` evaluating candidate local models (Whisper and Ollama LLMs) across tokens/second, heading cleanliness, sentence-per-line cadence, 2-4 framework compliance, and glossary proper-noun recall.

- **Automated Unit Test Suite Expansion**:
  - Added 8 new unit tests in `tests/test_scribe_session.py` covering Stage 0 reconnaissance, markdown cleanliness enforcement, front matter surgical mutation, and benchmark evaluation metrics (13/13 tests passing across suite).

---

## [0.1.0] - 2026-10-25

### Added

- **Procedural Agent Skills**:
  - `lookup-context`: Progressive context retrieval across Tier 1 (published canon), Tier 2 (active rulings), and Tier 3 (reference digests).
  - `lint-wiki`: Automated structural health-checking for orphan pages, broken links, stubs, and catalogue health.
  - `review-style`: Setting tone, cadence, and vocabulary calibration checks based on `AGENTS.md`.
  - `add-chapter`: Canonical session log and chapter authoring with Dataview scaffolding and parent navigation.
  - `add-character`: Character dossier creation for PCs and NPCs with biographical prompts and directory linking.
  - `prep-session`: Guided 8-step GM session preparation procedure.
  - `weave-threads`: Strategic analysis connecting unresolved narrative threads, faction moves, and economic anomalies.
  - `scribe-session`: Single-pass acoustic transcription (Apple Metal GPU Whisper) and dual synthesis (Google Drive GM notes + in-voice chapter log).
  - `illustrate-entry`: Archival public-domain artwork curation, graphic-novel filtering, and interactive slider studio.

- **Jekyll Static Site Engine (`jekyll/`)**:
  - `_plugins/data_extractor.rb`: Native in-memory Jekyll generator compiling `.agents/context/catalog.json`, bidirectional backlinks, and image galleries.
  - `_plugins/llm_content.rb`: Plaintext and structured LLM context generator (`/all-content.html`).
  - `_includes/connected_to.html`: Auto-rendered responsive entity and location galleries with campaign-isolated badge caching.
  - `_includes/header_chapter.md`, `_includes/header_directories.md`, and `_includes/image_gallery.html`.

- **Tooling & Release Infrastructure**:
  - `sync.sh`: Multi-repo synchronisation engine supporting drift detection (`--check`), unified diffs (`--diff`), forced overwrite (`--force`), and new vault initialisation (`--init`).
  - `templates/jekyll/`: Starter Jekyll content templates (`index.md`, `directory/index.md`, `campaigns/index.md`, `systems/index.md`) scaffolded on `--init`.
  - Dynamic discovery path generation for `.agents/skills.json` ensuring seamless skill discovery regardless of clone location.
  - `bin/setup`: Idempotent environment bootstrapper setting up Python virtual environment, dependencies, Git hooks, and verifying catalogue compilation.
  - `resources/filter_studio.html`: Standalone interactive generative UI studio for real-time preset blending, inking, grain, and lens flare placement.
  - GitHub Actions CI workflow verifying Python, Ruby, and Shell script syntax, ShellCheck, and comprehensive Markdown heading spacing rules on push and pull requests.
