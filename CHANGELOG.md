# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
