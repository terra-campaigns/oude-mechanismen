# ADR 003 Completion: Vault Migration, LAN Preview, and Semantic Wiki Digestion

* **Author:** `efsalvarenga`
* **Status:** Proposed
* **Date:** 2026-11-15

--------------------------------------------------------------------------------

## Overview

`oude-mechanismen` `v0.6.0` landed ADR 003 Phase 1 (`_gm-materials/` path normalisation and recursive `compile_references()` indexing), yet downstream campaign vaults (`hostile`, `charged`) remain tethered to Google Drive workflows across `ryu` (macOS tabletop companion) and `artemis` (Debian production hub). Phase 1 follow-ups (`#36`, `#37`, `#39`), external-PDF semantic digestion (Phase 3), and verified vault migration guidance (`#22`) remain incomplete, whilst local-network Jekyll preview (Phase 2) can be resolved cleanly through documentation rather than new CLI wrapper code.

This design finishes the remaining ADR 003 work across staged, independent deliveries: resolving Phase 1 defects and legacy path leaks, documenting zero-wrapper LAN Jekyll preview, delivering a harness-agnostic `skills/digest-book/` workflow backed by deterministic helpers in `scripts/generate_digests.py`, validating the digestion pipeline empirically against *BF1 Morgansfort* and *Eclipse Phase (1st Edition)*, and persisting the codebase's unresolved bootstrap/sync drift backlog with explicit tracking.

## The Problem

Campaign operators (`efsalvarenga`) still cannot move active campaign vaults (`hostile`, `charged`) off Google Drive onto the dual-workstation (`ryu` ↔ `artemis`) workflow because three operational blockers remain:

1. **Cross-OS Google Drive coupling & broken legacy path hooks**: Debian (`artemis`) lacks a native first-party Google Drive client, yet existing vaults remain tied to Drive paths without a verified migration path into git-ignored `_gm-materials/` (synced peer-to-peer via Obsidian Sync) plus portable `drive_dir: .` config. Meanwhile, `scripts/generate_digests.py` still computes `rpg_root = drive_dir.parents[1]` (residing outside the vault when `drive_dir: .`), leaks machine-specific paths into `.agents/context/references.json`, and scans `.git/`, `_site/`, and `vendor/` via `drive_dir.rglob("*.pdf")`.
2. **Untested, non-scalable sourcebook PDF ingestion**: Current `oude digest --scaffold` extracts only top-level PDF outline bookmarks into flat skeleton files. Large commercial PDFs exceed single-read harness caps (800 lines / 46,080 bytes), naive `pypdf` text extraction scrambles two-column RPG layouts and d100 tables, and the multi-file semantic wiki workflow planned in ADR 003 §3.5 has never been tested end-to-end against real sourcebooks.
3. **Undocumented LAN preview & contradictory repository tooling**: There is no documented workflow for serving a live Jekyll preview from `artemis` to `ryu` and mobile devices on the home network without dirtying tracked `_config.yml` production settings, and existing scripts, templates, and docs give conflicting instructions (`#36`, `#37`, `sync.sh` pushing `.agents/scripts/` whilst `oude doctor --fix` deletes legacy runners, and `README.md` still teaching `./sync.sh --init`, `_sessions/`, and localhost-only serving).

## Goals

* Close remaining Phase 1 defects (`#36`, `#37`, `#39`) and remove `rpg_root = drive_dir.parents[1]` and `drive_dir.rglob("*.pdf")` from `scripts/generate_digests.py`.
* Deliver Phase 2 LAN preview by amending ADR 003 §3.4/§5 and updating `README.md` with the raw Bundler command (`bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""`), host `avahi-daemon` notes (`http://artemis.local:4000`), and non-mDNS IP fallback (`http://<artemis-ip>:4000`).
* Add explicit external `<pdf_path>` handling (Pillar 3 outside Git and Obsidian Sync), deterministic outline/page slicing, portable `source_pdf` + `source` fields in `.agents/context/references.json`, and hard-invariant validation (YAML frontmatter, blank lines after headings, resolvable relative Markdown links) to `scripts/generate_digests.py`.
* Author a setting- and harness-agnostic `skills/digest-book/SKILL.md` containing zero hardcoded external model or harness-specific references, and update ADR 003 §3.5/§5 to align on `skills/digest-book/` instead of an LLM-backed `oude digest-deep` CLI command.
* Empirically validate the end-to-end digestion workflow against full *BF1 Morgansfort* and *Eclipse Phase (1st Edition)*.
* Publish reconciled migration and dynamic gem documentation (`#22`) unblocking `hostile` and `charged` vault migration off Google Drive, and explicitly track remaining bootstrap/sync drift (`sync.sh`, `bin/init_vault.sh`, `README.md`, missing `DYNAMIC_GEM.md`) so none of it is silently dropped.

## Non-Goals

* Implementing an `oude serve` CLI wrapper subcommand or a tracked `templates/jekyll/_config_dev.yml.template`.
* Embedding LLM SDKs, API keys, or harness-specific dispatch commands (such as `/vibe-execute` or `mistral-large-4`) inside `oude-mechanismen` Python CLI code or `skills/digest-book/SKILL.md`.
* Hard-failing deterministic digest validation on soft prose heuristics such as exact `30–120` line counts or mandatory nine-folder directory splits.
* Simultaneous multi-vault Jekyll serving on port `4000`, or daemon-level health monitoring of `obsidian-sync.service` inside `oude doctor`.
* Modifying Tier 0 air-gap Whisper/Ollama audio transcription paths (`~/Private/rpg-sessions/`).

## Open Questions

* **Stage C scanned-page fallback threshold**: Exact minimum extractable-character-per-page threshold triggering automatic `.pdf` slice fallback under `--extract` (defaulting conservatively and tuned empirically against *BF1 Morgansfort* and *Eclipse Phase 1st Edition*).
* **Drift backlog tracking destination**: Beyond documenting `bin/init_vault.sh` vs `oude init` and the `sync.sh` `.agents/scripts/` conflict in the backlog table below, confirm whether Stage B should also split those items into a dedicated GitHub issue or keep tracking unified under Stage D (`#22`).

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
* **When**: The GM runs the documented command `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` and opens `http://artemis.local:4000` (or `http://<artemis-ip>:4000` on non-mDNS devices) from `ryu` or a phone on the same LAN.
* **Then**: The compiled site loads cleanly with working internal navigation and local gallery images (`use_wsrv` stays disabled outside `JEKYLL_ENV=production`), without maintaining wrapper code or committing an un-gitignored dev overlay config.

### CUJ 4: Tooling & Documentation Consistency Audit

* **Given**: A developer, GM, or CI check consulting `README.md`, `AGENTS.md`, `templates/AGENTS.md.template`, `scripts/audit_coverage.py`, or running `oude doctor --fix`.
* **When**: Unindexed Pillar 3 materials are audited, manual catalogue compilation is run, or repository bootstrap/sync instructions are inspected.
* **Then**: Action hints invoke valid `oude` CLI commands (`oude digest`, `bundle exec jekyll build`), legacy conflicts (`sync.sh` vs `.agents/scripts/`, `bin/init_vault.sh` vs `oude init`) are explicitly resolved or tracked in-repo, and no doc directs users to deleted `_plugins/data_extractor.rb` or `.agents/scripts/` paths.

## Technical Plan (Architecture)

The remaining ADR 003 scope is delivered across four decoupled stages (`A` through `D`) so deterministic hygiene and docs land immediately without waiting on PDF extraction validation.

### Stage A — Phase 1 Hygiene & Google Drive Decoupling (`#36`, `#37`, `#39`)

* **`scripts/audit_coverage.py`**: Update `resolve_unindexed_file_action()` (line 130) to print `oude digest --scaffold` instead of `.agents/scripts/generate_digests.py`, align `resolve_drive_dir()` YAML parsing with sibling scripts (`yaml.safe_load` / consistent edge handling per `#39`), and remove obsolete Google Drive phrasing.
* **`templates/AGENTS.md.template` & `templates/tier1_sources.yml.template`**: Replace the deleted `_plugins/data_extractor.rb` command (`templates/AGENTS.md.template:53`) with `bundle exec jekyll build` / `oude doctor --fix` (`#37`), and reword `drive_dir` comments (`templates/tier1_sources.yml.template:10-12`) to mark `.` as the portable repository-root default.
* **`scripts/generate_digests.py`, `scripts/transcribe_session.py`, & `src/oude_mechanismen/cli.py` (`#39`)**: Propagate non-YAML read failures in `find_drive_dir()` loudly instead of falling back silently to `repo_root`; guard `compile_references()` against slicing Markdown thematic breaks (`---`) when frontmatter is absent or invalid; support CRLF line endings and blank/comment lines cleanly in `_has_jekyll_exclude` / `_append_jekyll_list_item`.
* **Drop `rpg_root` & bulk PDF scanning (`scripts/generate_digests.py`)**: Remove `rpg_root = drive_dir.parents[1]` (lines 112 and 376) and bulk `drive_dir.rglob("*.pdf")` (`find_pdf()` line 280). Require explicit `<pdf_path>` arguments outside the repository (Pillar 3) and record portable relative/filename `source_pdf` entries.

### Stage B — Phase 2 LAN Preview (Occam's Razor Docs) & ADR Amendment

* **Zero wrapper code (`No oude serve`, `No _config_dev.yml.template`)**: Inspecting `jekyll/_includes/image_gallery.html:13-18` and `jekyll/_includes/connected_to.html:37-42` shows `use_wsrv` (the sole consumer of `site.url`) only activates when `jekyll.environment == "production"` and `site.url` is non-localhost. Because `jekyll serve` runs in `development` mode by default and internal links use `| relative_url`, leaving production `url:` intact in `_config.yml` works on LAN without a dev YAML overlay or Python CLI wrapper.
* **ADR 003 & `README.md` updates**: Amend ADR 003 §3.4/§3.5/§5 to replace `oude serve` / `_config_dev.yml.template` with the documented command `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` (single active vault at a time on port `4000`) plus `oude digest` + `skills/digest-book/` replacing `oude digest-deep`. Update `README.md` (lines 96–101 and surrounding onboarding steps) with this LAN command, `avahi-daemon` host notes (`http://artemis.local:4000`), and non-mDNS IP fallback (`http://<artemis-ip>:4000`).

### Stage C — Hybrid PDF Extraction, Hard-Invariant Validation, `skills/digest-book/`, & Empirical Testing

* **Hybrid `--extract <pdf_path>` (`scripts/generate_digests.py`)**: Uses existing `pypdf` (`extract_pdf_outline()`, falling back to bounded page ranges when outline-less) to emit bounded staging slices so raw 50 MB PDFs never enter agent context monolithically:
  * *Default (`--format text`)*: Extracts UTF-8 slices via `page.extract_text(extraction_mode="layout")`, prefixed with explicit `--- Page X ---` markers and split below ~40 KB per file (`read_file` limit is 800 lines / 46,080 bytes).
  * *Scanned/table mode (`--format pdf`, or automatic per-slice fallback when extracted character density falls below threshold)*: Uses `pypdf.PdfWriter` to emit small bounded `.pdf` page-range slices into a temporary staging directory for visual or OCR readers.
* **Deterministic hard-invariant validator (`--validate`) & index parity**: Validates YAML frontmatter keys (`source`, `tier`, `entity_type`, `title`), blank line immediately after every Markdown heading, and existing relative Markdown link targets; restores the `source` property in `.agents/context/references.json` (`compile_references()`) to match ADR 003 §3.5.4. Soft heuristics (`30–120` line counts, nine-folder split rules) remain skill guidance rather than hard validator failures.
* **Harness-agnostic `skills/digest-book/SKILL.md` & Empirical Validation**: Authors the purely procedural skill per `AGENTS.md` §1 (zero hardcoded `/vibe-execute`, model names, or LLM SDKs), reading `--extract` slices, writing `_gm-materials/digests/<source>/` notes (`_index.md`, `factions/`, `locations/`, `people/`, `creatures/`, `artefacts/`, `mechanics/`, `tables/`, `other/`), and running `--validate` + `compile_references()`. Validate end-to-end against full *BF1 Morgansfort* and *Eclipse Phase (1st Edition)*.

### Stage D — Reconciled Vault Migration & Dynamic Gem Docs (`#22`)

* Publish `docs/MIGRATION_GUIDE.md` (step-by-step guide to move `hostile`/`charged` off Google Drive into git-ignored `_gm-materials/` + Obsidian Sync, set `drive_dir: .`, re-anchor `references.json`, and run `oude doctor` / `oude audit`) and `docs/DYNAMIC_GEM.md` (`oude-mechanismen` gem architecture, configuration, troubleshooting), linking both from root `AGENTS.md` and `README.md` whilst reconciling `bin/init_vault.sh` vs `oude init` and `sync.sh`.

### Data Flow

```text
Pillar 3 External PDF (<pdf_path>, outside Git & Obsidian Sync)
        │
        ▼
scripts/generate_digests.py --extract <pdf_path> [--format text|pdf]
  ├─ outline bookmarks (or page batches)
  ├─ text mode: pypdf layout extraction (--- Page X ---, <40 KB chunks)
  └─ --format pdf or low-text scanned fallback: pypdf.PdfWriter page slices
        │
        ▼
skills/digest-book/SKILL.md (harness-agnostic synthesis; optional user offload)
        │
        ▼  writes atomically per <source>
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
artemis ──▶ bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""
        ──▶ http://artemis.local:4000 (avahi-daemon) / http://<artemis-ip>:4000
        ──▶ ryu & mobile browsers (JEKYLL_ENV=development disables wsrv.nl)
```

### Repository Drift & Reconciliation Backlog

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
* **Reason for Rejection:** Rejected by author: inspecting `jekyll/_includes/image_gallery.html:13-18` and `jekyll/_includes/connected_to.html:37-42` confirms `wsrv.nl` (the sole consumer of `site.url`) is disabled outside `JEKYLL_ENV=production`, so `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` works cleanly without wrapper code or an overlay YAML file.

### Alternative B: Standalone LLM-Backed `oude digest-deep` CLI Command in Python

* **Pros:** Offers a single CLI command experience directly from the Python package.
* **Cons:** Forces LLM SDKs, API key configuration, and external provider coupling inside `oude-mechanismen`, contradicting the engine-agnostic contract in `AGENTS.md` §1.
* **Reason for Rejection:** Rejected by author: semantic Markdown synthesis belongs in the harness-agnostic `skills/digest-book/SKILL.md`, keeping `scripts/generate_digests.py` deterministic, offline, and testable in CI.

### Alternative C: Single-Format PDF Extraction (Split `.pdf` Only or Layout `.txt` Only)

* **Pros:** Simpler `--extract` implementation with only one output path to maintain.
* **Cons:** Split-only `.pdf` slices fail in text-only sessions lacking PDF vision/OCR support and hit binary read limits unless sliced thinly; layout-only `.txt` slices emit empty output on scanned PDFs and interleave complex boxed two-column RPG stat blocks.
* **Reason for Rejection:** Rejected by author: hybrid `--format text|pdf` with scanned-page auto-fallback preserves text portability across text-only sessions whilst providing lossless visual PDF slicing for scanned or table-dense chapters (with only the scanned-page density threshold tuned empirically in Stage C).

### Alternative D: Hard-Failing Deterministic Validator on Soft Prose Heuristics (`30–120` Line Cap & Mandatory Nine-Folder Taxonomy)

* **Pros:** Enforces uniform note sizing and directory layouts mechanically.
* **Cons:** Produces brittle build failures on legitimate short rollable tables or focused single-subsystem modules, coupling CI checks to prose length rather than structural integrity.
* **Reason for Rejection:** Rejected by author: deterministic validation stays restricted to hard structural invariants—valid YAML frontmatter, blank lines immediately after headings, resolvable relative Markdown link targets, and clean `.agents/context/references.json` schemas—whilst keeping soft sizing heuristics as guidance inside `skills/digest-book/SKILL.md`.

### Alternative E: Monolithic Single Implementation PR Across Stages A–D

* **Pros:** Ships all ADR 003 completion work in one review cycle.
* **Cons:** Couples straightforward Phase 1 bug fixes (`#36`, `#37`, `#39`) and Phase 2 documentation updates to Stage C's empirical PDF extraction validation and Stage D's migration guides, slowing delivery and inflating PR review scope.
* **Reason for Rejection:** Rejected by author: four decoupled PRs (Stages A–D) allow Phase 1 fixes and Phase 2 docs to land immediately whilst Stage C tooling validation and Stage D `#22` documentation proceed independently.

## Non-Functional Requirements

* **Security & Privacy (LAN Exposure & Air-Gap)**: Binding Jekyll to `--host 0.0.0.0` exposes compiled Tier 1 pages without authentication across the active local network interface; this remains safe only whilst `_gm-materials/` and `.agents/` stay excluded by `_config.yml` `exclude:` and `jekyll/_plugins/data_extractor.rb` (verified by `oude doctor`). Tier 0 raw recordings and verbatim transcripts remain confined to local disk (`~/Private/rpg-sessions/`).
* **Engine Agnosticism & Determinism**: No setting lore, LLM SDKs, API keys, model identifiers, or harness-specific dispatch commands (such as `/vibe-execute`) may appear in `oude-mechanismen` Python modules or `skills/digest-book/SKILL.md`. All `scripts/generate_digests.py` sub-commands (`--extract`, `--validate`, `compile_references()`, `--scaffold`) execute offline and deterministically for CI testing.
* **Portability & Bounded Context**: `.agents/context/references.json` records only portable POSIX relative paths or basenames (`source_pdf`), never host-specific `rpg_root` prefixes or OS absolute paths. Text slices emitted by `--extract` remain capped below `38,000` bytes (`read_file` ceiling: `800` lines / `46,080` bytes) and stage into a directory outside Git and Obsidian Sync.
* **Single-Vault Preview & Rollout Safety**: Only one vault is served on port `4000` at a time. Splitting delivery into four additive Stages (`A`–`D`) ensures Phase 1 bug fixes (`#36`, `#37`, `#39`) and docs are independently revertible without disturbing Tier 3 migration or empirical PDF work.

## Detailed Implementation Plan

### APIs, CLI Flags & Extraction Schemas

1. **`scripts/generate_digests.py` (`oude digest`) Contract**:
   - **External `<pdf_path>` & Portability**: Both `--scaffold <PDF_PATH>` and `--extract <PDF_PATH>` resolve `<PDF_PATH>` explicitly (`Path.expanduser().resolve()`); missing files raise `FileNotFoundError`. Optional `--source-pdf <REL_OR_NAME>` sets the canonical portable identifier recorded in frontmatter and `.agents/context/references.json`; if omitted, external Pillar 3 paths default to `pdf_path.name` and in-vault paths use `pdf_path.relative_to(drive_dir).as_posix()`. Remove `rpg_root = drive_dir.parents[1]` and `drive_dir.rglob("*.pdf")` (`find_pdf()`).
   - **Extraction CLI (`--extract <PDF_PATH>`)**:
     - Flags: `--format {auto,text,pdf}` (default `auto`), `--out-dir <DIR>` (defaults to `<system_temp>/oude-extract/<slug>` outside the repository), `--max-depth <N>` (default `1`), `--chunk-pages <N>` (default `10` when PDF has no outline), `--pdf-slice-pages <N>` (default `5`), `--max-bytes <N>` (default `38000`), `--min-chars-per-page <N>` (default `80`, calibrated empirically in Stage C).
     - Emits slice files plus `<out_dir>/manifest.json` adhering to:
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
     - In `text` / `auto` mode, page extraction uses `page.extract_text(extraction_mode="layout")` with `--- Page <N> ---` markers; when `char_count / page_count < min_chars_per_page` (or `--format pdf`), `pypdf.PdfWriter` splits `<= pdf_slice_pages` `.pdf` chunks instead.
   - **Hard-Invariant Validator (`--validate [<DIGEST_DIR>]`)**:
     - Defaults `<DIGEST_DIR>` to `<drive_dir>/_gm-materials/digests`. Checks every `*.md` file recursively, returning exit code `0` on pass or `1` with `file:line: <reason>` diagnostics on failure:
       1. Valid YAML mapping frontmatter containing `source` (non-empty `str`), `tier == 3`, `entity_type` in `{index, faction, location, person, creature, artefact, mechanic, table, other}`, and `title` (non-empty `str`).
       2. Every Markdown heading (`#`–`######`, outside fenced code blocks) followed immediately by an empty blank line.
       3. Every relative Markdown link target (excluding `http://`, `https://`, `mailto:`, and pure `#fragment` links, stripping `#fragment` before resolution) resolves to an existing file inside `<drive_dir>/_gm-materials/digests/`.
     - Emits non-fatal `[INFO]` stats for note line counts; never fails on soft `30–120` line counts or subset category directories.
   - **Index Parity (`compile_references()`)**: Copy optional `"source"` into `.agents/context/references.json` alongside `("entity_type", "pages", "tags")`, and preserve `body = content` / `fm_prefix = ""` whenever leading `---` does not parse as a YAML mapping (`#39`).

### Target Files to Create / Modify (Stages A–D)

#### 1. `scripts/audit_coverage.py` ([Modify] — Stage A, `#36`, `#39`)

* **Scope / Rationale**: Update `resolve_unindexed_file_action()` (`L130`) to suggest `oude digest --scaffold "{rel}"` instead of the deleted `.agents/scripts/generate_digests.py` path; align `resolve_drive_dir()` (`L52`) with `yaml.safe_load` / consistent edge handling (`#39`); remove obsolete Google Drive phrasing (`L722` and helpers).

#### 2. `scripts/transcribe_session.py` ([Modify] — Stage A, `#39`)

* **Scope / Rationale**: Re-raise non-YAML read failures (`OSError`, `UnicodeDecodeError`) inside `find_drive_dir()` (`L57-95`) instead of silently falling back to `repo_root`, and remove legacy Google Drive docstrings/help wording (`L12`, `L575`, `L648`).

#### 3. `src/oude_mechanismen/cli.py` ([Modify] — Stage A, `#39`)

* **Scope / Rationale**: Update `_has_jekyll_exclude()` (`L338`) and `_append_jekyll_list_item()` (`L301`) to tolerate CRLF (`\r\n`) endings and blank/comment lines inside YAML `exclude:` blocks so `oude doctor` handles Windows/macOS/Linux edits reliably.

#### 4. `templates/AGENTS.md.template` & `templates/tier1_sources.yml.template` ([Modify] — Stage A, `#37`)

* **Scope / Rationale**: Replace the deleted `ruby --disable-gems _plugins/data_extractor.rb` instruction (`templates/AGENTS.md.template:53`) with `bundle exec jekyll build` / `oude doctor --fix`; clarify `drive_dir` (`templates/tier1_sources.yml.template:10-12`) as the portable repository-root default (`.` alias).

#### 5. `scripts/generate_digests.py` ([Modify] — Stage A & Stage C)

* **Scope / Rationale**: In Stage A, propagate non-YAML read errors in `find_drive_dir()`, guard thematic-break `---` slicing in `compile_references()`, and strip `rpg_root = drive_dir.parents[1]` (`L112`, `L172-173`, `L376-378`) plus `find_pdf()` `drive_dir.rglob("*.pdf")` (`L280`), taking explicit `<pdf_path>`. In Stage C, add `--extract`, `--validate`, `--source-pdf`, `manifest.json` emission, and `"source"` output parity in `compile_references()`.

#### 6. `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md` & `README.md` ([Modify] — Stage B)

* **Scope / Rationale**: Amend ADR 003 §3.4, §3.5, and §5 to reflect Occam's razor LAN preview (`bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""`, dropping `oude serve` and `_config_dev.yml.template`) and deterministic `oude digest` + `skills/digest-book/` replacing `oude digest-deep`. Update `README.md` (`L87-113`) from legacy `./sync.sh --init` and localhost-only serving to `oude init`, `_gm-materials/`, LAN `http://artemis.local:4000`, `avahi-daemon`, and non-mDNS IP fallback.

#### 7. `skills/digest-book/SKILL.md` ([Create] — Stage C)

* **Scope / Rationale**: Author a setting- and harness-agnostic procedural skill compliant with `AGENTS.md` §6 (British English, heading blank lines, YAML frontmatter `name`, `description`, `argument-hint`) containing zero hardcoded `/vibe-execute` or LLM SDK dependencies. Documents consuming `oude digest --extract`, synthesising atomic `_gm-materials/digests/<source>/` notes matching ADR 003 §3.5 schema, and running `--validate` + `oude digest`.

#### 8. `skills/lookup-context/SKILL.md` ([Modify] — Stage C)

* **Scope / Rationale**: Add concise 3-hop progressive navigation guidance (`_index.md` → targeted entity note via `digest_path` → annotated relative links) and note `source` field matching in `.agents/context/references.json`.

#### 9. `tests/test_audit_coverage.py`, `tests/test_generate_digests.py`, `tests/test_transcribe_session.py`, `tests/test_cli.py` ([Modify] — Stage A & Stage C)

* **Scope / Rationale**: Update existing assertions (`oude digest --scaffold`, `rpg_root` removal, thematic-break `---` guard) and add coverage for non-YAML read propagation, CRLF/blank-line YAML `exclude:` parsing, `--extract` (`text`, `pdf`, `auto` density fallback, `manifest.json`), `--validate` pass/fail diagnostics, and `"source"` field emission in `references.json`.

#### 10. `docs/MIGRATION_GUIDE.md` & `docs/DYNAMIC_GEM.md` ([Create] — Stage D, `#22`)

* **Scope / Rationale**: Provide the reconciled step-by-step Google Drive → `_gm-materials/` + Obsidian Sync checklist (`drive_dir: .`, `references.json` re-indexing, `hostile`/`charged` cutover, `oude doctor --fix` + `oude audit` validation) and full `oude-mechanismen` RubyGem operator/customisation guide (reconciling `#22`'s `jekyll/DYNAMIC_GEM.md` vs `docs/` placement).

#### 11. `AGENTS.md`, `sync.sh`, `bin/init_vault.sh`, `tests/test_init_vault.py`, `.github/workflows/ci.yml` ([Modify] — Stage D)

* **Scope / Rationale**: Update `AGENTS.md` (`L119` gem indexing reference, §5 `sync.sh` scope note, relative links `./docs/MIGRATION_GUIDE.md` and `./docs/DYNAMIC_GEM.md`), link both guides from `README.md`, remove conflicting `.agents/scripts/` runner mappings (`L76-81`) from `sync.sh` `MANAGED_FILES`, mark `bin/init_vault.sh` formally deprecated in favour of `oude init` whilst keeping CI shellcheck passing, and extend `.github/workflows/ci.yml`'s heading-spacing check cleanly across `docs/*.md`.

### Verification Plan

* **Unit & Integration Test Suite**: Run `"$HOME/.local/bin/uv" run --no-project --with pyyaml --with pypdf --with pytest pytest -v -o cache_dir=/tmp/pytest_cache_oude` after Stage A and Stage C edits; require 100% passing assertions with zero skipped regressions.
* **Shell, Ruby & Markdown Hygiene**: Verify CI parity checks locally (`ruby -c` on `jekyll/_plugins/*.rb` and `lib/*.rb`, `bash -n` on `sync.sh` and `bin/init_vault.sh`, and CI heading-blank-line validation across `skills/*/SKILL.md`, `docs/*.md`, `README.md`, `AGENTS.md`).
* **Empirical Stage C Book Validation**: Run `oude digest --extract`, skill-guided wiki synthesis (including user-selected `/vibe-execute` model offload outside `SKILL.md` for full-book throughput), `oude digest --validate`, and `compile_references()` against *BF1 Morgansfort* and *Eclipse Phase (1st Edition)* in a non-committed local scratch vault; verify Markdown table survival, exact `--min-chars-per-page` auto-fallback threshold calibration, zero `--validate` failures, and lean `.agents/context/references.json` indexing.
* **Manual LAN Preview Smoke Check**: Start `bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""` from `artemis` on a migrated vault (`hostile` or `charged`) and verify live rendering, `relative_url` links, and gallery images load cleanly from `ryu` and mobile at `http://artemis.local:4000` (and `http://<artemis-ip>:4000`).

*Drafted with EGM*
