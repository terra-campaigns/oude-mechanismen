# ADR 003 Completion: Vault Migration, LAN Preview, and Semantic Wiki Digestion

* **Author:** `efsalvarenga`
* **Status:** Proposed
* **Date:** 2026-11-15

***

## Overview

`oude-mechanismen` `v0.6.0` shipped ADR 003 Phase 1 (`_gm-materials/` path normalisation and recursive `compile_references()` indexing), yet downstream operator campaign vaults (`hostile` and `charged`) still depend on Google Drive workflows across `ryu` (macOS tabletop companion) and `artemis` (Debian production hub). Across ADR 003, **Phase 1** covers path normalisation and index hygiene (with follow-ups `#36` `audit_coverage.py` CLI hint, `#37` `AGENTS.md.template` `data_extractor.rb` cleanup, and `#39` `find_drive_dir()`, `compile_references()`, and CRLF `exclude:` edge cases), **Phase 2** covers multi-device local-network Jekyll preview, and **Phase 3** covers multi-file semantic sourcebook PDF digestion. Phase 1 follow-ups, Phase 3 sourcebook digestion, and verified vault migration guidance (`#22` vault migration and `DYNAMIC_GEM.md` guides) remain incomplete, whilst Phase 2 can be solved through documentation rather than new CLI wrapper code.

This design finishes the remaining ADR 003 work across staged, independent deliveries: resolving Phase 1 defects and legacy path leaks, documenting zero-wrapper LAN Jekyll preview, delivering a harness-agnostic `skills/digest-book/` workflow backed by deterministic helpers in `scripts/generate_digests.py`, validating the digestion pipeline empirically against *BF1 Morgansfort* and *Eclipse Phase (1st Edition)*, and tracking the codebase's unresolved bootstrap/sync drift backlog under existing linked issues.

> **Axis Clarification (ADR 003 §2 — Storage Pillars vs Canon Tiers):** Physical **Storage Pillars** (**Pillar 1**: public Git repository; **Pillar 2**: git-ignored `_gm-materials/` synced peer-to-peer via Obsidian Sync; **Pillar 3**: local-only disk outside Git and Obsidian Sync) are orthogonal to **Canon Tiers** in `AGENTS.md` §4 (**Tier 0**: local-only raw audio/transcripts; **Tier 1**: published Git wiki notes; **Tier 2**: GM rulings and archival session notes in `_gm-materials/`; **Tier 3**: external reference PDFs and synthesised `_gm-materials/digests/`).

## The Problem

Campaign operators (`efsalvarenga`) still cannot move active campaign vaults (`hostile`, `charged`) off Google Drive onto the dual-workstation (`ryu` ↔ `artemis`) workflow because four operational blockers remain:

1. **Cross-OS Google Drive coupling & broken legacy path hooks**: Debian (`artemis`) lacks a native first-party Google Drive client, yet existing vaults remain tied to Drive paths without a verified migration path into git-ignored `_gm-materials/` synced via Obsidian Sync (peer-to-peer synchronisation for git-ignored vault directories) plus portable `drive_dir: .` config. Meanwhile, `scripts/generate_digests.py` still computes `rpg_root = drive_dir.parents[1]` (residing outside the vault when `drive_dir: .`), leaks machine-specific paths into `.agents/context/references.json`, and scans `.git/`, `_site/`, and `vendor/` via `drive_dir.rglob("*.pdf")`.
2. **Untested, non-scalable sourcebook PDF ingestion**: Current `oude digest --scaffold` extracts only top-level PDF outline bookmarks into flat skeleton files. Large commercial PDFs exceed typical agent file-reading tool limits (`800` lines / `46,080` bytes), layout-mode `pypdf` text extraction interleaves columns in two-column RPG layouts and d100 tables, and the multi-file semantic wiki workflow planned in ADR 003 §3.5 has never been tested end-to-end against real sourcebooks.
3. **Undocumented multi-device LAN preview**: There is no documented workflow for serving a live Jekyll preview from `artemis` to `ryu` and mobile devices on the home network without dirtying tracked `_config.yml` production settings.
4. **Contradictory repository bootstrap, sync, and audit tooling**: Existing scripts, templates, and docs give conflicting instructions (`#36`, `#37`, `sync.sh` pushing `.agents/scripts/` whilst `oude doctor --fix` deletes legacy runners, and `README.md` still teaching `./sync.sh --init`, `_sessions/`, and localhost-only serving).

## Goals

* Close remaining Phase 1 defects (`#36`, `#37`, `#39`) and remove `rpg_root = drive_dir.parents[1]` and `drive_dir.rglob("*.pdf")` from `scripts/generate_digests.py`.
* Deliver Phase 2 LAN preview by amending ADR 003 §3.4/§5 and updating `README.md` with the raw Bundler command (`bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""`), host `avahi-daemon` notes (`http://artemis.local:4000` via the Linux mDNS `*.local` hostname broadcaster), and non-mDNS IP fallback (`http://<artemis-ip>:4000`).
* Add explicit external `<pdf_path>` handling (Pillar 3 outside Git and Obsidian Sync), deterministic outline/page slicing, portable `source_pdf` + `source` fields (`zero host-specific paths in .agents/context/references.json`), and hard-invariant validation (YAML frontmatter, blank lines after headings, resolvable relative Markdown links) to `scripts/generate_digests.py`.
* Author a setting- and harness-agnostic `skills/digest-book/SKILL.md` containing zero hardcoded external model or harness-specific references, and update ADR 003 §3.5/§5 to align on `skills/digest-book/` instead of an LLM-backed `oude digest-deep` CLI command.
* Empirically validate the end-to-end digestion workflow against full *BF1 Morgansfort* and *Eclipse Phase (1st Edition)* with zero `--validate` failures across both sourcebooks.
* Publish reconciled migration and dynamic gem documentation (`#22`) unblocking `hostile` and `charged` vault migration off Google Drive, and explicitly track remaining bootstrap/sync drift (`sync.sh`, `bin/init_vault.sh`, `README.md`, missing `DYNAMIC_GEM.md`) so none of it is silently dropped.

## Non-Goals

* Implementing an `oude serve` CLI wrapper subcommand or a tracked `templates/jekyll/_config_dev.yml.template`.
* Embedding LLM SDKs, API keys, or harness-specific dispatch commands (such as `/vibe-execute` or `mistral-large-4`) inside `oude-mechanismen` Python CLI code or `skills/digest-book/SKILL.md`.
* Hard-failing deterministic digest validation on soft prose heuristics such as exact `30–120` line counts or mandatory nine-folder directory splits.
* Simultaneous multi-vault Jekyll serving on port `4000`, or daemon-level health monitoring of `obsidian-sync.service` inside `oude doctor`.
* Modifying Tier 0 air-gap Whisper/Ollama audio transcription paths (`~/Private/rpg-sessions/`).

## Open Questions

*(Open questions below are gating checks to resolve before transitioning Status from `Proposed` to `Accepted`.)*

* **Stage C scanned-page fallback threshold**: Exact minimum extractable-character-per-page threshold triggering automatic `.pdf` slice fallback under `--extract` (defaulting conservatively and tuned empirically against *BF1 Morgansfort* and *Eclipse Phase 1st Edition*).
* **Drift backlog tracking destination**: Confirmed anchored to existing linked GitHub issues (`#36`, `#37`, `#39`, `#22`) mapped in the `Target Stage` column of the backlog table below; decide during Stage B only whether any sub-item also warrants splitting out of `#22`.

## Critical User Journeys (CUJs)

### CUJ 1: Migrating `hostile` / `charged` Off Google Drive

* **Given**: An existing campaign vault using a legacy Google Drive `drive_dir`, external PDFs stored on local Pillar 3 disk (outside Git and Obsidian Sync), and Obsidian Sync active between `ryu` and `artemis` for git-ignored `_gm-materials/`.
* **When**: The GM follows the reconciled migration checklist (`docs/MIGRATION_GUIDE.md`), sets `drive_dir: .` in `.agents/context/tier1_sources.yml`, moves GM notes and digests into `_gm-materials/`, re-runs digest indexing, and executes `oude doctor`.
* **Then**: `.agents/context/references.json` contains only portable relative paths with zero host-specific `rpg_root` prefixes, Obsidian Sync keeps `_gm-materials/` aligned between `ryu` and `artemis`, and Google Drive is no longer required on either machine.

### CUJ 2: Semantic Book Digestion via `skills/digest-book/`

* **Given**: A commercial RPG rulebook or adventure PDF (such as *BF1 Morgansfort* or *Eclipse Phase 1st Edition*) located outside the campaign repo and an agent harness reading `skills/digest-book/SKILL.md`.
* **When**: Deterministic helpers in `scripts/generate_digests.py` split/extract bounded page-tagged chapters from the explicit `<pdf_path>`, the agent synthesises hyperlinked Markdown entity notes into `_gm-materials/digests/<source>/` (natively or via an external model opted into by the user), and the deterministic validator + `compile_references()` run.
* **Then**: Every entity note satisfies YAML frontmatter, blank-line heading spacing, and valid relative Markdown link invariants, tables survive as Markdown tables without raw 50 MB PDF context overflows, and `.agents/context/references.json` indexes all notes cleanly.

### CUJ 3: Multi-Device LAN Jekyll Preview (`artemis.local:4000`)

* **Given**: A campaign vault checked out on `artemis` with `avahi-daemon` active, `url:` configured for production GitHub Pages in `_config.yml`, and only one vault previewed at a time.
* **When**: The GM runs `oude doctor` to verify `_config.yml` `exclude:` safety, starts `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""`, and opens `http://artemis.local:4000` (or `http://<artemis-ip>:4000` on non-mDNS devices) from `ryu` or a phone on the same LAN.
* **Then**: The compiled site renders without broken links or missing images (`use_wsrv` stays disabled outside `JEKYLL_ENV=production`), without maintaining wrapper code or committing an un-gitignored dev overlay config.

### CUJ 4: Tooling & Documentation Consistency Audit

* **Given**: A developer, GM, or CI check consulting `README.md`, `AGENTS.md`, `templates/AGENTS.md.template`, `scripts/audit_coverage.py`, or running `oude doctor --fix`.
* **When**: Unindexed Pillar 3 materials are audited, manual catalogue compilation is run, or repository bootstrap/sync instructions are inspected.
* **Then**: Action hints invoke valid `oude` CLI commands (`oude digest`, `bundle exec jekyll build`), legacy conflicts (`sync.sh` vs `.agents/scripts/`, `bin/init_vault.sh` vs `oude init`) are explicitly resolved or tracked in-repo, and no doc directs users to deleted `_plugins/data_extractor.rb` or `.agents/scripts/` paths.

## Technical Plan (Architecture)

The remaining ADR 003 scope is delivered across four decoupled stages (`A` through `D`) so deterministic hygiene and docs ship immediately without waiting on PDF extraction validation.

### Stage A — Phase 1 Hygiene & Google Drive Decoupling (`#36`, `#37`, `#39`)

* **`scripts/audit_coverage.py`**: Update `resolve_unindexed_file_action()` (line 130) to print `oude digest --scaffold` instead of `.agents/scripts/generate_digests.py`, align `resolve_drive_dir()` YAML parsing with sibling scripts (`yaml.safe_load` / consistent edge handling per `#39`), and remove obsolete Google Drive phrasing.
* **`templates/AGENTS.md.template` & `templates/tier1_sources.yml.template`**: Replace the deleted `_plugins/data_extractor.rb` command (`templates/AGENTS.md.template:53`) with `bundle exec jekyll build` / `oude doctor --fix` (`#37`), and reword `drive_dir` comments (`templates/tier1_sources.yml.template:10-12`) to mark `.` as the portable repository-root default.
* **`scripts/generate_digests.py`, `scripts/transcribe_session.py`, & `src/oude_mechanismen/cli.py` (`#39`)**: Propagate non-YAML read failures in `find_drive_dir()` loudly instead of falling back silently to `repo_root`; guard `compile_references()` against slicing Markdown thematic breaks (`---`) when frontmatter is absent or invalid; support CRLF line endings and blank/comment lines cleanly in `_has_jekyll_exclude` / `_append_jekyll_list_item`.
* **Drop `rpg_root` & bulk PDF scanning (`scripts/generate_digests.py`)**: Remove `rpg_root = drive_dir.parents[1]` (lines 112 and 376) and bulk `drive_dir.rglob("*.pdf")` (`find_pdf()` line 280). Require explicit `<pdf_path>` arguments outside the repository (Pillar 3) and record portable relative/filename `source_pdf` entries.

### Stage B — Phase 2 Zero-Wrapper LAN Preview (Documentation Only) & ADR Amendment

* **Zero wrapper code (documentation only)**: Inspecting `jekyll/_includes/image_gallery.html:13-18` and `jekyll/_includes/connected_to.html:37-42` shows `use_wsrv` (gating `https://wsrv.nl`, the external production image-optimisation proxy and sole consumer of `site.url`) only activates when `jekyll.environment == "production"` and `site.url` is non-localhost. Because `jekyll serve` runs in `development` mode by default and internal links use `| relative_url`, leaving production `url:` intact in `_config.yml` works on LAN without a dev YAML overlay or Python CLI wrapper (`oude serve` / `_config_dev.yml.template` omitted).
* **ADR 003 & `README.md` updates**: Amend ADR 003 §3.4/§3.5/§5 to replace `oude serve` / `_config_dev.yml.template` with pre-serve `oude doctor` verification followed by `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` (single active vault at a time on port `4000`) plus `oude digest` + `skills/digest-book/` replacing `oude digest-deep`. Update `README.md` (lines 96–101 and surrounding onboarding steps) with pre-serve `oude doctor` usage, this LAN command, `avahi-daemon` host notes (`http://artemis.local:4000`), and non-mDNS IP fallback (`http://<artemis-ip>:4000`).

### Stage C — Hybrid PDF Extraction, Hard-Invariant Validation, `skills/digest-book/`, & Empirical Testing

* **Hybrid `--extract <pdf_path>` (`scripts/generate_digests.py`)**: Uses existing `pypdf` (`extract_pdf_outline()`, falling back to bounded page ranges when outline-less) to emit bounded staging slices so raw 50 MB PDFs are never read whole into agent context:
  * *Default (`--format text`)*: Extracts UTF-8 slices via `page.extract_text(extraction_mode="layout")`, prefixed with explicit `--- Page X ---` markers and split at `<= 38,000` bytes per file (to stay within typical agent file-reading tool limits of `800` lines / `46,080` bytes).
  * *Scanned/table mode (`--format pdf`, or automatic per-slice fallback when extracted character density falls below threshold)*: Uses `pypdf.PdfWriter` to emit small bounded `.pdf` page-range slices into a temporary staging directory for visual or OCR readers.
* **Deterministic hard-invariant validator (`--validate`) & index parity**: Validates YAML frontmatter keys (`source`, `tier`, `entity_type`, `title`), blank line immediately after every Markdown heading, and existing relative Markdown link targets; restores the `source` property in `.agents/context/references.json` (`compile_references()`) to match ADR 003 §3.5.4. Soft heuristics (`30–120` line counts, nine-folder split rules) remain skill guidance rather than hard validator failures.
* **Harness-agnostic `skills/digest-book/SKILL.md` & Empirical Validation**: Authors the purely procedural skill per `AGENTS.md` §1 (zero hardcoded `/vibe-execute`, model names, or LLM SDKs), reading `<out_dir>/manifest.json` slices from `--extract`, writing `_gm-materials/digests/<source>/` notes via atomic staging (`<out_dir>/staged/<source>/` validated with `--validate` before replacing `<drive_dir>/_gm-materials/digests/<source>/`) under priority-order folder classification (`factions/` → `locations/` → `people/` → `creatures/` → `artefacts/` → `mechanics/` → `tables/` → `other/` catch-all, with `_index.md` as book root), and running `compile_references()`. Validate end-to-end against full *BF1 Morgansfort* and *Eclipse Phase (1st Edition)*.

### Stage D — Reconciled Vault Migration & Dynamic Gem Docs (`#22`)

* Publish `docs/MIGRATION_GUIDE.md` (step-by-step guide to move `hostile`/`charged` off Google Drive into git-ignored `_gm-materials/` + Obsidian Sync, set `drive_dir: .`, re-anchor `references.json`, and run `oude doctor` / `oude audit`) and `docs/DYNAMIC_GEM.md` (`oude-mechanismen` gem architecture, configuration, troubleshooting), linking both from root `AGENTS.md` and `README.md` whilst reconciling `bin/init_vault.sh` vs `oude init` and `sync.sh`.

### Data Flow

```text
Pillar 3 External PDF (<pdf_path>, outside Git & Obsidian Sync)
        │
        ▼
scripts/generate_digests.py --extract <pdf_path> [--format auto|text|pdf]
  ├─ outline bookmarks (or bounded page batches)
  ├─ text mode: pypdf layout extraction (--- Page X ---, <= 38,000-byte chunks)
  └─ --format pdf or low-text scanned fallback: pypdf.PdfWriter page slices
        │  emits slices + <out_dir>/manifest.json
        ▼
skills/digest-book/SKILL.md (harness-agnostic synthesis; optional user offload)
        │
        ▼  stages in <out_dir>/staged/<source>/ -> --validate -> atomic replace
Pillar 2 (git-ignored, Obsidian-Synced): _gm-materials/digests/<source>/
        │
        ▼
scripts/generate_digests.py --validate  +  compile_references()
  ├─ hard invariants: YAML frontmatter, blank line after headings, link targets
  └─ compiles portable relative entries (+ source field)
        │
        ▼
Pillar 1 (Public Git): .agents/context/references.json

LAN Preview Path (Docs-Only Phase 2):
artemis ──▶ oude doctor && bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""
        ──▶ http://artemis.local:4000 (avahi-daemon) / http://<artemis-ip>:4000
        ──▶ ryu & mobile browsers (JEKYLL_ENV=development disables external wsrv.nl image proxy)
```

### Repository Drift & Reconciliation Backlog

All rows below remain anchored to their mapped GitHub issues (`#36`, `#37`, `#39`, `#22`) in the `Target Stage` column rather than duplicating separate tracking issues.

| Drift Item | Current Contradiction | Planned Resolution | Target Stage |
|---|---|---|---|
| `sync.sh` vs `oude doctor --fix` | `sync.sh` pushes templates into `.agents/scripts/` whilst `src/oude_mechanismen/cli.py` marks `.agents/scripts/` legacy and deletes it on `--fix` | Remove runner-script sync or align `MANAGED_FILES` with `cli.py` and document engine upgrade path | Stage D (`#22`) |
| `bin/init_vault.sh` vs `oude init` | Legacy shell bootstrapper in `docs/adr/001`, tests, CI, and `#22` overlaps with `cli.py` `oude init` | Document `oude init` as canonical; deprecate `bin/init_vault.sh` cleanly | Stage D (`#22`) |
| `README.md` onboarding | Still teaches `./sync.sh --init`, `_sessions/`, `_digests/`, and localhost-only `bundle exec jekyll serve` | Update quickstart, `--host 0.0.0.0` LAN preview, and Pillar 1–3 boundaries | Stage B / D |
| `#22` & root `AGENTS.md` | `#22` expects `init_vault.sh` / notebook phrasing and non-existent `DYNAMIC_GEM.md`; `AGENTS.md` mixes `jekyll build` and `_plugins/data_extractor.rb` phrasing | Author `docs/MIGRATION_GUIDE.md` & `docs/DYNAMIC_GEM.md`, sync `AGENTS.md`, close `#22` | Stage D (`#22`) |

## Alternatives Considered

### Alternative A: Wrapper `oude serve` + Tracked `templates/jekyll/_config_dev.yml.template`

* **Pros:** Provides a single CLI entry point for LAN preview and centralises Jekyll flags in Python.
* **Cons:** Adds subprocess and flag plumbing for a single shell command; a tracked `_config_dev.yml` absent from `DEFAULT_GITIGNORE` risks leaking `url: ""` into GitHub Pages vault configs.
* **Reason for Rejection:** Rejected: inspecting `jekyll/_includes/image_gallery.html:13-18` and `jekyll/_includes/connected_to.html:37-42` confirms `use_wsrv` (gating `https://wsrv.nl`, the external production image-optimisation proxy and sole consumer of `site.url`) is disabled outside `JEKYLL_ENV=production`, so running `oude doctor` followed by `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` works without wrapper code or an overlay YAML file.

### Alternative B: Standalone LLM-Backed `oude digest-deep` CLI Command in Python

* **Pros:** Offers a single CLI command experience directly from the Python package.
* **Cons:** Forces LLM SDKs, API key configuration, and external provider coupling inside `oude-mechanismen`, contradicting the engine-agnostic contract in `AGENTS.md` §1.
* **Reason for Rejection:** Rejected: semantic Markdown synthesis belongs in the harness-agnostic `skills/digest-book/SKILL.md`, keeping `scripts/generate_digests.py` deterministic, offline, and testable in CI.

### Alternative C: Single-Format PDF Extraction (Split `.pdf` Only or Layout `.txt` Only)

* **Pros:** Simpler `--extract` implementation with only one output path to maintain.
* **Cons:** Split-only `.pdf` slices fail in text-only sessions lacking PDF vision/OCR support and hit binary read limits unless sliced thinly; layout-only `.txt` slices emit empty output on scanned PDFs and interleave complex boxed two-column RPG stat blocks.
* **Reason for Rejection:** Rejected: hybrid `--format text|pdf` with scanned-page auto-fallback preserves text portability across text-only sessions whilst providing lossless visual PDF slicing for scanned or table-dense chapters (with only the scanned-page density threshold tuned empirically in Stage C).

### Alternative D: Hard-Failing Deterministic Validator on Soft Prose Heuristics (`30–120` Line Cap & Mandatory Nine-Folder Taxonomy)

* **Pros:** Enforces uniform note sizing and directory layouts mechanically.
* **Cons:** Produces brittle build failures on legitimate short rollable tables or focused single-subsystem modules, coupling CI checks to prose length rather than structural integrity.
* **Reason for Rejection:** Rejected: deterministic validation stays restricted to hard structural invariants—valid YAML frontmatter, blank lines immediately after headings, resolvable relative Markdown link targets, and schema-valid `.agents/context/references.json` entries—whilst keeping soft sizing heuristics as guidance inside `skills/digest-book/SKILL.md`.

### Alternative E: Monolithic Single Implementation PR Across Stages A–D

* **Pros:** Ships all ADR 003 completion work in one review cycle.
* **Cons:** Couples straightforward Phase 1 bug fixes (`#36`, `#37`, `#39`) and Phase 2 documentation updates to Stage C's empirical PDF extraction validation and Stage D's migration guides, slowing delivery and inflating PR review scope.
* **Reason for Rejection:** Rejected: four decoupled PRs (Stages A–D) allow Phase 1 fixes and Phase 2 docs to ship immediately whilst Stage C tooling validation and Stage D `#22` documentation proceed independently.

## Non-Functional Requirements, Risks & Mitigations

* **Security & Privacy (LAN Exposure Risk & Air-Gap)**: Binding Jekyll to `--host 0.0.0.0` exposes compiled Tier 1 pages without authentication across the active local network interface; *Risk*: misconfigured `_config.yml` `exclude:` rules could expose `_gm-materials/` or `.agents/`. *Mitigation*: operators run `oude doctor` before serving on `--host 0.0.0.0` so Jekyll `exclude:` and `jekyll/_plugins/data_extractor.rb` exclusions are verified in advance, and Tier 0 raw recordings/verbatim transcripts remain confined to local disk (`~/Private/rpg-sessions/`).
* **Engine Agnosticism, Determinism & Heuristic Drift Risk**: No setting lore, LLM SDKs, API keys, model identifiers, or harness-specific dispatch commands (such as `/vibe-execute`) may appear in `oude-mechanismen` Python modules or `skills/digest-book/SKILL.md`, and all `scripts/generate_digests.py` sub-commands (`--extract`, `--validate`, `compile_references()`, `--scaffold`) execute offline in CI; *Risk*: `--min-chars-per-page` miscalibration yields empty text or excess `.pdf` slices. *Mitigation*: operators can override with `--format pdf` explicitly and inspect `--validate` `auto_fallback_reason` diagnostics.
* **Portability & Bounded Context**: `.agents/context/references.json` records only portable POSIX relative paths or basenames (`source_pdf`), never host-specific `rpg_root` prefixes or OS absolute paths. Text slices emitted by `--extract` remain capped at `<= 38,000` bytes (within typical agent file-reading tool limits of `800` lines / `46,080` bytes) and stage into a temp directory outside Git and Obsidian Sync.
* **Port Conflict, Sync Conflict & Rollout Safety**: *Risk*: serving a second vault simultaneously fails or collides on port `4000`, and interrupted multi-file digestion could expose partial trees over Obsidian Sync. *Mitigation*: only one vault is previewed at a time (or operators pass `--port <N>`), `skills/digest-book/` writes atomically per `<source>` via `<out_dir>/staged/<source>/` before replacing `_gm-materials/digests/<source>/`, and four additive Stages (`A`–`D`) ensure Phase 1 bug fixes (`#36`, `#37`, `#39`) and docs are independently revertible.

## Detailed Implementation Plan

### APIs, CLI Flags & Extraction Schemas

1. **`scripts/generate_digests.py` (`oude digest`) Contract**:
   - **External `<pdf_path>` & Portability**: Stage A updates `--scaffold <PDF_PATH>` from its legacy substring query via `find_pdf()` to explicit `<PDF_PATH>` resolution (`Path.expanduser().resolve()`), matching Stage C's `--extract <PDF_PATH>`; missing files raise `FileNotFoundError`. Optional `--source-pdf <REL_OR_NAME>` sets the canonical portable identifier recorded in frontmatter and `.agents/context/references.json`; if omitted, external Pillar 3 paths default to `pdf_path.name` and in-vault paths use `pdf_path.relative_to(drive_dir).as_posix()`. Remove `rpg_root = drive_dir.parents[1]` and `drive_dir.rglob("*.pdf")` (`find_pdf()`).
   - **Extraction CLI (`--extract <PDF_PATH>`)**:
     - Flags: `--format {auto,text,pdf}` (default `auto`), `--out-dir <DIR>` (defaults to `Path(tempfile.gettempdir()) / "oude-extract" / slug`, resolving `$TMPDIR` → `/tmp` outside the repository and retained on disk for inspection/re-runs until overwritten or cleared by OS temp cleanup), `--max-depth <N>` (default `1`), `--chunk-pages <N>` (default `10` when PDF has no outline), `--pdf-slice-pages <N>` (default `5`), `--max-bytes <N>` (default `38000`), `--min-chars-per-page <N>` (default `80`, calibrated empirically in Stage C).
     - Emits ordered slice files plus `<out_dir>/manifest.json` (consumed by `skills/digest-book/SKILL.md` to iterate slices in page order and by `oude digest --validate` for fallback telemetry) adhering to:
       ```json
       {
         "source_pdf": "bf1_morgansfort.pdf",
         "slug": "bf1_morgansfort",
         "total_pages": 72,
         "format_requested": "auto",
         "min_chars_per_page": 80,
         "slices": [
           {
             "index": 1,
             "title": "Chapter 1: Morgansfort",
             "start_page": 3,
             "end_page": 14,
             "format": "text",
             "path": "001_chapter_1_morgansfort.txt",
             "byte_size": 24180,
             "char_count": 21940,
             "auto_fallback_reason": null
           }
         ]
       }
       ```
     - **Deterministic Chunking & Fallback Algorithm**: Flatten PDF outline bookmarks to `--max-depth` (`1`), deriving each entry's `[start_page, end_page]` span without merging adjacent top-level bookmarks. For outline-less PDFs or any span whose layout UTF-8 text (`page.extract_text(extraction_mode="layout")` with `--- Page <N> ---` markers) exceeds `--max-bytes` (`38,000`), split into sequential `--chunk-pages` (`10`) page windows and halve any still-oversized window recursively down to single pages. In `--format pdf` mode or whenever `char_count / page_count < min_chars_per_page` under `auto`, emit `.pdf` sub-slices of `<= --pdf-slice-pages` (`5`) pages via `pypdf.PdfWriter` and set `"auto_fallback_reason": "low_char_density (<density> < <min_chars_per_page>)"` in `manifest.json`.
   - **Hard-Invariant Validator (`--validate [<DIGEST_DIR>]`)**:
     - Defaults `<DIGEST_DIR>` to `<drive_dir>/_gm-materials/digests`. Checks every `*.md` file recursively, returning exit code `0` on pass or `1` with `file:line: <reason>` diagnostics on failure:
       1. Valid YAML mapping frontmatter containing `source` (non-empty `str`), `tier == 3`, `entity_type` in `{index, faction, location, person, creature, artefact, mechanic, table, other}`, and `title` (non-empty `str`).
       2. Every Markdown heading (`#`–`######`, outside fenced code blocks) followed immediately by an empty blank line.
       3. Every relative Markdown link target (excluding `http://`, `https://`, `mailto:`, and pure `#fragment` links, stripping `#fragment` before resolution) resolves via `(md_file.parent / link_target).resolve()` to an existing file inside `<drive_dir>/_gm-materials/digests/` (intra-digest links) or `<repo_root>/{campaigns,directory,systems}/` (outbound Tier 1 cross-references), failing if missing or escaping `<repo_root>/`.
     - Emits non-fatal `[INFO]` stats for note line counts and (`when <out_dir>/manifest.json` is present) summary counts of `auto_fallback_reason`; never fails on soft `30–120` line counts or subset category directories.
   - **Index Parity (`compile_references()`)**: Extend `compile_references()` to copy newly added optional `"source"` from YAML frontmatter into `.agents/context/references.json` alongside existing `("entity_type", "pages", "tags")`, and preserve `body = content` / `fm_prefix = ""` whenever leading `---` does not parse as a YAML mapping (`#39`).

### Target Files to Create / Modify (Stages A–D)

*(Line numbers cited below reflect `v0.6.0` (`0350c7b`) as of drafting; named functions, symbols, and section headings are authoritative.)*

#### 1. `scripts/audit_coverage.py` ([Modify] — Stage A, `#36`, `#39`)

* Update `resolve_unindexed_file_action()` (`L130`) to suggest `oude digest --scaffold "{rel}"` instead of the deleted `.agents/scripts/generate_digests.py` path; align `resolve_drive_dir()` (`L52`) with `yaml.safe_load` / consistent edge handling (`#39`); remove obsolete Google Drive phrasing (`L722` and helpers).

#### 2. `scripts/transcribe_session.py` ([Modify] — Stage A, `#39`)

* Re-raise non-YAML read failures (`OSError`, `UnicodeDecodeError`) inside `find_drive_dir()` (`L57-95`) instead of silently falling back to `repo_root`, and remove legacy Google Drive docstrings/help wording (`L12`, `L575`, `L648`).

#### 3. `src/oude_mechanismen/cli.py` ([Modify] — Stage A, `#39`)

* Update `_has_jekyll_exclude()` (`L338`) and `_append_jekyll_list_item()` (`L301`) to tolerate CRLF (`\r\n`) endings and blank/comment lines inside YAML `exclude:` blocks so `oude doctor` handles Windows/macOS/Linux edits reliably.

#### 4. `templates/AGENTS.md.template` & `templates/tier1_sources.yml.template` ([Modify] — Stage A, `#37`)

* Replace the deleted `ruby --disable-gems _plugins/data_extractor.rb` instruction (`templates/AGENTS.md.template:53`) with `bundle exec jekyll build` / `oude doctor --fix`; clarify `drive_dir` (`templates/tier1_sources.yml.template:10-12`) as the portable repository-root default (`.` alias).

#### 5. `scripts/generate_digests.py` ([Modify] — Stage A & Stage C)

* In Stage A, propagate non-YAML read errors in `find_drive_dir()`, guard thematic-break `---` slicing in `compile_references()`, and strip `rpg_root = drive_dir.parents[1]` (`L112`, `L172-173`, `L376-378`) plus `find_pdf()` `drive_dir.rglob("*.pdf")` (`L280`), taking explicit `<pdf_path>`. In Stage C, add `--extract`, `--validate`, `--source-pdf`, `manifest.json` emission, and `"source"` output parity in `compile_references()`.

#### 6. `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md` & `README.md` ([Modify] — Stage B)

* Amend ADR 003 §3.4, §3.5, and §5 to reflect zero-wrapper LAN preview (`oude doctor` followed by `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""`, dropping `oude serve` and `_config_dev.yml.template`) and deterministic `oude digest` + `skills/digest-book/` replacing `oude digest-deep`. Update `README.md` (`L87-113`) from legacy `./sync.sh --init` and localhost-only serving to `oude init`, `_gm-materials/`, pre-serve `oude doctor`, LAN `http://artemis.local:4000`, `avahi-daemon`, and non-mDNS IP fallback.

#### 7. `skills/digest-book/SKILL.md` ([Create] — Stage C)

* Author a setting- and harness-agnostic procedural skill compliant with `AGENTS.md` §6 (British English, heading blank lines, YAML frontmatter `name`, `description`, `argument-hint`) containing zero hardcoded `/vibe-execute` or LLM SDK dependencies. Documents consuming `<out_dir>/manifest.json` from `oude digest --extract`, classifying multi-category entities via priority order (`factions/` → `locations/` → `people/` → `creatures/` → `artefacts/` → `mechanics/` → `tables/` → `other/` catch-all, `_index.md` book root), staging atomic `_gm-materials/digests/<source>/` trees in `<out_dir>/staged/<source>/` matching ADR 003 §3.5 schema, running `--validate`, and atomically replacing `<drive_dir>/_gm-materials/digests/<source>/` before running `compile_references()`.

#### 8. `skills/lookup-context/SKILL.md` ([Modify] — Stage C)

* Add concise 3-hop progressive navigation guidance (`_index.md` → targeted entity note via `digest_path` → annotated relative links) and note `source` field matching in `.agents/context/references.json`.

#### 9. `tests/test_audit_coverage.py`, `tests/test_generate_digests.py`, `tests/test_transcribe_session.py`, `tests/test_cli.py` ([Modify] — Stage A & Stage C)

* Update existing assertions (`oude digest --scaffold`, `rpg_root` removal, thematic-break `---` guard) and add coverage with synthetic fixtures (2-page outlined PDF, outline-less multi-page PDF, sparse `<80` chars/page PDF triggering `.pdf` slice fallback, CRLF `_config.yml`) for non-YAML read propagation, CRLF/blank-line YAML `exclude:` parsing, `--extract` (`text`, `pdf`, `auto` density fallback, `manifest.json`), `--validate` pass/fail diagnostics + `auto_fallback_reason` summary stats, and `"source"` field emission in `references.json`.

#### 10. `docs/MIGRATION_GUIDE.md` & `docs/DYNAMIC_GEM.md` ([Create] — Stage D, `#22`)

* Provide the reconciled step-by-step Google Drive → `_gm-materials/` + Obsidian Sync checklist (`drive_dir: .`, `references.json` re-indexing, `hostile`/`charged` cutover, `oude doctor --fix` + `oude audit` validation) and full `oude-mechanismen` RubyGem operator/customisation guide (reconciling `#22`'s `jekyll/DYNAMIC_GEM.md` vs `docs/` placement).

#### 11. `AGENTS.md`, `sync.sh`, `bin/init_vault.sh`, `tests/test_init_vault.py`, `.github/workflows/ci.yml` ([Modify] — Stage D)

* Update `AGENTS.md` (`L118–119` Tier 1 `_plugins/data_extractor.rb` `catalog.json` indexing reference, §5 `sync.sh` scope note, relative links `./docs/MIGRATION_GUIDE.md` and `./docs/DYNAMIC_GEM.md`), link both guides from `README.md`, remove conflicting `.agents/scripts/` runner mappings (`L76-81`) from `sync.sh` `MANAGED_FILES`, mark `bin/init_vault.sh` formally deprecated in favour of `oude init` whilst keeping CI shellcheck passing, and extend `.github/workflows/ci.yml`'s heading-spacing check across `docs/*.md`.

### Verification Plan

* **Unit & Integration Test Suite**: Run `"$HOME/.local/bin/uv" run --no-project --with pyyaml --with pypdf --with pytest pytest -v -o cache_dir=/tmp/pytest_cache_oude` after Stage A and Stage C edits; require `100%` passing assertions, zero failures, and zero skipped tests.
* **Shell, Ruby & Markdown Hygiene**: Verify CI parity checks locally (`ruby -c` on `jekyll/_plugins/*.rb` and `lib/*.rb`, `bash -n` on `sync.sh` and `bin/init_vault.sh`, and CI heading-blank-line validation across `skills/*/SKILL.md`, `docs/*.md`, `README.md`, `AGENTS.md`).
* **Empirical Stage C Book Validation**: Run `oude digest --extract`, skill-guided wiki synthesis (including user-selected `/vibe-execute` model offload outside `SKILL.md` for full-book throughput), `oude digest --validate`, and `compile_references()` against *BF1 Morgansfort* and *Eclipse Phase (1st Edition)* in a non-committed local scratch vault; verify pipe-delimited Markdown table row preservation on rollable tables, `>=95%` page-mode classification accuracy across sampled pages of both sourcebooks (tuning `--min-chars-per-page`), zero `--validate` failures, and portable relative-path entries only in `.agents/context/references.json`.
* **Manual LAN Preview Smoke Check**: Run `oude doctor` and start `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` from `artemis` on a migrated vault (`hostile` or `charged`) and verify live rendering, `relative_url` links, and gallery images render without broken links or missing images from `ryu` and mobile at `http://artemis.local:4000` (and `http://<artemis-ip>:4000`).
