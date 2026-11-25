# Tier 2 Canon Structure, Supersession Tracking, and Faction-Turn Records

* **Author:** `efsalvarenga`
* **Status:** Proposed (Post-Review Revision — Round 2 Resolved)
* **Date:** 2026-11-25
* **Addresses:** [#117](https://github.com/terra-campaigns/oude-mechanismen/issues/117)
* **Review Records:** [003_goldfish_review_117.md](../reviews/003_goldfish_review_117.md), [004_design_006_egm_review.md](../reviews/004_design_006_egm_review.md)

---

## Overview

`oude-mechanismen` (invoked via the `oude` Python CLI) is the shared procedural engine for tabletop RPG campaign vaults — Obsidian Markdown knowledge bases published as Jekyll static sites (such as the maintainer's two active campaign vaults, `charged` and `hostile`). In those vaults, Tier 2 canon currently sits as unstructured prose bullets in `.agents/context/decisions.md` (tracked in public Git, inside the vault's `.agents/context/` configuration and derived-cache directory) alongside AI-extracted session notes in `_gm-materials/session-summaries/`. Behind-the-screen Game Master (GM) world-state decisions — specifically off-screen faction-turn outcomes produced by the independent TOME simulation engine — have no dedicated private home, schema, stable identifier, supersession validation, or derived index.

This design introduces a structured Markdown format for Tier 2 rulings and faction-turn records under `_gm-materials/rulings/` and adds optional stable Tier 1 `id:` fields indexed by `jekyll/_plugins/data_extractor.rb`. A single pass-through script (`oude tier2`, dispatching `scripts/tier2.py` via `PASS_THROUGH_SCRIPTS` in `src/oude_mechanismen/cli.py`) builds a derived local index at `_gm-materials/.cache/tier2.json`, and deterministic validation integrates into `scripts/lint_wiki.py` and `oude doctor`. `oude-mechanismen` and `tome` remain independent applications with no shared runtime dependency.

### Clarified Four-Tier Canon Model vs. Storage Pillars

This design formalises the separation between **narrative authority (Canon Tiers 0–3)** and **physical storage / privacy boundaries (Storage Pillars 0–3 from [ADR 003](../adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md))**:

* **Tier 0 — Raw Table Evidence (Pillar 0, `~/Private/rpg-sessions/`):** Raw session recordings and verbatim transcripts. Exposed at the table, kept strictly local on disk for player privacy.
* **Tier 1 — Verified Exposed Canon (Pillar 1, public Git: `include_paths` from `.agents/context/tier1_sources.yml` — template default in `templates/tier1_sources.yml.template`: `campaigns/`, `directory/`, `systems/` for campaign rules and subsystems, and `trading/`; engine code fallback when the YAML file is absent: additionally `statblocks/` per `jekyll/_plugins/data_extractor.rb:186` and `scripts/tier2.py:49-50`):** GM-verified, player-facing published notes, including published common world knowledge ("who is the king?"). Outranks all other tiers; changing it is a retcon.
* **Tier 2 — Behind-the-Screen Working Canon & Unverified Records (Pillar 2, `_gm-materials/`, plus the gitignored derived `.agents/context/rolling_glossary.md`):** Confirmed behind-the-screen GM rulings and faction-turn records (`_gm-materials/rulings/`) plus AI-extracted, not line-by-line GM-verified session notes (`_gm-materials/session-summaries/`), alongside `.agents/context/rolling_glossary.md` (unverified session-new terminology awaiting promotion to Tier 1). Outranked by Tier 1; outranks Tier 3.
* **Tier 3 — Defined Campaign Influences & Unplayed Prep (Pillar 2, `_gm-materials/`):** Distilled reference wikis (`_gm-materials/digests/`) and unplayed session preparation notes (`_gm-materials/session-preps/`). Commercial sourcebook PDFs (Pillar 3) sit outside Tier 3 as an external inspiration archive until distilled into the campaign's defined influence scope.

### Terminology

* **Obsidian & campaign vault:** Obsidian is the local Markdown editor and graph viewer used to author campaign notes; a *campaign vault* is a Git repository serving as both an Obsidian vault and a Jekyll static website. *Obsidian Sync* synchronises `_gm-materials/` peer-to-peer between the GM's two workstations: `ryu` (macOS tabletop laptop) and `artemis` (Debian Linux production workstation).
* **GM / NPC:** Game Master (campaign referee) and Non-Player Character.
* **Skill & pass-through script:** A *skill* is a procedural agent instruction file at `skills/<name>/SKILL.md`. A *pass-through script* is a standalone Python tool under `scripts/` invoked directly by `oude <cmd>` via `PASS_THROUGH_SCRIPTS` in `src/oude_mechanismen/cli.py`.
* **3-Gate Pre-Publishing Protocol & `lint-wiki` modes:** The engine's publishing checklist consisting of Gate 1 (`scripts/lint_chapter.py` prose-cadence and formatting linter), Gate 2 (`skills/review-style/SKILL.md` voice review), and Gate 3 (`scripts/lint_wiki.py` / `oude lint-wiki` deterministic structural wiki linter). `oude lint-wiki` runs either in *full mode* (no paths passed; scans the whole vault) or *targeted mode* (explicit file/directory paths passed; runs file-level checks and records omitted repo-wide checks in `checks_skipped`).
* **EGM / Goldfish review:** The Elephant-Goldfish Model design review process, where isolated fresh-context subagents (*Goldfishes*) audit a specification across specialised lenses without conversation history.
* **TOME (TriO Matrix Engine — TriO is the trinary Obvious/Option/Odd posture scale):** An independent multi-actor tabletop simulation engine that resolves off-screen moves between campaign factions, producing one new world-state fact per turn. `oude-mechanismen` does not import, wrap, or invoke TOME.
* **Faction turn:** One resolved off-screen actor move (proposal, peer votes, resolution roll, and resulting world-state fact).
* **TriO posture tier:** An external narrative posture cue used by TOME (for example, `Obvious`, `Option`, or `Odd`). Treated as optional freeform metadata in `oude`, not a hardcoded enum.
* **Spark tags:** Creative prompt cues drawn during a faction turn (stored as optional freeform strings).
* **Vote and shifted:** During peer evaluation, each non-active actor casts an integer `vote` (`-1`, `0`, or `+1`) and records `shifted` (`true`/`false`) to mark whether it shifted its baseline plausibility assessment by citing an existing canon fact.
* **ID grammar:** Ruling IDs use zero-padded sequential identifiers (`R-NNN`, matching `^R-[0-9]{3,}$`, e.g. `R-001`, `R-004`). Tier 1 entity IDs and behind-the-screen actor slugs use lowercase identifiers matching `^[a-z0-9][a-z0-9_-]*$` (e.g. `sigisfarne`, `piot_chant`, `iron_pot_6_body`).

## The Problem

Running live campaigns (`charged`, `hostile`) with `oude-mechanismen` exposed five concrete operational gaps in how Tier 2 canon is documented and verified:

1. **Behind-the-screen spoilers sit in public Git:** `.agents/context/decisions.md` is tracked in public repositories (`terra-campaigns/charged`, `terra-campaigns/hostile`) alongside static style conventions, exposing unpublished GM world state (such as covert contracts and off-screen NPC intentions) to players who inspect GitHub.
2. **No home or process for faction-turn outcomes and actor opinions:** Off-screen faction turns run in TOME are real behind-the-screen world canon (not Tier 1 exposed play and not Tier 3 uncommitted reference material), yet no folder, schema, or workflow exists to store their established facts and private actor votes/opinions so they enrich session prep, session write-ups, and future faction turns.
3. **Unstructured prose blocks deterministic tracking and conflict surfacing:** Freeform Markdown bullets in `decisions.md` lack IDs, entity references, and machine-readable lifecycle state. Retractions and supersessions appear only as inline prose (such as `**[Retracted 2026-11-07: ...]**`), so humans and agents easily overlook them and tooling cannot check new faction-turn outcomes against older rulings.
4. **Tier 2 is invisible to engine tooling:** `catalog.json` indexes Tier 1 (plus `rolling_glossary.md`), `references.json` indexes Tier 3 digests, and `oude lint-wiki` / `oude doctor` ignore Tier 2 rulings completely. Agents must read the whole `decisions.md` file in prose and receive no automated signal when rulings conflict, go stale, or break links.
5. **Documentation tier drift:** Root `AGENTS.md` and `skills/scribe-session/SKILL.md` still classify unplayed `_gm-materials/session-preps/` as Tier 2 rather than Tier 3, blurring the boundary between confirmed off-screen canon and unplayed prep options.

## Goals

* Define a single canonical YAML front matter + narrative Markdown schema for Tier 2 rulings and faction-turn records under `_gm-materials/rulings/`, preserving existing `_gm-materials/session-summaries/`, `_gm-materials/session-preps/`, and `_gm-materials/digests/` paths untouched.
* Support structured YAML `opinions` and optional freeform `turn` metadata directly inside ruling YAML front matter so every record parses in a single `yaml.safe_load()` pass while remaining readable in Obsidian (Source Mode for properties).
* Preserve private behind-the-screen actor `opinions` across ruling lifecycle transitions (`active → superseded | retracted | promoted`, with terminal lifecycle states immutable) without creating a duplicate Tier 2 gazetteer or per-actor mirror files.
* Add optional explicit Tier 1 `id:` fields indexed by `jekyll/_plugins/data_extractor.rb` into `.agents/context/catalog.json` (with uniqueness enforced by `lint_wiki.py` and no filename fallback), enabling compile-time left-join resolution of Tier 2 entity/actor slugs without a separate mapping file.
* Provide one pass-through script `scripts/tier2.py` (`oude tier2`) that compiles an entries-only derived index (`{schema_version, generated, catalog_sha, entries[]}`) to `_gm-materials/.cache/tier2.json`, derives `superseded_by: []`, resolves Tier 1 entity paths, and reports active-entity overlap advisories and unresolved-slug warnings.
* Integrate deterministic ruling validation (`check_rulings()`) into `scripts/lint_wiki.py` (executed when `_gm-materials/rulings/` contains ruling files locally; skipped cleanly on CI runners where `_gm-materials/` is absent), verifying schema validity, unique ruling IDs, DAG acyclicity, single active successor, status-to-partner-field invariants, valid `promoted_to` Tier 1 paths, fail-loud `opinions` validation, and index freshness (including `catalog.json` staleness).
* Protect `_gm-materials/.cache/tier2.json` via `DERIVED_CACHE_FILES`, an uncommented entry in `DEFAULT_GITIGNORE`, and `oude doctor`, and add an advisory check when legacy `.agents/context/decisions.md` coexists with `_gm-materials/rulings/`.
* Execute an atomic cutover retiring `.agents/context/decisions.md` across `oude init`, `scripts/transcribe_session.py`, `scripts/scribe_session.py`, and all five affected skills (`lookup-context`, `prep-session`, `weave-threads`, `scribe-session`, `lint-wiki`), and correct `session-preps/` tier classification in `AGENTS.md` and `skills/scribe-session/SKILL.md`.

## Non-Goals

* Running, wrapping, or parsing TOME engine outputs via `oude` CLI (`oude` and `tome` remain independent applications with no shared runtime dependency).
* Archiving raw TOME `state.json` or `log.jsonl` snapshots inside the campaign vault.
* Adding a multi-subcommand `oude tier2` CLI family or dedicated terminal query commands (such as `oude tier2 actor <id>`).
* Moving or renaming existing `_gm-materials/session-summaries/`, `_gm-materials/session-preps/`, or `_gm-materials/digests/` directories.
* Creating a Tier 2 gazetteer mirroring `directory/` or splitting actor opinions into per-actor private files.
* Storing behind-the-screen Tier 2 lore or actor stances inside `{% comment %}` blocks of published `directory/` files.
* Adding new token-budget enforcement rules, deterministic Tier-1-prose-vs.-Tier-2 contradiction detection, or automated LLM-based semantic contradiction checks inside `lint_wiki.py`.
* Rewriting public Git history in `charged` or `hostile` to purge past `.agents/context/decisions.md` commits.

## Open Questions

None. All architectural and operational decisions from brainstorming, [003_goldfish_review_117.md](../reviews/003_goldfish_review_117.md), and [004_design_006_egm_review.md](../reviews/004_design_006_egm_review.md) are resolved in the Technical Plan below.

## Critical User Journeys (CUJs)

### CUJ 1: Recording a Faction-Turn Outcome and Surfacing Entity Overlaps

* **Given**: A campaign vault (`charged`) with Tier 1 notes indexed in `.agents/context/catalog.json` (carrying optional explicit `id:` fields on referenced entities), `_gm-materials/rulings/` present on disk, and an existing active ruling `R-003` referencing `sigisfarne`.
* **When**: The GM runs an off-screen faction turn in TOME independently, authors (or has an agent author) `_gm-materials/rulings/R-004_sigisfarne_tribute.md` with YAML front matter (`kind: faction-turn`, `status: active`, `fact`, `entities`, `actors`, optional `turn`, and `opinions`) plus narrative body, and runs `oude tier2`.
* **Then**: `oude tier2` compiles `_gm-materials/.cache/tier2.json` locally (target under 50 ms for ~100 rulings), resolves known Tier 1 `id`s to their vault-relative paths in `resolved_entities`, prints an advisory listing `R-003` as an active ruling sharing `sigisfarne` (so the GM immediately evaluates whether `R-004` supersedes `R-003`), and emits an advisory `WARN` for any actor slug not yet present in `catalog.json` (such as `piot_chant`).

### CUJ 2: Superseding or Promoting a Ruling Without Losing Private Actor Opinions

* **Given**: Active faction-turn ruling `R-004` in `_gm-materials/rulings/` containing private behind-the-screen peer `opinions`, and either (a) a subsequent session chapter `campaigns/arc/ep_014.md` exposes `R-004`'s outcome at the table, or (b) a newer ruling `R-007` overrides `R-004`.
* **When**: In case (a), the GM sets `status: promoted` and `promoted_to: campaigns/arc/ep_014.md` on `R-004`; in case (b), the GM adds `supersedes: [R-004]` on `R-007` and sets `status: superseded` on `R-004`. The GM runs `oude tier2` and `oude lint-wiki`.
* **Then**: `tier2.json` reflects `R-004`'s terminal status (and derived `superseded_by: [R-007]` in case (b)), `oude lint-wiki` confirms DAG acyclicity, single active successor, and status-to-partner-field invariants with zero failures, routine prep and lookup filter to `status: active` facts, and future faction-turn preparation still discovers `R-004` via `actors` in `tier2.json` and reads its retained `opinions` from disk.

### CUJ 3: Publishing a Behind-the-Screen Actor to Tier 1 Without Editing Historical Rulings

* **Given**: Several past Tier 2 rulings reference behind-the-screen actor slug `piot_chant`, which previously had no Tier 1 note (`resolved_entities["piot_chant"] == null`).
* **When**: Players encounter the Piot Chants in play, the GM publishes `directory/PiotChants/index.md` with `id: piot_chant` in its YAML front matter, rebuilds `catalog.json` (`bundle exec jekyll build`), and runs `oude tier2`.
* **Then**: Every historical and active entry in `_gm-materials/.cache/tier2.json` referencing `piot_chant` automatically resolves `resolved_entities["piot_chant"] = "directory/PiotChants/index.md"` (with updated `catalog_sha`) without editing any historical ruling file or maintaining a separate actor mapping file. If `oude lint-wiki` runs before `oude tier2`, the `catalog_sha` mismatch flags `tier2.json` as stale (`FAIL`).

### CUJ 4: Migrating an Existing Vault Off `.agents/context/decisions.md` and Running Public CI

* **Given**: An existing public campaign vault (`charged` or `hostile`) containing `.agents/context/decisions.md` with a mix of static style conventions and mutable world-state rulings, synced between `ryu` and `artemis` via Obsidian Sync.
* **When**: The GM moves static conventions into `.agents/AGENTS.md`, moves mutable rulings into `_gm-materials/rulings/`, removes `.agents/context/decisions.md`, runs `oude doctor --fix`, `oude tier2`, and `oude lint-wiki` locally, and pushes public Tier 1 changes to GitHub Actions CI (where `_gm-materials/` is absent).
* **Then**: Locally, `oude doctor` confirms `_gm-materials/.cache/tier2.json` is gitignored and untracked, `oude lint-wiki` validates all rulings and Tier 1 `id:` uniqueness, and Obsidian Sync replicates `_gm-materials/rulings/*.md` while skipping `_gm-materials/.cache/tier2.json` under default hidden-files settings. On public CI runners where `_gm-materials/` is absent, `oude lint-wiki` skips `check_rulings()` cleanly with zero false failures, and zero private Tier 2 data exists in the public Git tree.

## Technical Plan (Architecture)

The architecture adds one private source directory (`_gm-materials/rulings/`), one derived local index (`_gm-materials/.cache/tier2.json`), one optional Tier 1 front-matter key (`id:`), and one pass-through Python module (`scripts/tier2.py`) shared between `oude tier2`, `scripts/lint_wiki.py`, `scripts/transcribe_session.py`, and `scripts/scribe_session.py`.

### System Data Flow

```text
Pillar 1 (Public Git)                              Pillar 2 (gitignored, Obsidian Sync)
─────────────────────                              ────────────────────────────────────
Tier 1 notes (`include_paths`)                     _gm-materials/rulings/*.md
  (optional explicit YAML `id:`)                     (authored by GM or agent;
        │                                             YAML front matter + narrative body)
        ▼                                                        │
jekyll/_plugins/data_extractor.rb                                │
        │ writes                                                 ▼
        ▼                                          scripts/tier2.py (`oude tier2`)
.agents/context/catalog.json ───── left-join ────→   ├─ validate schema, opinions, DAG
  (Tier 1 entries + `id`)           on `id`          ├─ derive `superseded_by: []`
  + `catalog_sha` fingerprint                        ├─ resolve `entities`/`actors` → path|null
                                                     ├─ print active-entity overlap advisories
                                                     └─ atomic write (when changed)
                                                                 │
                                                                 ▼
                                                   _gm-materials/.cache/tier2.json
                                                     (dot-folder skipped by default Obsidian
                                                      hidden-files sync; four-layer excluded
                                                      from Git & Jekyll)
                                                                 │
                     ┌───────────────────────────────────────────┴───────────────────────┐
                     ▼                                                                   ▼
  Validation & Health (Local; skipped on CI when _gm-materials/ absent)    Consumers (Human & Agent)
  ├─ scripts/lint_wiki.py (`oude lint-wiki`, Gate 3)                       ├─ lookup-context / prep-session /
  │    ├─ check_duplicate_ids() on Tier 1 `id:`                            │  weave-threads / scribe-session /
  │    └─ check_rulings() via scripts/tier2.py + compile diff              │  lint-wiki skills
  └─ src/oude_mechanismen/cli.py (`oude doctor`)                           ├─ transcribe_session.py & scribe_session.py
       ├─ git ls-files guard on DERIVED_CACHE_FILES                        │  reading rulings/*.md directly via
       ├─ legacy decisions.md advisory (never auto-deleted)                │  load_active_rulings_text()
       └─ refresh tier2.json on `--fix` when rulings exist                 └─ GM/agent assembling inputs for
                                                                              independent TOME faction turns
```

### Component 1: Optional Stable Tier 1 `id:` Indexing

* **`jekyll/_plugins/data_extractor.rb`:** Add `"id" => raw_id` to each entry in `.agents/context/catalog.json`, where `raw_id` is `fm['id'].to_s.strip` when present and non-empty, or `nil` otherwise. No fallback to filename or path is computed so renaming or moving a Tier 1 note never silently changes an ID.
* **Grammar & uniqueness (`scripts/lint_wiki.py`):** Add `check_duplicate_ids(root, tier1_files, findings, check_duplicates=True)`:
  * If a Tier 1 note specifies `id:`, verify it is a string matching `^[a-z0-9][a-z0-9_-]*$` (`FAIL` under `front-matter` otherwise).
  * When `check_duplicates=True` (full mode), verify no two Tier 1 notes share the same `id:` (`FAIL` under `duplicate-id` listing all conflicting file paths).
* **Rollout:** `id:` is strictly optional on Tier 1 notes, avoiding a big-bang backfill across existing `charged` and `hostile` vaults; operators add `id:` progressively to entities referenced by Tier 2 rulings. Updating `data_extractor.rb` requires a RubyGem version bump when releasing.

### Component 2: Canonical Ruling Schema (`_gm-materials/rulings/*.md`)

Rulings reside as Markdown files (`*.md`, skipping dot-files) directly inside `_gm-materials/rulings/` (recommended filename convention `<id>_<slug>.md`; `lint_wiki.py` emits an advisory `WARN` if a ruling filename does not start with `f"{id}_"` so filename/front-matter mismatches are caught without blocking valid files). All machine-read metadata — including structured `opinions` and optional freeform `turn` metadata — lives in YAML front matter so every file parses in a single `yaml.safe_load()` pass while the Markdown body stays pure narrative prose.

| Front-matter field | Type | Required | Rules & invariants |
| :--- | :--- | :--- | :--- |
| `id` | `str` | Yes | Matches `^R-[0-9]{3,}$` (e.g. `R-004`). Unique across `_gm-materials/rulings/`. |
| `title` | `str` | Yes | Non-empty string. |
| `date` | `str \| date` | Yes | Real-world ISO date `YYYY-MM-DD` (normalised to ISO string in JSON; rejects `datetime`). |
| `in_world_date` | `str \| null` | No | Optional freeform campaign calendar label (intentionally unpinned to support arbitrary campaign calendars, e.g. `1025-12`; stringified if YAML parses a date; must be `str \| date \| null`). |
| `kind` | `str` | Yes | Enum: `ruling` or `faction-turn`. |
| `status` | `str` | Yes | Enum: `active`, `superseded`, `retracted`, or `promoted`. |
| `fact` | `str` | Yes | Non-empty 1–2 sentence canonical world-state statement. |
| `entities` | `list[str]` | Yes | List (may be empty) of slugs matching `^[a-z0-9][a-z0-9_-]*$`. |
| `actors` | `list[str]` | Conditional | Optional slug list for `ruling` (defaults to `[]`); required non-empty slug list for `faction-turn`. Every `opinions[].actor` must appear in `actors` (`FAIL` otherwise); compiled verbatim with no hidden union. |
| `supersedes` | `list[str]` | No | Defaults to `[]`; list of ruling IDs matching `^R-[0-9]{3,}$`. |
| `superseded_by` | *(forbidden)* | No | **Must not be authored** in front matter (`FAIL` if present); derived exclusively at compile time. |
| `promoted_to` | `str \| null` | Conditional | Required non-empty vault-relative path to an existing Tier 1 `.md` file (matching `include_paths` from `tier1_sources.yml`, outside `_gm-materials/` and `.agents/`) when `status == promoted`; must be `null`/absent otherwise. |
| `retraction_reason` | `str \| null` | Conditional | Required non-empty string when `status == retracted`; must be `null`/absent otherwise. |
| `turn` | `dict \| null` | No | Optional freeform mapping for engine-agnostic faction-turn metadata (e.g. `active_actor`, `trio_tier`, `spark_tags`, `roll`, `outcome`). No hardcoded TOME enum checks. |
| `opinions` | `list[dict]` | Conditional | Required non-empty list when `kind == faction-turn`; optional for `kind == ruling` (validated with identical item rules when present). |

Each element of `opinions` must be a mapping containing:

* `actor`: slug string matching `^[a-z0-9][a-z0-9_-]*$` (required; must be listed in the ruling's `actors` field — `FAIL` otherwise).
* `vote`: exact integer in `{-1, 0, 1}` (required; Python `bool` values are explicitly rejected since `isinstance(True, int)` is true).
* `shifted`: exact boolean `true` or `false` (required).
* `stance`: non-empty string (required).

Any malformed YAML, missing required key, wrong value type, invalid slug, or invalid opinion item causes a hard `FAIL` with file path and diagnostic message (zero silent drops).

### Component 3: Supersession State Machine & DAG Invariants

Lifecycle transitions follow a one-way graph with lifecycle-immutable terminal states (terminal rulings remain editable only for typo/editorial cleanup, never transitioned back to `active` or across terminal states):

```text
active → superseded   (referenced by at least one newer ruling's `supersedes` list)
active → promoted     (requires valid Tier 1 `promoted_to` path)
active → retracted    (requires non-empty `retraction_reason`)
```

Deterministic graph rules enforced by `scripts/tier2.py` and `scripts/lint_wiki.py`:

1. **No self-loops or dangling targets:** Every ID in `supersedes` must refer to a distinct existing ruling in `_gm-materials/rulings/` (`FAIL`).
2. **DAG acyclicity:** Depth-first 3-colour traversal over all `supersedes` edges must find zero cycles; any cycle emits `FAIL` showing the cycle path.
3. **Target status alignment:** Every ruling referenced by another ruling's `supersedes` list must have `status == superseded` (`FAIL` if `active`, `promoted`, or `retracted` — `promoted` and `retracted` rulings are invalid `supersedes` targets by design because exposed Tier 1 canon cannot be superseded by Tier 2 and retracted claims are withdrawn rather than replaced). Conversely, every ruling with `status == superseded` must be referenced by at least one other ruling's `supersedes` list (`FAIL` if orphaned).
4. **Status-to-partner-field matrix:**
   * `active` and `superseded`: `promoted_to` and `retraction_reason` must both be `null` or absent (`FAIL` otherwise); `supersedes` may be empty or non-empty.
   * `promoted`: `promoted_to` must resolve inside the vault root to an existing Tier 1 `.md` file; `retraction_reason` must be `null` or absent (`FAIL` otherwise). A `promoted` ruling may retain any historical `supersedes` list from when it was `active` so promoting a successor does not orphan the superseded ruling it replaced.
   * `retracted`: `retraction_reason` must be a non-empty string; `promoted_to` must be `null` or absent; `supersedes` must be empty (`[]`, `FAIL` otherwise — a withdrawn ruling cannot remain the supersessor of another ruling).
5. **Single active successor:** At most one `status == active` ruling may list a given target ID in `supersedes`; two or more active rulings superseding the same target emit `FAIL` (preventing un-reconciled forked replacements, per [003_goldfish_review_117.md](../reviews/003_goldfish_review_117.md)).

### Component 4: Pass-Through Compiler (`scripts/tier2.py` → `oude tier2`)

`scripts/tier2.py` is registered in `PASS_THROUGH_SCRIPTS` as `"tier2": "tier2.py"` (invoked as `oude tier2 [--root PATH]`, emitting plain text diagnostics and writing the JSON index directly). It serves both as the compiler CLI and as the single shared library imported by `lint_wiki.py`, `transcribe_session.py`, and `scribe_session.py` (each using the existing `sys.path.insert(0, str(Path(__file__).resolve().parent))` guard patterned after `scripts/scribe_session.py:27-30`).

1. **Discovery:** Scans `_gm-materials/rulings/*.md` (ignoring dot-files). If `_gm-materials/rulings/` does not exist or contains zero `.md` files, reports cleanly and exits `0` without creating directories or an empty cache unasked (matching ADR 003 on-demand subdirectory creation).
2. **Validation gate before write:** Runs full schema, `opinions`, and supersession DAG validation. If any `FAIL`-severity error exists, prints diagnostics and exits `1` without writing or corrupting `_gm-materials/.cache/tier2.json`.
3. **Compile-time left-join & inverse derivation:**
   * Loads `.agents/context/catalog.json` (when present) to build `id_to_path: Dict[str, str]` (skipping entries with `null`/empty `id`) and computes an 8-char SHA-256 `catalog_sha` over `catalog.json`'s raw bytes (`null` when `catalog.json` is absent).
   * Compiles `actors` verbatim (guaranteed to cover every `opinions[].actor` by validation) and populates `resolved_entities: {slug: id_to_path.get(slug)}` across the union of `entities` and `actors`.
   * Computes `superseded_by` (sorted list of ruling IDs) by inverting all `supersedes` edges.
   * Computes 8-char SHA-256 (`sha`) over each ruling's raw file bytes, matching `data_extractor.rb` and `lint_wiki.py`.
4. **Entries-only index write:** Writes `_gm-materials/.cache/tier2.json` with structure `{"schema_version": 1, "generated": "<ISO-8601>", "catalog_sha": "<8-char-sha-or-null>", "entries": [...]}` sorted by `id`, omitting full `opinions` prose so the index remains compact. Mirrors `data_extractor.rb`'s idempotent write guard (skips rewriting the file when everything except `generated` is unchanged) and writes atomically via a temporary file in `_gm-materials/.cache/` followed by `os.replace()`.
5. **Non-fatal advisories (exit `0`):**
   * **Active-entity overlaps:** Groups all `status == active` entries by each slug in `entities` and prints any slug touched by two or more active rulings (with their IDs and titles) so the operator evaluates potential supersession immediately.
   * **Unresolved slugs:** Lists any slug across `entities` and `actors` whose `resolved_entities[slug]` is `null` (surfaces typos without failing on behind-the-screen actors).
   * **Filename prefix mismatch:** Warns when a ruling filename does not begin with `f"{id}_"`.
6. **Shared active-rulings reader (`load_active_rulings_text(repo_root)`):** Consumed by `scripts/transcribe_session.py` and `scripts/scribe_session.py` (which invoke local Ollama `qwen2.5:14b` for Pass 2A tactical extraction and Pass 2B sensory extraction).
   * When `_gm-materials/rulings/` exists, `load_active_rulings_text()` runs `validate_rulings(repo_root)` directly against `_gm-materials/rulings/*.md` (bypassing `_gm-materials/.cache/tier2.json` so a stale cache can never inject outdated canon into session prompts; target under 50 ms for ~100 rulings). If any `FAIL`-severity diagnostic is present, it prints all `FAIL` diagnostics to stderr and raises `ValueError` (never silently skipping a malformed ruling). Otherwise it formats `- **<id> — <title>:** <fact>` lines for all `status == active` rulings sorted by `id`.
   * If the count of active rulings exceeds an advisory threshold (`ACTIVE_RULINGS_WARN_THRESHOLD = 50`), prints a `[WARN]` to stderr advising review/promotion without silently truncating active canon.
   * If `_gm-materials/rulings/` does not exist, it falls back read-only to legacy `.agents/context/decisions.md` (when present) so un-migrated vaults continue working during transition.

### Component 5: Linter & Doctor Integration

* **`scripts/lint_wiki.py` (Gate 3):**
  * Runs `check_duplicate_ids()` across scanned Tier 1 files in full mode (and validates `id:` syntax in both full and targeted modes).
  * Runs `check_rulings(root, findings)` in full mode (and in targeted mode when at least one raw CLI `paths` argument resolves inside `_gm-materials/rulings/`, evaluated *before* `_has_skipped_segment` filtering).
  * When `_gm-materials/rulings/` does not exist or contains zero `.md` files (for example on public CI runners where `_gm-materials/` is absent, or a fresh vault with an empty `rulings/` directory), `check_rulings()` returns cleanly with zero findings (preventing an unfixable missing-index `WARN`).
  * `check_rulings()` calls the shared validator in `scripts/tier2.py` (reporting `FAIL` / `WARN` findings under check name `rulings`) and verifies `_gm-materials/.cache/tier2.json` via a single compile-diff path (intentionally stricter than `check_catalogue()` because agents treat `tier2.json` as authoritative behind-the-screen world state):
    * Absent `_gm-materials/.cache/tier2.json` (when ≥1 ruling file exists) → `WARN` (`run oude tier2 or oude doctor --fix`).
    * Invalid JSON, non-dict payload, or unknown `schema_version != 1` → `FAIL`.
    * When validation produced no `FAIL` diagnostics, compute expected payload via `compile_tier2_index(root, write=False)` and compare against on-disk `tier2.json` ignoring `generated`: any difference (covering ruling `sha` drift, missing/extra ruling entries, derived `superseded_by` drift, or `catalog_sha` / `resolved_entities` drift after a `catalog.json` rebuild) → `FAIL` (`_gm-materials/.cache/tier2.json is stale; run oude tier2`).
  * Emits a `WARN` under `rulings` if both legacy `.agents/context/decisions.md` and `_gm-materials/rulings/` (non-empty) exist simultaneously.
* **`src/oude_mechanismen/cli.py`:**
  * Registers `"tier2": "tier2.py"` in `PASS_THROUGH_SCRIPTS`.
  * Removes `("templates/decisions.md.template", ".agents/context/decisions.md")` from `TEMPLATE_MAPPINGS` and removes `templates/decisions.md.template`.
  * Adds an **uncommented** `_gm-materials/.cache/tier2.json` line to `DEFAULT_GITIGNORE` (with a `#` comment line above it, matching `.agents/context/catalog.json`) and adds `"_gm-materials/.cache/tier2.json"` to `DERIVED_CACHE_FILES` so `_has_gitignore_entry()` passes on fresh vaults and `_doctor()`'s `git ls-files --error-unmatch` guard flags or untracks any force-added copy.
  * In `_doctor()`:
    * If legacy `.agents/context/decisions.md` exists, prints a `⚠` advisory guiding manual migration (static conventions to `.agents/AGENTS.md`, mutable rulings to `_gm-materials/rulings/`). **Never** auto-deletes `.agents/context/decisions.md` under `--fix` to prevent data loss.
    * When `_gm-materials/rulings/` contains at least one `.md` file, checks `_gm-materials/.cache/tier2.json` presence, `schema_version`, and compile-diff freshness (advisory `⚠` if absent or stale, `✗` if corrupt JSON); under `--fix`, runs `scripts/tier2.py` to compile/refresh `_gm-materials/.cache/tier2.json` alongside `catalog.json`.

### Component 6: Atomic Cutover of Skills & Documentation

All Tier 2 consumers cut over in the same PR as the tooling:

* **`skills/lookup-context/SKILL.md`:** Step 1 inspects `_gm-materials/.cache/tier2.json` (rebuilding via `oude tier2` if absent/stale; filtering to `status == active` for active world state, or matching `actors` and opening `path` for historical `opinions`) instead of `.agents/context/decisions.md`.
* **`skills/prep-session/SKILL.md`:** Step 0 monthly faction turn writes one ruling file per resolved turn under `_gm-materials/rulings/` and runs `oude tier2` to refresh `_gm-materials/.cache/tier2.json` and check entity overlaps; session prep notes remain in `_gm-materials/session-preps/` (reclassified as Tier 3).
* **`skills/weave-threads/SKILL.md`:** Reads `_gm-materials/.cache/tier2.json` for active rulings and records GM-confirmed lore into `_gm-materials/rulings/`.
* **`skills/scribe-session/SKILL.md`:** Updates Guiding Principles (dynamic canon grounding and tier definitions), Step 2 (chat ingestion), and Step 3 Section 7 (proposed table rulings) to reference `_gm-materials/rulings/` and `_gm-materials/.cache/tier2.json`, adds a promotion check as a final sub-step of Step 5 (after character condition reconciliation), and corrects `_gm-materials/session-preps/` from Tier 2 to Tier 3.
* **`skills/lint-wiki/SKILL.md`:** Documents the new `duplicate-id` (`FAIL`) and `rulings` (`FAIL`/`WARN`) checks, updates `checks_skipped` targeted-mode rules, updates the output Summary template, and clarifies that `oude lint-wiki` deterministically inspects `_gm-materials/rulings/` locally while the skill itself does not bulk-read `_gm-materials/`.
* **Core docs (`AGENTS.md`, `templates/AGENTS.md.template`, `README.md`, `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md`, `docs/MIGRATION_GUIDE.md`):** Align all references to the clarified Tier 0–3 hierarchy (`session-preps/` in Tier 3, raw PDFs outside Tier 3, `_gm-materials/rulings/` + `_gm-materials/.cache/tier2.json` in Tier 2, noting that `rolling_glossary.md` retains `tier: 2` in `catalog.json`), add an addendum note to ADR 003, and document that already-pushed public Git history for legacy `decisions.md` in `charged` and `hostile` is accepted without history rewrites.

## Alternatives Considered

### Alternative A: Nest Existing `_gm-materials/` Subfolders into `tier2/` and `tier3/`

* **Pros**: Visual directory grouping matches the Tier 2 and Tier 3 hierarchy directly (`_gm-materials/tier2/{rulings,session-summaries}/` and `_gm-materials/tier3/{digests,session-preps}/`).
* **Cons**: Forces path changes across `generate_digests.py`, `transcribe_session.py`, `scribe_session.py`, `audit_coverage.py`, `lint_wiki.py`, multiple skills, and existing `{% comment %}` cross-tier links already embedded in `charged` and `hostile` Tier 1 notes (`../../_gm-materials/digests/...`).
* **Reason for Rejection**: Rejected by author: high cross-repository migration blast radius for a directory naming cleanup; adding `_gm-materials/rulings/` alongside existing folders achieves the same isolation with zero breakage to existing paths.

### Alternative B: Store Behind-the-Screen Actor Stances in `{% comment %}` Blocks Inside Published `directory/` Notes

* **Pros**: Single file per faction; zero separate Tier 2 entity files; hidden from rendered Jekyll HTML pages.
* **Cons**: `charged` and `hostile` are public GitHub repositories, so `{% comment %}` blocks remain readable in plain Markdown on GitHub and in Git history; every off-screen faction turn mutates public Tier 1 files, changing `catalog.json` SHAs and causing unnecessary Git commits and site rebuilds.
* **Reason for Rejection**: Rejected on privacy and separation-of-concerns grounds: `{% comment %}` does not protect secrets in a public repository and couples off-screen GM updates to public Tier 1 commits.

### Alternative C: Maintain a Tier 2 Gazetteer Mirror or Per-Actor Private Opinion Files (`_gm-materials/actors/<slug>.md`)

* **Pros**: Consolidates each actor's behind-the-screen history into one file per actor and allows promoted turn rulings to be deleted outright.
* **Cons**: Splits every faction turn into `N + 1` file edits (the ruling plus one file per voting actor) and creates a shadow semi-directory mirroring published `directory/` notes, introducing split-brain maintenance.
* **Reason for Rejection**: Rejected by author: recreates a duplicate semi-directory for active actors and multiplies edit overhead per turn; retaining promoted/superseded ruling files in `_gm-materials/rulings/` preserves private `opinions` in a single file per turn.

### Alternative D: Delete Tier 2 Rulings Immediately Upon Promotion to Tier 1 or Supersession

* **Pros**: Keeps `_gm-materials/rulings/` containing exclusively active facts with no status-filtering logic.
* **Cons**: Deleting a faction-turn ruling once its outcome enters Tier 1 discards private behind-the-screen peer `opinions` (votes, grudges, reasoning) that were never exposed to players and therefore do not move into Tier 1.
* **Reason for Rejection**: Rejected by author: loses private actor memory required to inform subsequent faction turns.

### Alternative E: Reference Entities by Vault-Relative Paths Plus an Optional `_gm-materials/rulings/_actors.yml` Roster

* **Pros**: Requires zero changes to Tier 1 notes or the RubyGem (`jekyll/_plugins/data_extractor.rb`).
* **Cons**: Introduces an extra configuration file (`_actors.yml`) to keep in sync with `directory/`, and raw file paths break whenever a Tier 1 note is renamed or moved.
* **Reason for Rejection**: Rejected by author after Goldfish review in favour of optional explicit Tier 1 `id:` fields joined at compile time against `catalog.json`: eliminates the mapping file and keeps references stable across file renames.

### Alternative F: Auto-Derive Fallback Tier 1 `id`s from Filenames When `id:` Is Omitted

* **Pros**: Every Tier 1 note immediately gets an `id` without adding front matter.
* **Cons**: Renaming or reorganising a Tier 1 file silently alters its fallback `id` and breaks Tier 2 joins, undermining the stability guarantee.
* **Reason for Rejection**: Rejected by author: explicit optional `id:` fields added progressively preserve rename stability with zero big-bang backfill.

### Alternative G: Place the Compiled Index at `.agents/context/tier2.json` or `_gm-materials/tier2.json`

* **Pros**: `.agents/context/tier2.json` groups all derived indexes in one directory; `_gm-materials/tier2.json` avoids a `.cache/` subfolder.
* **Cons**: `.agents/context/` is Git-tracked, leaving a single `.gitignore` line as the sole barrier against leaking GM secrets into public Git history on un-migrated vaults; `_gm-materials/tier2.json` outside a dot-folder is synced by Obsidian Sync, causing avoidable sync conflicts across `ryu` and `artemis`.
* **Reason for Rejection**: Rejected by author after Goldfish review: `_gm-materials/.cache/tier2.json` inherits `_gm-materials/`'s four-layer exclusion and is skipped by Obsidian Sync under default hidden-files settings while rebuilding locally (target under 50 ms for ~100 rulings).

### Alternative H: Author Bidirectional `superseded_by` Alongside `supersedes: []` in Front Matter

* **Pros**: Opening an older ruling file directly shows which newer ruling replaced it.
* **Cons**: Pairing list `supersedes: []` with scalar `superseded_by` is not pairwise symmetric, duplicates relationship state across two files, and does not prevent cycles without an explicit DAG check.
* **Reason for Rejection**: Rejected by author after Goldfish review: authoring only `supersedes: []` + `status` and deriving `superseded_by: []` at compile time (with DAG cycle detection and single-active-successor enforcement in `lint_wiki.py`) removes redundant state and prevents drift.

### Alternative I: Multi-Subcommand `oude tier2` CLI and Compiled `by_actor` Rollup Inside `tier2.json`

* **Pros**: Provides dedicated terminal query subcommands (`oude tier2 index | check | actor <id>`) and a pre-grouped actor lookup block with a recency window (proposed by `egm-design` in [003_goldfish_review_117.md](../reviews/003_goldfish_review_117.md) to bound prompt size past ~30 turns).
* **Cons**: Diverges from `oude`'s single-script pass-through pattern (`PASS_THROUGH_SCRIPTS`), duplicates `lint-wiki` validation flags, and adds secondary index structures that agents can derive from `entries[]` (matching `catalog.json`).
* **Reason for Rejection**: Rejected by author after Goldfish review in favour of one pass-through `oude tier2` command, `check_rulings()` in `lint_wiki.py`, and an entries-only `{schema_version, generated, catalog_sha, entries[]}` index; long-horizon actor prompt bloat is explicitly deferred to manual consolidation rulings under Future Improvements.

### Alternative J: Store `opinions` as Markdown Bullets, a 3-Column Markdown Pipe Table, or an In-Body Fenced `yaml` Block

* **Pros**: Bullets and pipe tables render natively as Markdown prose/tables; fenced `yaml` blocks avoid Obsidian's Properties UI rendering limits for nested YAML.
* **Cons**: Freeform bullets risk silent parse failures after manual edits; author dislikes Markdown tables; fenced body blocks require a secondary parser pass beyond front matter, and the author uses Source Mode for properties so Properties UI rendering is not a constraint.
* **Reason for Rejection**: Rejected by author (bullets/tables) and superseded by Goldfish consensus on YAML front matter (single `yaml.safe_load()` pass; pure narrative body).

### Alternative K: Archive Raw TOME `state.json`/`log.jsonl` and Wire a CLI Faction-Turn Runner into `oude`

* **Pros**: Enables deterministic seed-based replay of past TOME turns from inside `oude`.
* **Cons**: Couples `oude` to `tome`'s internal JSON contract, adds heavy archival payloads to `_gm-materials/`, and assumes future faction-turn rounds start directly from the prior round's static end state even though intervening played sessions alter the world.
* **Reason for Rejection**: Rejected by author: `oude` and `tome` must remain independent applications, and humans/agents assemble each new round's initial state from Tier 1 canon plus active Tier 2 rulings and historical `opinions`.

### Alternative L: Move `_gm-materials/session-summaries/` into Public Git as Tier 1

* **Pros**: Places all table-originated records in Pillar 1 Git and allows direct GitHub links from chapters.
* **Cons**: AI-extracted session notes (`*_session_notes.md`) and intermediate scratch files are not line-by-line GM-verified and may contain transcription or extraction errors.
* **Reason for Rejection**: Rejected by author: unverified AI session records belong in Tier 2 inside `_gm-materials/session-summaries/`.

## Non-Functional Requirements

### Security & Privacy

* **Four-layer secret isolation:** Both `_gm-materials/rulings/` and `_gm-materials/.cache/tier2.json` reside inside `_gm-materials/`, which is excluded across `.gitignore`, `_config.yml` `exclude:`, Jekyll's leading-underscore skip, and `jekyll/_plugins/data_extractor.rb`.
* **Force-add detection:** Registering `_gm-materials/.cache/tier2.json` in `DERIVED_CACHE_FILES` and as an uncommented line in `DEFAULT_GITIGNORE` ensures `oude doctor`'s `git ls-files --error-unmatch` loop detects and (under `--fix`) untracks any copy staged via `git add -f`.
* **No public Git history rewrite:** Historical commits of `.agents/context/decisions.md` in `charged` and `hostile` remain in Git history; operators accept existing history rather than force-pushing rewritten public branches.

### Performance & Storage

* **Index compilation latency:** `oude tier2` parses only YAML front matter across `_gm-materials/rulings/*.md` and reads `.agents/context/catalog.json` locally with zero network or LLM calls (target under 50 ms for ~100 rulings).
* **Compact index footprint & prompt growth envelope:** Omitting `opinions` prose from `_gm-materials/.cache/tier2.json` keeps the derived index compact (~300–500 bytes per entry). `load_active_rulings_text()` parses `_gm-materials/rulings/*.md` directly (avoiding stale-cache injection) and injects all `status == active` facts without silent truncation; expected steady-state active ruling count is ~10–40 per campaign, with an advisory `WARN` emitted past 50 active rulings.
* **Atomic, idempotent writes:** `scripts/tier2.py` writes via a temporary file in `_gm-materials/.cache/` followed by `os.replace()`, and skips writing when compiled content (excluding `generated`) is unchanged.

### Rollout, Backward Compatibility & Rollback

* **Atomic cutover:** Retiring `templates/decisions.md.template`, updating `cli.py`, updating `transcribe_session.py` / `scribe_session.py`, and cutting over all five skills (`lookup-context`, `prep-session`, `weave-threads`, `scribe-session`, `lint-wiki`) land in a single PR so documentation and tooling never disagree.
* **Graceful degradation on un-migrated vaults & CI:** `load_active_rulings_text()` falls back read-only to `.agents/context/decisions.md` when `_gm-materials/rulings/` does not exist; `oude lint-wiki` skips `check_rulings()` cleanly when `_gm-materials/rulings/` is absent or empty (preserving green public CI runs); `oude doctor` never deletes `.agents/context/decisions.md` automatically.
* **RubyGem coordination:** Downstream vaults adopt Tier 1 `id:` indexing on their next `oude-mechanismen` gem tag bump; until bumped, `catalog.json` entries simply lack `"id"`, which `oude tier2` handles gracefully via `resolved_entities[slug] = null` + `WARN`.
* **Rollback:** Reverting the PR leaves plain Markdown files in `_gm-materials/rulings/` intact and human-readable in Obsidian; no irreversible data transformation occurs.

## Risks & Mitigations

* **Stale `resolved_entities` after Tier 1 `catalog.json` rebuilds:** Adding or editing `id:` on a Tier 1 note updates `.agents/context/catalog.json` without changing any ruling file SHA. *Mitigation:* `scripts/tier2.py` stores `catalog_sha` in `_gm-materials/.cache/tier2.json`, and `check_rulings()` verifies freshness via `compile_tier2_index(root, write=False)` diff so any `catalog.json` change flags `tier2.json` as stale (`FAIL`).
* **Unbounded active ruling growth in session prompts:** Because `load_active_rulings_text()` injects all active rulings verbatim without silent truncation, an unpruned multi-year campaign could bloat local Ollama prompt inputs. *Mitigation:* Emit a stderr `[WARN]` past 50 active rulings prompting promotion/consolidation, and keep `scribe-session` Step 5 prompting promotion as soon as rulings reach play.
* **Obsidian Sync hidden-files override:** While Obsidian Sync excludes dot-folders like `.cache/` by default, an operator who explicitly enables hidden-file sync could sync `_gm-materials/.cache/tier2.json` across `ryu` and `artemis` (unverifiable by `oude doctor`, per ADR 003 §2). *Mitigation:* The file is purely derived and harmless if overwritten; running `oude tier2` deterministically restores it locally (target under 50 ms for ~100 rulings).
* **Legacy `.agents/context/decisions.md` coexistence during migration:** Operators who begin authoring `_gm-materials/rulings/` without removing legacy `decisions.md` risk split Tier 2 state. *Mitigation:* Both `oude lint-wiki` (`check_rulings()`) and `oude doctor` emit explicit coexistence warnings without auto-deleting human-authored content.
* **Unresolved slug typos masquerading as behind-the-screen actors:** Without a separate actor registry, a mistyped slug (`sigisfarn` vs. `sigisfarne`) resolves to `null` rather than failing hard. *Mitigation:* Both `oude tier2` and `check_rulings()` emit an explicit `WARN` for every unresolved slug so typos surface immediately on every compile and lint pass.

### Additional Resources

* Issue [#117](https://github.com/terra-campaigns/oude-mechanismen/issues/117) — *Rethink Tier 2 documentation: structured rulings, supersession tracking, faction-turn records*.
* [ADR 003: Dual-Workstation Topology, Four-Pillar Storage, and Semantic Wiki Ingestion](../adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md).
* [003_goldfish_review_117.md](../reviews/003_goldfish_review_117.md) — Step 2 brainstorm Goldfish synthesis.
* [004_design_006_egm_review.md](../reviews/004_design_006_egm_review.md) — Consolidated Round 1 and Round 2 `/egm-review` findings and resolutions.

### Future Improvements

* **Ignore-list audit for `.agents/context/references.json`:** Evaluate whether `.agents/context/references.json` should be added to `DERIVED_CACHE_FILES` and `DEFAULT_GITIGNORE` (flagged during Goldfish review; tracked separately to keep Issue #117 tightly scoped).
* **Removal of legacy `.agents/context/decisions.md` fallback shim:** Remove the read-only `.agents/context/decisions.md` fallback branch in `scripts/tier2.py:load_active_rulings_text()` in the next minor release after `charged` and `hostile` complete migration to `_gm-materials/rulings/`.
* **Long-horizon actor memory consolidation:** If a campaign exceeds ~30 faction turns for a single actor and opening historical ruling files becomes noisy, operators can author a single manual consolidation ruling (`kind: ruling`, `supersedes: [...]`) summarising enduring grievances without introducing a new file type.

## Detailed Implementation Plan

All changes ship in a single PR targeting `develop` (per [AGENTS.md §8](../../AGENTS.md)) so code, templates, skills, documentation, and tests cut over atomically. No changes to `pyproject.toml` are required because `[tool.hatch.build.targets.wheel.force-include]` already bundles the entire `scripts/` directory.

### Target Files to Create/Modify

#### 1. `jekyll/_plugins/data_extractor.rb` (Modify)

* **Type / Scope**: Ruby Jekyll plugin (`OudeMechanismen::DataExtractor.extract`).
* **Proposed Changes**:
  * Inside the `catalog_entries << { ... }` hash builder (around line 251), extract optional explicit `id` from parsed front matter:
    * `raw_id = fm['id']`
    * `entry_id = raw_id.nil? ? nil : raw_id.to_s.strip`
    * `entry_id = nil if entry_id.nil? || entry_id.empty?`
  * Add `"id" => entry_id` to each catalogue entry dict. Do **not** derive fallback IDs from filenames or paths.
  * Keep `_gm-materials/` exclusion (line 43) and `rolling_glossary.md` handling (`tier: 2` legacy label) untouched.

#### 2. `scripts/tier2.py` (Create)

* **Type / Scope**: Python pass-through script (`oude tier2`) and shared Tier 2 validation/index library.
* **Proposed Changes**:
  * Define module constants:
    * `SCHEMA_VERSION = 1`
    * `ACTIVE_RULINGS_WARN_THRESHOLD = 50`
    * `RULING_ID_RE = re.compile(r"^R-[0-9]{3,}$")`
    * `SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")`
    * `VALID_KINDS = frozenset({"ruling", "faction-turn"})`
    * `VALID_STATUSES = frozenset({"active", "superseded", "retracted", "promoted"})`
    * `RULINGS_REL_DIR = Path("_gm-materials") / "rulings"`
    * `CACHE_REL_PATH = Path("_gm-materials") / ".cache" / "tier2.json"`
  * Define dataclasses:
    * `Tier2Diagnostic(severity: str, file: str, line: int, message: str)` (`severity` in `{"FAIL", "WARN"}`).
    * `ParsedRuling(id, title, date, in_world_date, kind, status, fact, entities, actors, supersedes, promoted_to, retraction_reason, turn, opinions, rel_path, sha)`.
  * Implement pure functions (no side effects until atomic cache write):
    * `discover_ruling_files(root: Path) -> List[Path]`: return sorted `*.md` directly inside `root / RULINGS_REL_DIR`, ignoring dot-files; return `[]` if the directory does not exist.
    * `parse_ruling_file(root: Path, path: Path) -> Tuple[Optional[ParsedRuling], List[Tier2Diagnostic]]`: parse YAML front matter via `yaml.safe_load()` (failing loudly on missing front matter, non-mapping YAML, or `yaml.YAMLError`); reject authored `superseded_by` key (`FAIL`); validate `id` (`RULING_ID_RE`), `title` (non-empty `str`), `date` (`str` matching `YYYY-MM-DD` or `datetime.date`, rejecting `datetime.datetime`), `in_world_date` (intentionally freeform optional `str | date | None` to support arbitrary campaign calendars, stringified if date), `kind` (`VALID_KINDS`), `status` (`VALID_STATUSES`), `fact` (non-empty `str`), `entities` (list of slugs matching `SLUG_RE`), `actors` (list of slugs matching `SLUG_RE`; required non-empty for `faction-turn`), `supersedes` (list of IDs matching `RULING_ID_RE`), `promoted_to` (`str | None`), `retraction_reason` (`str | None`), optional `turn` (`dict | None`), and `opinions` (required non-empty list for `faction-turn`; optional for `ruling`, validated identically when present: each item must have `actor` matching `SLUG_RE` and present in `actors` — `FAIL` otherwise — exact `int` `vote` in `{-1, 0, 1}` rejecting `bool`, exact `bool` `shifted`, and non-empty `str` `stance`); emit `WARN` if `path.name` does not start with `f"{id}_"`; compute 8-char SHA-256 over raw file bytes.
    * `load_catalog_state(root: Path) -> Tuple[Dict[str, str], Optional[str]]`: read `.agents/context/catalog.json` if present and return `({e["id"]: e["path"] for e in entries if isinstance(e.get("id"), str) and e["id"]}, sha8_of_catalog_bytes)` (explicitly skipping `null`/empty `id` entries); return `({}, None)` if absent or unreadable.
    * `validate_rulings(root: Path, catalog_ids: Optional[Dict[str, str]] = None) -> Tuple[List[ParsedRuling], Dict[str, List[str]], Dict[str, Dict[str, Optional[str]]], List[Tier2Diagnostic]]`:
      * Parse all discovered files and check ruling `id` uniqueness (`FAIL` on duplicates).
      * Enforce supersession DAG invariants:
        * No self-loops or unknown IDs in `supersedes` (`FAIL`).
        * 3-colour DFS cycle detection over `supersedes` edges (`FAIL` reporting the exact cycle path).
        * Every ID targeted by `supersedes` must have `status == "superseded"` (`FAIL` otherwise — `active`, `promoted`, and `retracted` are invalid targets); every ruling with `status == "superseded"` must be targeted by at least one `supersedes` edge (`FAIL` if orphaned).
        * Status-to-partner-field matrix: `active`/`superseded` forbid `promoted_to` and `retraction_reason`; `promoted` requires `promoted_to` resolving inside `root` to an existing Tier 1 `.md` file (matching `include_paths` from `tier1_sources.yml` or the engine code fallback when absent, outside `_gm-materials/` and `.agents/`), forbids `retraction_reason`, and may retain historical `supersedes` entries; `retracted` requires non-empty `retraction_reason`, forbids `promoted_to`, and requires `supersedes == []` (`FAIL` otherwise).
        * Single active successor check: if two or more `status == "active"` rulings list the same target ID in `supersedes`, emit `FAIL`.
      * Derive inverse map `superseded_by: Dict[str, List[str]]` (sorted IDs per ruling).
      * Left-join all slugs (`entities` and `actors`) against `catalog_ids`, producing `resolved_entities` per ruling and emitting an advisory `WARN` per unresolved slug (deduplicated per ruling).
    * `find_active_entity_overlaps(rulings: List[ParsedRuling]) -> Dict[str, List[ParsedRuling]]`: group `status == "active"` rulings by each slug in `entities` and return slugs shared by two or more active rulings.
    * `compile_tier2_index(root: Path, write: bool = True) -> Tuple[Optional[Dict[str, Any]], List[Tier2Diagnostic], Dict[str, List[ParsedRuling]]]`: load `(catalog_ids, catalog_sha)` via `load_catalog_state(root)`; run `validate_rulings()`; if any `FAIL` diagnostic exists, return `(None, diagnostics, {})` without writing; otherwise build `{"schema_version": SCHEMA_VERSION, "generated": iso_utc, "catalog_sha": catalog_sha, "entries": [...]}` sorted by `id` (each entry containing `id`, `title`, `date`, `in_world_date`, `kind`, `status`, `fact`, `entities`, `actors` verbatim, `resolved_entities`, `supersedes`, `superseded_by`, `promoted_to`, `retraction_reason`, `path`, `sha` — omitting full `opinions` prose). When `write=True`, compare against existing `_gm-materials/.cache/tier2.json` ignoring `generated` (skip write if unchanged) and write atomically via a temp file in `_gm-materials/.cache/` + `os.replace()`.
    * `load_active_rulings_text(repo_root: Path) -> str`: shared helper for `transcribe_session.py` and `scribe_session.py`. When `(repo_root / RULINGS_REL_DIR).is_dir()`, run `validate_rulings(repo_root)` directly against `_gm-materials/rulings/*.md` (never reading the derived cache); if any `FAIL`-severity diagnostic exists, emit all `FAIL` diagnostics to stderr and raise `ValueError` (never silently skipping a malformed ruling); otherwise collect `status == "active"` rulings sorted by `id`, emit a stderr `[WARN]` if count exceeds `ACTIVE_RULINGS_WARN_THRESHOLD`, and format `- **<id> — <title>:** <fact>` lines. If `(repo_root / RULINGS_REL_DIR)` does not exist, fall back read-only to `.agents/context/decisions.md` when present.
    * `main(argv: Optional[List[str]] = None) -> int`: parse `--root` (default `.`). Exit `0` when `_gm-materials/rulings/` is absent/empty or compilation succeeds (printing overlap advisories and `WARN`s as plain text), exit `1` on any `FAIL` diagnostic, exit `2` if `--root` is not a directory.

#### 3. `scripts/lint_wiki.py` (Modify)

* **Type / Scope**: Gate 3 structural wiki linter.
* **Proposed Changes**:
  * Add `sys.path.insert(0, str(Path(__file__).resolve().parent))` guard (matching `scripts/scribe_session.py:27-30`) before `import tier2`.
  * Add `"duplicate-id"` and `"rulings"` to the report `order` list in `render_text_report()` (around line 801).
  * Add `check_duplicate_ids(root: Path, files: List[Path], findings: List[Finding], check_duplicates: bool = True) -> None`:
    * For every scanned Tier 1 note with a non-empty `id` key in front matter, validate it is a string matching `tier2.SLUG_RE` (`FAIL` under `front-matter` if invalid).
    * When `check_duplicates=True` (full mode), detect duplicate `id:` values across scanned Tier 1 files and emit `FAIL` under `duplicate-id` listing all conflicting paths (mirroring `check_duplicate_titles()`).
  * Add `check_rulings(root: Path, findings: List[Finding]) -> None`:
    * Locate `ruling_files = tier2.discover_ruling_files(root)`. If `not ruling_files` (absent or empty `_gm-materials/rulings/`), return immediately with zero findings (keeps public CI runners and fresh empty vaults green).
    * If `(root / ".agents" / "context" / "decisions.md").is_file()`, emit a `WARN` under `rulings` noting legacy `decisions.md` coexists with `_gm-materials/rulings/`.
    * Call `expected, diagnostics, _ = tier2.compile_tier2_index(root, write=False)` and translate every `Tier2Diagnostic` into a `Finding(check="rulings", ...)`.
    * Validate `_gm-materials/.cache/tier2.json` freshness via a single compile-diff check (intentionally stricter than `check_catalogue()` because agents read `tier2.json` as authoritative behind-the-screen state):
      * Absent cache file → `WARN` (`_gm-materials/.cache/tier2.json absent; run oude tier2 or oude doctor --fix`).
      * Invalid JSON, non-dict payload, or `schema_version != tier2.SCHEMA_VERSION` → `FAIL`.
      * When `expected is not None` and on-disk `tier2.json` (excluding `generated`) differs from `expected` (excluding `generated`) → `FAIL` (`_gm-materials/.cache/tier2.json is stale; run oude tier2`).
  * Wire `check_duplicate_ids()` and `check_rulings()` into `lint_wiki()`:
    * Full mode: run both `check_duplicate_ids(..., check_duplicates=True)` and `check_rulings(root, f)`.
    * Targeted mode: evaluate whether any raw CLI `paths` argument resolves to or inside `_gm-materials/rulings/` **before** `_has_skipped_segment` filtering (`lint_wiki.py:55,151-153,753-759`); permit explicitly targeted `_gm-materials/rulings/` files through directory expansion while keeping them out of Tier 1 checks (`tier1_files`); run `check_duplicate_ids(..., check_duplicates=False)` on `tier1_files`; run `check_rulings(root, f)` only when rulings were targeted (otherwise append `"rulings"` and `"duplicate-id"` to `report.checks_skipped`).

#### 4. `src/oude_mechanismen/cli.py` (Modify)

* **Type / Scope**: Unified `oude` CLI dispatcher, vault scaffolder, and health diagnostics.
* **Proposed Changes**:
  * Remove `("templates/decisions.md.template", ".agents/context/decisions.md")` from `TEMPLATE_MAPPINGS` (line 50).
  * Add `"tier2": "tier2.py"` to `PASS_THROUGH_SCRIPTS` (around line 74).
  * Add `"_gm-materials/.cache/tier2.json"` to `DERIVED_CACHE_FILES` (around line 93) and add an **uncommented** `_gm-materials/.cache/tier2.json` line to `DEFAULT_GITIGNORE` (with an explanatory `#` comment line above it, matching `.agents/context/catalog.json` at lines 116–117) so `_has_gitignore_entry()` passes on fresh vaults and `_doctor()`'s `git ls-files --error-unmatch` guard catches any force-added copy.
  * In `_doctor()`:
    * Check for legacy `.agents/context/decisions.md`: if present, print a `⚠` advisory (without failing `all_passed` or auto-deleting under `--fix`) instructing the operator to move static conventions to `.agents/AGENTS.md` and mutable world-state rulings to `_gm-materials/rulings/`.
    * When `(vault / "_gm-materials" / "rulings").is_dir()` contains at least one `.md` file: inspect `_gm-materials/.cache/tier2.json` (`schema_version` and compile-diff freshness). If absent or stale, print an advisory `⚠` (or `✗` if corrupt JSON); when `fix=True`, invoke `_run_script("tier2.py", ["--root", str(vault)])` (setting `all_passed = False` if compilation fails).

#### 5. `scripts/transcribe_session.py` (Modify)

* **Type / Scope**: Acoustic glossary compiler (`build_dynamic_glossary()`, line 264).
* **Proposed Changes**:
  * Add `sys.path.insert(0, str(Path(__file__).resolve().parent))` guard and replace direct `.agents/context/decisions.md` reading (lines 278, 368–370) with `tier2.load_active_rulings_text(repo_root)`.
  * Update docstrings (lines 13, 271–272) to reference `_gm-materials/rulings/` rather than `.agents/context/decisions.md`.

#### 6. `scripts/scribe_session.py` (Modify)

* **Type / Scope**: Local Ollama (`qwen2.5:14b`) two-pass session extractor — Pass 2A tactical facts and Pass 2B sensory textures (`read_context_files()`, line 452).
* **Proposed Changes**:
  * Import sibling `tier2` (already guarded by `sys.path.insert` at lines 27–30) and replace direct `.agents/context/decisions.md` reading (lines 476–478) with `tier2.load_active_rulings_text(repo_root)`, populating `context["decisions"]` only when non-empty.

#### 7. `templates/decisions.md.template` (Delete)

* **Type / Scope**: Retired starter template.
* **Proposed Changes**:
  * Delete `templates/decisions.md.template` as part of the atomic cutover (new vaults store static conventions in `.agents/AGENTS.md` and mutable behind-the-screen rulings in `_gm-materials/rulings/`).

#### 8. `skills/lookup-context/SKILL.md` (Modify)

* **Type / Scope**: Progressive multi-tier context retrieval skill.
* **Proposed Changes**:
  * Update Step 1 (Tier 2 lookup) to read `_gm-materials/.cache/tier2.json` (rebuilding via `oude tier2` if absent/stale): filter to `status == active` for active world-state facts, and inspect `actors` / `entities` then open the ruling `path` under `_gm-materials/rulings/` when private `opinions` or turn narrative are needed.
  * Update Step 4 canon tier labels to match the clarified Tier 0–3 hierarchy (`_gm-materials/rulings/` and `_gm-materials/session-summaries/` as Tier 2; `_gm-materials/digests/` and `_gm-materials/session-preps/` as Tier 3).

#### 9. `skills/prep-session/SKILL.md` (Modify)

* **Type / Scope**: 8-step GM session preparation skill.
* **Proposed Changes**:
  * Update Guiding Principles (line 14) to source Tier 2 from `_gm-materials/.cache/tier2.json` / `_gm-materials/rulings/` (not `.agents/context/decisions.md`) and classify `_gm-materials/session-preps/` as Tier 3.
  * Update Step 0 Monthly Faction Turn (line 31) to author one ruling note per resolved turn under `_gm-materials/rulings/<id>_<slug>.md` (with `kind: faction-turn`, `status: active`, `fact`, `entities`, `actors`, optional `turn`, and `opinions`), run `oude tier2` to refresh `_gm-materials/.cache/tier2.json`, and review printed active-entity overlaps for supersession.

#### 10. `skills/weave-threads/SKILL.md` (Modify)

* **Type / Scope**: Narrative thread and anomaly analysis skill.
* **Proposed Changes**:
  * Replace `.agents/context/decisions.md` reads (lines 25, 81) with `_gm-materials/.cache/tier2.json` (and targeted reads of `_gm-materials/rulings/*.md`).
  * Update Step 2.4 consolidation (line 70) to record GM-confirmed lore as a structured ruling note in `_gm-materials/rulings/` and refresh `_gm-materials/.cache/tier2.json` via `oude tier2`.

#### 11. `skills/scribe-session/SKILL.md` (Modify)

* **Type / Scope**: Air-gapped transcription and chapter drafting skill.
* **Proposed Changes**:
  * Update Guiding Principles (lines 14, 17) to reference `_gm-materials/.cache/tier2.json` / `_gm-materials/rulings/` and correct `_gm-materials/session-preps/` from Tier 2 to Tier 3.
  * Update Step 2 (line 61) and Step 3 Section 7 (line 80) to read `_gm-materials/.cache/tier2.json` and propose new behind-the-screen rulings for `_gm-materials/rulings/`.
  * Add a promotion check as a final sub-step of Step 5 (after line 157, Character Condition Reconciliation): inspect active entries in `_gm-materials/.cache/tier2.json` matching entities appearing in the drafted chapter and prompt the GM to mark exposed rulings `status: promoted` with `promoted_to: campaigns/...` (retaining private `opinions`).

#### 12. `skills/lint-wiki/SKILL.md` (Modify)

* **Type / Scope**: Gate 3 structural wiki linting skill.
* **Proposed Changes**:
  * Update full-scan and targeted-mode bullet descriptions (lines 22–23) to include `duplicate-id` and `rulings` (and document that `duplicate-id` and `rulings` appear in `checks_skipped` in targeted mode unless `_gm-materials/rulings/` is explicitly targeted).
  * Clarify line 26 (`Do not read ... _gm-materials/`): the CLI deterministically inspects `_gm-materials/rulings/` locally; the skill still must not bulk-read `_gm-materials/`.
  * Add `duplicate-id (FAIL)` and `rulings (FAIL/WARN)` entries under `## Interpreting findings` (after line 40) and add matching lines to the `## Summary` output template (lines 52–62).

#### 13. `AGENTS.md`, `templates/AGENTS.md.template`, `README.md`, `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md`, `docs/MIGRATION_GUIDE.md` (Modify)

* **Type / Scope**: Core architecture manual, vault starter instructions, README, ADR 003, and operator migration guide.
* **Proposed Changes**:
  * **`AGENTS.md`**: Update §1.3, §2 topology (add `scripts/tier2.py`, remove `decisions.md.template`), and §4 Canon Hierarchy to document the clarified Tier 0–3 model (moving `_gm-materials/session-preps/` to Tier 3, raw PDFs outside Tier 3, `_gm-materials/rulings/` and `_gm-materials/.cache/tier2.json` in Tier 2, optional stable Tier 1 `id:` fields, and noting `rolling_glossary.md` retains `tier: 2` in `catalog.json`).
  * **`templates/AGENTS.md.template`**: Update `## Campaign Canon & Canon Hierarchy` (section at line 40, Tier 2 bullet at line 43) and `## Context & Token Optimisation Policy` (section at line 46, cache bullet at line 53) to replace `.agents/context/decisions.md` with `_gm-materials/rulings/` and `_gm-materials/.cache/tier2.json`, and place `session-preps/` under Tier 3.
  * **`README.md`**: Update line 33 to reflect `_gm-materials/rulings/` (Tier 2), `session-preps/` (Tier 3), and `oude tier2`.
  * **`docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md`**: Add a dated addendum note (without rewriting historical ADR 003 body sections) documenting `_gm-materials/rulings/` and `_gm-materials/.cache/tier2.json` inside Pillar 2 and aligning the Tier 2 vs. Tier 3 classification of `session-preps/` and external PDFs.
  * **`docs/MIGRATION_GUIDE.md`**: Add a short section *Migrating Legacy `.agents/context/decisions.md`* detailing the manual split (static style/procedure rules → `.agents/AGENTS.md`; mutable world-state rulings → `_gm-materials/rulings/<id>_<slug>.md`; remove `.agents/context/decisions.md`; run `oude doctor --fix`, `oude tier2`, and `oude lint-wiki`) and documenting acceptance of historical public Git commits without rewriting Git history.
  * Ensure every heading in every modified Markdown file is followed by a blank line (required by CI).

#### 14. `.github/workflows/ci.yml` (Modify)

* **Type / Scope**: GitHub Actions CI `validate` job.
* **Proposed Changes**:
  * Add `oude tier2 --help` alongside `oude lint --help` and `oude lint-wiki --help` in the wheel build & CLI smoke step (after line 50).

#### 15. `tests/fixtures/vault/directory/alpha.md`, `tests/test_dynamic_gem.rb`, `tests/test_e2e_jekyll.py` (Modify)

* **Type / Scope**: Fixture vault and Ruby/Python end-to-end Jekyll integration tests.
* **Proposed Changes**:
  * Add `id: alpha` to front matter of `tests/fixtures/vault/directory/alpha.md` (leave `campaigns/ep_001.md` without `id:` to test optional omission).
  * Update `tests/test_dynamic_gem.rb` and `tests/test_e2e_jekyll.py` to assert that `catalog.json` includes `"id": "alpha"` for `directory/alpha.md` and `"id": null` for entries without `id:`.

#### 16. `tests/test_tier2.py` (Create)

* **Type / Scope**: Unit test suite for `scripts/tier2.py`.
* **Proposed Changes**:
  * Cover: valid `ruling` and `faction-turn` compilation into `_gm-materials/.cache/tier2.json` with `schema_version: 1` and `catalog_sha`; omission of `opinions` prose from `tier2.json`; idempotent write skip when unchanged; atomic write failure safety (no corrupt `tier2.json` written on `FAIL`); absent/empty `_gm-materials/rulings/` exit `0` without directory or cache creation; compile-time left-join against `catalog.json` (`resolved_entities` matched vs. `null` + `WARN`, ignoring `null`-`id` catalog entries); active-entity overlap advisories; filename prefix mismatch `WARN`; authored `superseded_by` rejection (`FAIL`); supersession DAG valid chains, self-loop rejection, 2-node and 3-node cycle rejection, dangling target rejection, invalid `promoted`/`retracted` target rejection, orphaned `status: superseded` rejection, forked active successor `FAIL`; status-to-partner-field matrix (`promoted` valid/broken/non-Tier-1 path and retaining historical `supersedes`, `retracted` empty/present reason and non-empty `supersedes` rejection, `active`/`superseded` forbidden fields); strict `opinions` validation (boolean rejected as `vote`, out-of-range `vote`, non-bool `shifted`, empty `stance`, missing `opinions` on `faction-turn`, optional `opinions` on `ruling`, `opinions[].actor ∉ actors` `FAIL`); `load_active_rulings_text()` direct ruling parsing (ignoring stale cache), fail-loud `ValueError` + stderr output on malformed rulings, `>50` active-ruling stderr warning, and read-only legacy `decisions.md` fallback when `rulings/` is absent.

#### 17. `tests/test_lint_wiki.py` (Modify)

* **Type / Scope**: Unit test suite for `scripts/lint_wiki.py`.
* **Proposed Changes**:
  * Add tests for Tier 1 `id:` invalid grammar (`FAIL`) and duplicate Tier 1 `id:` detection (`FAIL`), plus optional `id:` omission (clean pass).
  * Add tests for `check_rulings()`: clean skip when `_gm-materials/rulings/` is absent (CI simulation) or empty (no unfixable `WARN`); full-mode and raw-CLI-path targeted-mode validation (`oude lint-wiki _gm-materials/rulings/`); absent `tier2.json` (`WARN`), corrupt or unknown `schema_version` `tier2.json` (`FAIL`), ruling SHA drift / missing ruling / `catalog_sha` drift (`FAIL`); coexistence of legacy `.agents/context/decisions.md` and non-empty `_gm-materials/rulings/` (`WARN`).

#### 18. `tests/test_cli.py` (Modify)

* **Type / Scope**: Unit test suite for `src/oude_mechanismen/cli.py`.
* **Proposed Changes**:
  * Update `test_init_repository_scaffolding` (`tests/test_cli.py:151`, assertion at line 178) to assert `.agents/context/decisions.md` is **not** scaffolded and an uncommented `_gm-materials/.cache/tier2.json` line is present in `.gitignore`.
  * Verify `PASS_THROUGH_SCRIPTS["tier2"] == "tier2.py"`, `DERIVED_CACHE_FILES` includes `_gm-materials/.cache/tier2.json`, and fresh-vault `oude doctor` passes cleanly.
  * Add `_doctor()` tests for: force-tracked `_gm-materials/.cache/tier2.json` detection and `--fix` untracking; legacy `.agents/context/decisions.md` advisory preserved (never deleted) under `--fix`; empty `_gm-materials/rulings/` produces no missing-index warning; stale/absent `_gm-materials/.cache/tier2.json` refreshed under `--fix` when `_gm-materials/rulings/` contains ruling files.

#### 19. `tests/test_scribe_session.py` & `tests/test_transcribe_session.py` (Modify)

* **Type / Scope**: Unit tests for session extraction (`read_context_files()`) and acoustic glossary compilation (`build_dynamic_glossary()`).
* **Proposed Changes**:
  * Verify both scripts ingest `status: active` rulings directly from `_gm-materials/rulings/*.md` (ignoring `superseded`/`retracted`/`promoted` rulings and ignoring any stale `_gm-materials/.cache/tier2.json`) when `_gm-materials/rulings/` exists, and retain read-only fallback when only legacy `.agents/context/decisions.md` exists.

### Verification Plan

All checks mirror `.github/workflows/ci.yml` (`validate` job) and must pass before opening a PR against `develop`:

* **Python AST & Unit Suite**:
  * `python3 -c "import ast, glob; [ast.parse(open(f, 'rb').read(), f) for f in glob.glob('scripts/*.py') + glob.glob('src/oude_mechanismen/*.py') + glob.glob('tests/*.py')]"`
  * `python3 -m unittest discover -s tests -v`
* **Package Wheel Build & CLI Smoke**:
  * `uv build && uv tool install --force . && oude --version && oude lint --help && oude lint-wiki --help && oude tier2 --help`
* **Ruby Syntax, Gem Build & Headless Dynamic-Gem Integration**:
  * `ruby -c jekyll/_plugins/data_extractor.rb && gem build oude-mechanismen.gemspec && gem install --no-document jekyll -v '~> 4.4.1' && ruby tests/test_dynamic_gem.rb`
* **Markdown Heading Blank-Line Gate**:
  * Run the CI blank-line validator (`.github/workflows/ci.yml:69-91`) across `skills/*/SKILL.md`, `README.md`, `CHANGELOG.md`, `AGENTS.md`, `templates/*.md.template`, `templates/jekyll/*.md.template`, and `docs/**/*.md`.
* **Manual Operational Smoke (Post-Implementation on a Local Copy of an Existing Vault such as `charged`)**:
  * Migrate sample rulings (for example, one retracted ruling and one TOME faction turn) into `_gm-materials/rulings/<id>_<slug>.md`, add explicit `id:` to two Tier 1 notes, run `bundle exec jekyll build`, `oude tier2`, `oude lint-wiki`, and `oude doctor`, and confirm active-entity overlaps, unresolved-slug warnings, `catalog_sha` staleness detection, and zero Git-tracked Tier 2 files (`git status --ignored`).

---

<!-- Provenance: Indicates initial structural drafting via Elephant-Goldfish Model (EGM). -->

*Drafted with Elephant-Goldfish Model (EGM)*
