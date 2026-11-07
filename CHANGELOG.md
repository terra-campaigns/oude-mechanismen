# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

- **Deterministic Chapter Prose Architecture Linter (`scripts/lint_chapter.py`)**:
  - Implemented static verification of the **2-4 Framework** (2–4 headings, 2–4 paragraphs per heading, 2–4 sentences per paragraph, and one sentence per line cadence).
  - Built-in noise masking preserving exact line numbering across YAML front matter, Jekyll Liquid includes/comments, Obsidian Dataview blocks, and HTML comments.
  - Sentence boundary disambiguation supporting abbreviations (`e.g.`, `i.e.`, `Dr.`, `vs.`, military ranks), uppercase initials, decimals, and dialogue attributions (e.g. `"You unfixed me!" he says.`).
  - Dual parallel section support for bilingual campaigns (`English version below`, Portuguese on top, horizontal rule `---`, British English on bottom).
  - CLI output formats for human inspection (`--format text`) and agent consumption (`--format json`).
  - Added runner template `templates/runners/lint_chapter.py.template` and registered in `sync.sh`'s `MANAGED_FILES` array.

- **Mandatory 3-Gate Pre-Publishing Protocol (`skills/add-chapter/SKILL.md`)**:
  - Formalised three publication quality gates: Gate 1 (Prose Architecture via `scripts/lint_chapter.py`), Gate 2 (Tone & Voice Calibration via `review-style`), and Gate 3 (Wiki & Asset Integrity via `lint-wiki`).
  - Codified the standardised Pre-Publishing Readiness Scorecard for agent reporting.
  - Restricted full 3-Gate execution strictly to pre-PR drafting and pre-final-review checkpoints to prevent LLM token burn on routine intermediate commits.

- **Pre-Publishing Policy Invariants (`AGENTS.md` & `templates/AGENTS.md.template`)**:
  - Enshrined the operational invariant prohibiting agents from declaring publication readiness on the basis of Git, CI, or Jekyll build status alone without executing the 3-Gate Audit.

- **Automated Unit Test Suite (`tests/test_lint_chapter.py`)**:
  - Authored 10 unit tests covering compliant monolingual, compliant bilingual, heading violations, paragraph count violations, sentence count violations, inline cadence violations, noise masking line preservation, abbreviation disambiguation, and JSON serialisation.

### Removed

- **Legacy Interactive Filter Studio**:
  - Removed `skills/illustrate-entry/resources/filter_studio.html` and deleted the HTML generator block from `skills/illustrate-entry/scripts/art_filter.py`, simplifying image curation into a clean, 100% chat-native pair-programming workflow.
  - Rewrote Step 3 of `skills/illustrate-entry/SKILL.md` to focus on direct in-chat curated candidate showcase and selection.
  - Pruned obsolete filter studio references from `AGENTS.md` and `README.md`.

### Fixed

- **Session Slug Date Regex Boundary**:
  - Fixed regex in `scripts/scribe_session.py` (`resolve_session_metadata`) from `r"^(\d{4}-\d{2}-\d{2})\b"` to `r"^(\d{4}-\d{2}-\d{2})(?:[_\b]|$)"`, ensuring session slugs with underscore suffixes (`YYYY-MM-DD_NNN`) correctly extract the recording date across calendar days.

---

## [0.2.0] - 2026-11-05

### Added

- **Three-Tier Storage Separation & Privacy Air-Gap**:
  - Implemented local disk air-gap resolution (`~/Private/rpg-sessions/<campaign>/`) in `scripts/transcribe_session.py` and `scripts/scribe_session.py`, completely excluding raw table audio and verbatim speech transcripts from Git and Google Drive for player privacy.
  - Formalised Google Drive `<drive_dir>/_sessions/` (`<slug>_session_notes.md`, `<slug>_prep.md`, `<slug>_glossary.md`) as active Tier 2 Canon across `AGENTS.md`, `templates/AGENTS.md.template`, and `skills/lookup-context/SKILL.md`.
  - Added `--airgap-dir` CLI override and `RPG_SESSIONS_DIR` environment variable support.
  - Added automated unit and integration test suite in `tests/test_transcribe_session.py`.

- **Decomposed Local Two-Pass Extraction (Pass 2A & Pass 2B)**:
  - Decomposed Ollama extraction over Tier 0 transcripts in `scripts/scribe_session.py` into Pass 2A (tactical facts, combat actions, damage, mechanical rolls, wounds, and economy ledger) and Pass 2B (sensory textures, environmental grime, acoustics, lighting, odours, and in-character quotes).
  - Emitted `<slug>_tactical_facts.md` and `<slug>_sensory_textures.md` to Google Drive `_sessions/` in completely de-personalised Markdown, clearing the privacy air-gap for Gemini chat orchestration.

- **Objective In-World Observer Notes Synthesis (Pass 2C) & In-Voice Chapter Drafting (Pass 3)**:
  - Updated `skills/scribe-session/SKILL.md` to codify Gemini chat orchestration: merging de-personalised 2A and 2B files into canonical 8-section notes in Google Drive (`<slug>_session_notes.md`) under the Objective In-World Observer perspective (zero player meta-talk, zero boxed read-aloud prose).
  - Codified in-voice chapter drafting adhering to the **2-4 Framework** (2–4 headings, 2–4 paragraphs per heading, 2–4 sentences per paragraph, and one sentence per line) with tone and cadence derived strictly from the target campaign's `AGENTS.md`, supporting ingestion of multiple past chapters for continuity, and bilingual mirror translation.

- **Campaign-Parameterised Character Condition Reconciliation (Pass 4)**:
  - Codified character condition reconciliation as a dedicated chat skill step in `skills/scribe-session/SKILL.md` where Gemini surgically updates `conditions:` lists and declared campaign state markers (e.g. `stress`, `bends`, `charge`, `status`) in `directory/` character YAML front matter, leaving markdown body text byte-for-byte untouched.
  - Documented tracker parameterisation in `templates/AGENTS.md.template`.

- **Local Model Benchmark Runner & Empirical Evaluation**:
  - Authored empirical benchmark harness in `scripts/benchmark_models.py` evaluating candidate local Ollama models on actual session transcripts across Pass 2A and Pass 2B tokens/second and extraction throughput.
  - Completed side-by-side empirical benchmark of `qwen2.5:14b` vs `mistral-nemo:latest` across a 10,313-word multilingual session transcript. Selected `qwen2.5:14b` as the canonical default model for local extraction due to zero repetition loops and superior factual accuracy.

- **Automated Unit Test Suite & CI Execution**:
  - Expanded unit test suite in `tests/test_scribe_session.py` covering fence-aware markdown cleanliness, air-gap prompt-echo stripping, session metadata resolution, optional input auto-discovery, setting-agnostic British English prompts, and weighted benchmark reporting (14/14 tests passing across suite and wired into GitHub Actions CI).

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

[Unreleased]: https://github.com/terra-campaigns/oude-mechanismen/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/terra-campaigns/oude-mechanismen/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/terra-campaigns/oude-mechanismen/releases/tag/v0.1.0
