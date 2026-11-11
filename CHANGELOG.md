# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

---

## [0.5.1] - 2026-11-11

### Added

- **Self-Healing Diagnostics & Automated Vault Remediation (`oude doctor --fix`)**:
  - Enhanced `oude doctor` to inspect `_config.yml` for required `oude-mechanismen` plugin activation and report actionable warnings when missing.
  - Added detection of legacy engine files (`_plugins/data_extractor.rb`, `_plugins/llm_content.rb`, `.agents/venv`) left behind by pre-ADR 001/002 synchronization.
  - Added `--fix` flag to `oude doctor` providing automated remediation:
    - Automatically injects `- oude-mechanismen` under `plugins:` in `_config.yml`.
    - Prunes obsolete shadowing `_plugins/` files and empty `_plugins/` directory.
    - Prunes obsolete `.agents/venv` virtual environments.
    - Automatically triggers `bundle exec jekyll build` when `catalog.json` lacks engine version metadata.
  - Modernised `templates/bin/setup.template` to eliminate obsolete local engine repository searches and per-vault venv creation, streamlining to Bundler installation, Jekyll site compilation, and `oude doctor` diagnostics.
  - Added comprehensive automated unit test coverage in `tests/test_cli.py` for config detection, legacy plugin pruning, and automated catalogue regeneration.

### Added

- **Cross-Vault Python Tooling & Zero-Clone CLI Distribution via Astral `uv` (ADR 002)**:
  - Authored and formally proposed [ADR 002](docs/adr/002_python_cli_distribution_uv.md) establishing zero-clone engine distribution and decoupling procedural tooling from local repository clones.
  - Packaged `oude-mechanismen` with modern Python standards via `pyproject.toml` (`hatchling` backend, Python bounds `>=3.11`, single source of truth versioning bound to `VERSION`).
  - Implemented unified console entrypoint `oude` (`src/oude_mechanismen/cli.py` and `src/oude_mechanismen/__init__.py`) supporting `init`, `install-skills`, `doctor`, and pass-through execution of bundled scripts (`lint`, `audit`, `digest`, `harvest`, `filter`, `transcribe`, `scribe`, `benchmark`).
  - Added dual-mode asset resolution (`_resolve_asset_dir`) supporting both editable git checkouts and isolated wheel distributions installed via `uv tool`.
  - Added global skills synchronisation (`oude install-skills`) into XDG data directory `~/.local/share/oude-mechanismen/skills` with idempotent registration in `~/.gemini/config/skills.json`.
  - Consolidated `skills/illustrate-entry/scripts/art_filter.py` into `scripts/art_filter.py` and simplified the import in `scripts/harvest_archival.py`.
  - Added PEP 723 `# /// script` metadata blocks to standalone scripts with third-party dependencies (`art_filter.py`, `generate_digests.py`, `harvest_archival.py`, `transcribe_session.py`).
  - Updated procedural skills (`skills/add-chapter/SKILL.md`, `skills/illustrate-entry/SKILL.md`, `skills/scribe-session/SKILL.md`) and `templates/AGENTS.md.template` to invoke `oude <subcommand>` rather than local script paths.
  - Added corrupt configuration backup protection in `_load_gemini_skills_config()` preventing data loss upon invalid `skills.json`.
  - Added comprehensive automated unit test suite in `tests/test_cli.py` (9 test cases, 67 tests passing across entire suite).
  - Extended CI workflow (`.github/workflows/ci.yml`) with Astral `uv` setup, wheel packaging validation, and CLI execution tests.

---

## [0.4.1] - 2026-11-10

### Added

- **Enforced Automatic Branch Deletion on Merge**:
  - Updated `bin/init_vault.sh` to opportunistically enable `gh repo edit --delete-branch-on-merge` when target repositories possess a configured GitHub remote.
  - Added `## Agent Behaviour` to `templates/AGENTS.md.template` enshrining the Branch Lifecycle invariant and mandatory post-merge local branch cleanup.
  - Added Section 7 (`## 7. Git Hygiene & Branch Lifecycle`) to `AGENTS.md`.
  - Added explicit post-merge local branch cleanup instructions (`git checkout main && git pull`, `git branch -d <branch>`, `git fetch --prune`) to procedural skills (`skills/add-chapter/SKILL.md`, `skills/scribe-session/SKILL.md`, and `skills/add-character/SKILL.md`).
  - Added automated unit test coverage in `tests/test_init_vault.py` verifying opportunistic remote branch deletion.

---

## [0.4.0] - 2026-11-09

### Added

- **Dynamic Decoupled Jekyll Gem Architecture (ADR 001)**:
  - Packaged `oude-mechanismen` as a native Jekyll plugin RubyGem (`oude-mechanismen.gemspec` and `lib/oude_mechanismen.rb`) serving plugins and in-memory Liquid includes (`_includes/`) via Jekyll's `site.includes_load_paths` hook (`:site, :after_reset`), eliminating the need to copy engine templates into downstream campaign repositories.
  - Added `lib/oude_mechanismen/version.rb` dynamically bound to root `VERSION` file (`0.4.0`) and `lib/oude-mechanismen.rb` compatibility shim for Bundler/Jekyll plugin discovery.
  - Updated `jekyll/_plugins/data_extractor.rb` to stamp `"engine_version": "0.4.0"` into `.agents/context/catalog.json` and automatically invalidate the build cache whenever the engine version changes.
  - Implemented `bin/init_vault.sh` (63 lines), an idempotent, declarative campaign vault bootstrapper replacing continuous file synchronisation (`sync.sh`) with one-time starter scaffolding (`cp -n`).
  - Updated starter templates (`templates/jekyll/Gemfile.template`, `templates/jekyll/_config.yml.template`) to declare `gem "oude-mechanismen", git: "https://github.com/terra-campaigns/oude-mechanismen.git", tag: "v0.4.0"` and registered `oude-mechanismen` under `plugins:`.
  - Authored and committed [ADR 001](docs/adr/001_dynamic_engine_vs_sync_distribution.md) formalising the Hybrid Decoupled Architecture, versioning policy, and Git pre-commit hook elimination.
  - Added automated unit test suite in `tests/test_init_vault.py` covering directory topology, template scaffolding, no-clobber idempotence, and Ruby gem version binding.
  - Extended CI workflow (`.github/workflows/ci.yml`) to validate `bin/init_vault.sh` (`bash -n` and `shellcheck`), Ruby module syntax, and automated `gem build`.

- **The Archival Scriptorium (`scripts/harvest_archival.py`)**:
  - Implemented headless cultural asset excavator querying keyless open-access collections (Wikimedia Commons Action API and The Metropolitan Museum of Art Open Access API).
  - Implemented anti-AI lexical filtering across categories and descriptions, and machine-readable rights validation (`CC0`, `Public domain`, `CC BY`).
  - Added semantic query expansion via local Ollama (`qwen2.5:14b`), translating campaign entities into pre-20th-century historical museum terms with deterministic fallback.
  - Added note-relative image path calculation (`../../imgs/gallery/<slug>.jpg`) ensuring full compatibility with Jekyll's `_plugins/data_extractor.rb` and bidirectional gallery indexing.
  - Added theme-compliant HTML attribution generation (`<a href="..." target="_blank" rel="noopener noreferrer">...</a>`) for `footer_content:`.
  - Added multi-preset graphic-novel variant styling via `scripts/art_filter.py` and automated disk cleanup of unselected candidate assets.
  - Added downstream runner `templates/runners/harvest_archival.py.template` and registered in `sync.sh`'s `MANAGED_FILES`.
  - Added comprehensive automated unit test suite in `tests/test_harvest_archival.py` with 28 tests passing in 0.003s.

- **Vault Gap Coverage Extension (`scripts/audit_coverage.py --unillustrated`)**:
  - Added `--unillustrated` flag to `scripts/audit_coverage.py`, scanning campaign markdown notes across included paths to identify entries lacking `images:` or displaying fallback geometric badges (`/imgs/badges/`).
  - Added JSON export and markdown table reporting for discovery sweeps.

---

## [0.3.0] - 2026-11-08

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
