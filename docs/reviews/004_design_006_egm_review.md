# EGM Multi-Stage Review Summary — Design 006 (Issue #117)

* **Author:** `efsalvarenga`
* **Status:** Complete — Round 1 & Round 2 Findings Resolved
* **Date:** 2026-11-25
* **Addresses:** [#117](https://github.com/terra-campaigns/oude-mechanismen/issues/117)
* **Target Document:** [006_tier2_canon_and_faction_turns.md](../designs/006_tier2_canon_and_faction_turns.md)
* **Prior Brainstorm Review:** [003_goldfish_review_117.md](003_goldfish_review_117.md)

---

## Overview

[006_tier2_canon_and_faction_turns.md](../designs/006_tier2_canon_and_faction_turns.md) underwent two full five-stage Elephant-Goldfish Model (`/egm-review`, Preset 1: uninterrupted flow) review rounds covering Initial Zoom Out + Inventive Catalyst (Stage 5), Comprehension (Stage 6), Design/Structural/Style Critique (Stage 7), Intermediate Zoom Out (Stage 8), and Implementation Readiness + Codebase Details (Stage 9).

## Round 1 Verdict & Resolutions (2026-11-24)

**Verdict:** 0 Blockers · 10 Majors · ~20 Nits. All codebase citations verified against the working tree; all four settled blockers from [003_goldfish_review_117.md](003_goldfish_review_117.md) confirmed honoured.

All 10 Round 1 Majors were resolved in the 2026-11-25 revision:

1. **M1 (`actors` single source of truth):** Made `opinions[].actor ⊆ actors` a hard `FAIL`; compiled `actors` verbatim and removed the implicit union and redundant `WARN`.
2. **M2 (`DEFAULT_GITIGNORE` format):** Specified an uncommented `_gm-materials/.cache/tier2.json` entry (matching `.agents/context/catalog.json`) so `_has_gitignore_entry()` passes on fresh vaults.
3. **M3 (`skills/lint-wiki/SKILL.md` cutover):** Added `skills/lint-wiki/SKILL.md` to the atomic single-PR cutover.
4. **M4 (Freshness severity & single compile-diff path):** Removed the contradictory `"same severity rules as check_catalogue()"` clause and unified freshness validation via `compile_tier2_index(root, write=False)` diff plus `schema_version: 1`.
5. **M5 (Forked active successors):** Promoted forked active successors to `FAIL` (single active successor) and added deterministic Tier-1-prose-vs.-Tier-2 contradiction detection to Non-Goals.
6. **M6 (`catalog_sha` dependency):** Added `catalog_sha` to `_gm-materials/.cache/tier2.json` so `catalog.json` rebuilds flag stale `resolved_entities`.
7. **M7 (Direct ruling reads & growth bound):** Switched `load_active_rulings_text()` to parse `_gm-materials/rulings/*.md` directly (never reading a stale cache) with a stderr `[WARN]` past 50 active rulings.
8. **M8 (Empty `rulings/` directory):** Skipped missing-index `WARN` when `_gm-materials/rulings/` has zero `.md` files.
9. **M9 (Symbol corrections):** Corrected `compile_campaign_glossary()` → `build_dynamic_glossary()` (`scripts/transcribe_session.py:264`) and `load_session_context()` → `read_context_files()` (`scripts/scribe_session.py:452`).
10. **M10 (`## Risks & Mitigations`):** Added per the `003` design template with `Additional Resources` and `Future Improvements` nested beneath it.

## Round 2 Verdict & Resolutions (2026-11-25)

**Verdict:** 0 Blockers · 2 Majors · ~12 Nits. All 10 Round 1 Majors and all Round 1 Stage 6/7/9 Nits verified resolved; Stage 9 Implementation Readiness reported 0 Blockers and 0 Majors.

All Round 2 Majors and Nits were resolved directly in [006_tier2_canon_and_faction_turns.md](../designs/006_tier2_canon_and_faction_turns.md) before opening the design PR:

1. **R2-M1 (Fail-loud `load_active_rulings_text()`):** Specified calling `validate_rulings()` directly and raising `ValueError` after printing `FAIL` diagnostics to stderr (eliminating any silent-drop path on malformed rulings), with unit test coverage in `tests/test_tier2.py`.
2. **R2-M2 (`include_paths` default attribution):** Separated the scaffolded template default (`templates/tier1_sources.yml.template`: `campaigns/`, `directory/`, `systems/`, `trading/`) from the engine code fallback when the YAML file is absent (additionally `statblocks/` in `data_extractor.rb:186` and `lint_wiki.py:34`).
3. **R2 Nits resolved:** Dropped unused `--format text|json` flag on `oude tier2`; unified `"target under 50 ms for ~100 rulings"` wording; clarified `.agents/context/rolling_glossary.md` in the Tier 2 parenthetical; qualified TOME TriO posture values as illustrative; restricted `supersedes == []` on `retracted` rulings while preserving historical `supersedes` on `promoted` rulings; fixed `templates/AGENTS.md.template` section citation (line 40, bullet line 43); filtered `null`-`id` entries in `load_catalog_state()`; added `gem install` prerequisite and `templates/jekyll/*.md.template` glob to the Verification Plan; noted `in_world_date` freeform grammar is intentional; added removal horizon for the legacy `decisions.md` fallback shim under Future Improvements; and added upfront comprehension glosses.

## Follow-Up Issue Triage

* **Recommended standalone GitHub issue:** Audit `.agents/context/references.json` against `DERIVED_CACHE_FILES` and `DEFAULT_GITIGNORE` (deferred out of scope of [#117](https://github.com/terra-campaigns/oude-mechanismen/issues/117)).
* **Post-implementation follow-up (defer opening until after implementation PR merges):** Remove the read-only `.agents/context/decisions.md` fallback shim in `scripts/tier2.py:load_active_rulings_text()` once `charged` and `hostile` complete migration.
* **No issues needed for Round 2 design findings:** Both Round 2 Majors and all Nits are resolved in [006_tier2_canon_and_faction_turns.md](../designs/006_tier2_canon_and_faction_turns.md).
