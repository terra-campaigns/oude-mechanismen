# Unified `type` Front Matter Key Across Tier 1 Notes and Tier 3 Digests

* **Author:** `efsalvarenga`
* **Status:** Proposed (Post-Review Revision — Round 1 Resolved)
* **Date:** 2026-11-25
* **Addresses:** [#115](https://github.com/terra-campaigns/oude-mechanismen/issues/115)
* **Review Records:** [005_design_007_egm_review.md](../reviews/005_design_007_egm_review.md)

---

## Overview

This design makes `type` the single front matter key that classifies a note on every canon tier, aligns the values shared between tiers, adds `reference` to the Tier 3 vocabulary, and migrates existing digest notes in place through `oude doctor --fix`. Legacy `entity_type` digests keep validating with a warning, so an engine upgrade never breaks a vault that has not migrated yet.

Issue #115 proposes picking one canonical key and deriving the other at read time. This design does both: `oude digest` derives `type` at read time from either key (making the transition safe), and a one-command physical migration ends the dual-key state on disk (making it finish).

### Background and Terminology

* **Campaign vault:** a downstream Git repository that is both an Obsidian vault (Obsidian is the local Markdown editor) and a Jekyll static site, parameterised by this engine. The two live vaults are `charged` and `hostile`. Their private `_gm-materials/` folder is synchronised by Obsidian Sync between two GM workstations, `ryu` and `artemis` ([ADR 003](../adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md)).
* **Canon tiers** (see `AGENTS.md` §4): Tier 1 is published notes (`campaigns/`, `directory/`, `systems/`), indexed into `.agents/context/catalog.json`. Tier 2 is behind-the-screen rulings and session notes; it does not use either key and is out of scope. Tier 3 is reference material.
* **Digest note:** a front-mattered Markdown note summarising one entity from an external sourcebook PDF, stored under `_gm-materials/digests/<source>/` and written by the `digest-book` skill. A *legacy flat digest* is an older single-file summary (`_gm-materials/digests/<source>.md`) with no front matter.
* **`oude`:** the CLI installed from this repository. `oude digest` (`scripts/generate_digests.py`) compiles `.agents/context/references.json` from digests, and `oude digest --validate` checks them. `oude doctor` (`src/oude_mechanismen/cli.py`) audits and, with `--fix`, repairs vault health.
* **`drive_dir`:** the root containing `_gm-materials/`, read from `drive_dir:` in `.agents/context/tier1_sources.yml` and resolved by `find_drive_dir()` in `scripts/generate_digests.py` (`.` in standard vaults since ADR 003).

## The Problem

Tier 1 notes classify themselves with `type`. That key is consumed by `jekyll/_plugins/data_extractor.rb`, `jekyll/_includes/connected_to.html`, `scripts/audit_coverage.py`, and the `add-character`, `add-chapter`, and `scribe-session` skills. Tier 3 digests use `entity_type` instead, validated by `oude digest --validate` and copied into `references.json`.

Issue #115 warns that the two keys *can* drift apart on digest notes. A manual survey of the live vaults on 2026-11-25 found no note carrying both keys yet, but confirmed the underlying inconsistency:

| Vault | Digest `*.md` | With `entity_type:` | With `type:` | Both | No front matter (legacy flat) |
| --- | --- | --- | --- | --- | --- |
| `charged` | 118 | 108 | 0 | 0 | 10 |
| `hostile` | 54 | 54 | 0 | 0 | 0 |

Survey command, run per vault from its root: `grep -rlE '^entity_type:' _gm-materials/digests | wc -l` (and likewise for `^type:`).

1. **Two keys for one concept:** classification lives in `type` in `catalog.json` but in `entity_type` in `references.json`, so any cross-tier query on classification must translate between both keys.
2. **Divergent values:** Tier 1 uses `people`; Tier 3 uses `person`.
3. **Vocabulary gap:** three `charged` digests (`dungeon_full_of_monsters/framework/*.md`) use `entity_type: reference`, which `VALID_ENTITY_TYPES` (`scripts/generate_digests.py:974`) rejects, so `oude digest --validate` fails on them today.

Jekyll never renders digests: `_gm-materials` is underscore-prefixed, gitignored, and listed under `exclude` in each vault's `_config.yml` (enforced by `oude doctor`). Choosing `type` therefore unifies the vocabulary for agents, skills, and Obsidian's front matter Properties view; it does not affect site rendering.

## Goals

* `type` is the only classification key written by the engine and its skills, and the only one emitted into `references.json`.
* Shared concepts use the Tier 1 values: `people`, `faction`, `location`, `creature`.
* Tier 3 keeps its additional values: `index`, `artefact`, `mechanic`, `table`, `reference`, `other`.
* Front-mattered digests migrate with one command (`oude doctor --fix`), without hand edits except for genuinely conflicting notes.
* No engine upgrade ever turns an unmigrated legacy `entity_type` digest into a validation failure.

## Non-Goals

* Enforcing a Tier 1 `type` vocabulary (Tier 1 values such as `session` stay free-form).
* Migrating the 10 legacy flat digests in `charged`. They keep failing `--validate` with the existing `missing YAML frontmatter block` error until retired under the legacy flat-digest guidance in `skills/digest-book/SKILL.md`.
* Adding `references.json` to `DERIVED_CACHE_FILES` / `DEFAULT_GITIGNORE`, which is tracked separately in [#118](https://github.com/terra-campaigns/oude-mechanismen/issues/118).
* Excluding Obsidian Sync conflict copies from digest scans (see Risks).
* Changing the Jekyll plugin, includes, or `catalog.json` schema, or rewriting Git history, published Tier 1 notes, or past `CHANGELOG.md` entries.

## Open Questions

None. The key, the value alignment, `reference`, and doctor-driven migration were decided in the GM workshop on 2026-11-25. The Round 1 review changes (indefinite legacy warning, automatic resolution of agreeing both-key pairs) are recorded in [005_design_007_egm_review.md](../reviews/005_design_007_egm_review.md).

## Technical Plan (Architecture)

### Component 1: Vocabulary and Canonical-Type Resolution

The Tier 3 vocabulary becomes `index`, `people`, `faction`, `location`, `creature`, `artefact`, `mechanic`, `table`, `reference`, `other`. The single legacy value mapping is `person` → `people`; any other legacy value passes through unchanged.

One shared helper resolves a note's canonical type from its parsed front matter, returning the canonical value and a state. Both the validator and the index compiler call it, so they cannot disagree.

| State | Front matter | Resolved value |
| --- | --- | --- |
| `canonical` | `type` only | `type` |
| `legacy` | `entity_type` only | mapped `entity_type` |
| `both_agree` | both, `type` equals mapped `entity_type` | `type` |
| `both_conflict` | both, values differ after mapping | none |
| `missing` | neither | none |

### Component 2: Validator (`oude digest --validate`)

| State | Result |
| --- | --- |
| `canonical`, value in vocabulary | Pass |
| `canonical`, value not in vocabulary (including `person`) | `[FAIL] file:1: frontmatter 'type' must be one of [...]` |
| `legacy`, mapped value in vocabulary | Pass with `[WARN] file:1: legacy 'entity_type' key; run 'oude doctor --fix' to migrate to 'type'` |
| `legacy`, mapped value not in vocabulary | `[FAIL]` (same message as invalid `type`) |
| `both_agree`, value in vocabulary | Pass with `[WARN] file:1: redundant legacy 'entity_type' key; run 'oude doctor --fix' to remove it` |
| `both_conflict` | `[FAIL] file:1: frontmatter 'type' and legacy 'entity_type' disagree; keep only 'type'` |
| `missing` | `[FAIL] file:1: frontmatter 'type' must be one of [...]` |

`file:1:` follows the existing validator convention (`scripts/generate_digests.py:1070-1082`), where line 1 denotes the front matter block. Warnings never change the exit code, and the legacy warning has no expiry: retiring legacy support would need its own issue and release note. Notes with no front matter keep the existing `missing YAML frontmatter block` failure.

### Component 3: Index (`compile_references()`)

`compile_references()` in `scripts/generate_digests.py` writes the resolved value as `type` into each `references.json` entry and no longer writes `entity_type`. When the resolved value is absent or outside the vocabulary, it prints a `[WARN]` to stderr and omits `type` for that entry, closing today's gap where invalid values are copied unvalidated.

No compatibility alias is emitted: `compile_references()` rewrites `references.json` wholesale on every `oude digest` run, and no bundled skill or script reads its `entity_type` field (`grep -rn entity_type skills/ src/ jekyll/` matches only `skills/digest-book/SKILL.md`, which documents note front matter). Vault-local scripts that read `entry["entity_type"]` must switch to `entry["type"]` on the first recompile after upgrading; `docs/MIGRATION_GUIDE.md` and `CHANGELOG.md` state this.

### Component 4: Migration and Doctor Check

* **`oude digest --migrate-type [--dry-run]`:** rewrites legacy digests under `<drive_dir>/_gm-materials/digests/` in place. A `legacy` note has its `entity_type:` line renamed to `type:` with the mapped value. A `both_agree` note has its `entity_type:` line removed. Every other note is left untouched. The rewrite is line-level, not a YAML load-and-dump round-trip, so comments, key order, quoting, and line endings survive. It reports counts for `migrated`, `conflicts`, `already canonical`, and `no front matter`, and lists each conflicting file.
* **`oude doctor`:** adds a `Digest type keys` check. Detection and repair both run through the script (`--migrate-type --dry-run` to check, `--migrate-type` with `--fix`) with `--repo-root <vault>`, so `drive_dir` resolution and the rewrite rules live only in `scripts/generate_digests.py`. Pending migrations or conflicts set the doctor exit code to 1. That is intentional: the doctor nags until the vault is migrated, while the validator, which gates `digest-book` publishing, only warns. When the digests directory does not exist (for example on CI), the check passes as skipped.

### Component 5: Documentation and Skills

* `skills/digest-book/SKILL.md` documents `type:` and the new vocabulary.
* ADR 003 and designs 003 and 004 each get a dated amendment note pointing here; accepted text is not rewritten.
* `docs/MIGRATION_GUIDE.md` gains an upgrade step, and `CHANGELOG.md` gets `Changed` and `Deprecated` entries.

## Alternatives Considered

### Alternative A: Keep `entity_type` on Digests

* **Pros:** No migration. The validator only needs to add `reference` and reject a stray `type:`.
* **Cons:** Two keys and two vocabularies for one concept persist across tiers.
* **Reason for Rejection:** It leaves the friction #115 targets in place; the GM workshop chose `type`.

### Alternative B: Use `type` but Keep Per-Tier Values (`person` in Tier 3)

* **Pros:** Avoids a value rewrite.
* **Cons:** A single `type: people` query still misses Tier 3 people.
* **Reason for Rejection:** The value rewrite costs nothing extra once the key rewrite runs.

### Alternative C: One-Off Script or Hard Switch

* **Pros:** Simplest code; no legacy branch in the validator.
* **Cons:** Any vault that upgrades the engine before migrating fails validation on every digest.
* **Reason for Rejection:** It breaks vaults on upgrade; doctor-driven migration plus an indefinite warning does not.

### Alternative D: Alias at Read Time Only (Issue #115's Proposal)

* **Pros:** Zero files rewritten; no Obsidian Sync exposure.
* **Cons:** Both keys and both vocabularies stay on disk permanently. Obsidian's Properties view and agents reading notes directly still see `entity_type: person`. The `digest-book` skill would keep writing the legacy form, or mixed forms would accumulate.
* **Reason for Rejection:** It hides the inconsistency rather than removing it. Component 3 already adopts the read-time alias for the transition, so physical migration is the only addition.

### Alternative E: Vault-State Migration Stamp

* **Pros:** Allows a hard failure on `entity_type` once a vault records that it has migrated.
* **Cons:** Adds a second hidden state that can itself drift from the notes, which is the same class of problem #115 targets.
* **Reason for Rejection:** The indefinite warning plus doctor's exit code gives enough pressure without new state.

## Non-Functional Requirements

* **Privacy:** the migration reads and writes only `_gm-materials/digests/` on local disk; no content leaves the machine.
* **Performance:** one pass over at most a few hundred small Markdown files; negligible.
* **Rollback:** reverting the engine restores `entity_type` handling. Migrated notes carry `type:`, which the old validator rejects, so rollback after migration needs `--migrate-type` reversed by hand or a vault snapshot. `docs/MIGRATION_GUIDE.md` Step 1 (snapshot the vault) already covers this.

## Risks and Mitigations

* **Front matter edge cases (quoted values, trailing comments, CRLF, duplicate keys):** the rewrite rules in the Detailed Implementation Plan pin the anchor, bounds, and newline handling, and any disagreement with `yaml.safe_load()` is classed as a conflict and fails loudly. New tests will cover each case.
* **Obsidian Sync race between `ryu` and `artemis`:** run the migration on one workstation only and let Sync propagate it (single-writer precondition, documented in the migration guide). The rewrite is designed to be idempotent. If Sync produces a conflict copy that reintroduces `entity_type`, the validator warns and the doctor flags it, so nothing is silently lost. Excluding conflict-copy filenames from every digest scan would change behaviour for all digest edits, not just this migration, so it is a non-goal.
* **External consumers of `references.json`:** the field rename is immediate on recompile; flagged in the migration guide and changelog.

### Future Improvements

* Retire legacy `entity_type` reading once no supported vault carries it (separate issue and release note).

## Detailed Implementation Plan

### Target Files

| Action | File | Change |
| --- | --- | --- |
| Modify | `scripts/generate_digests.py` | Vocabulary constants, `_canonical_type()` helper, validator rows (Component 2), `compile_references()` output (Component 3), `--migrate-type [--dry-run]` flag and `migrate_digest_types()` function |
| Modify | `src/oude_mechanismen/cli.py` | `Digest type keys` check in `_doctor()` |
| Modify | `tests/test_generate_digests.py` | Switch fixtures from `entity_type` to `type`; add validator, index, and migration cases |
| Modify | `tests/test_cli.py` | Doctor check cases |
| Modify | `skills/digest-book/SKILL.md` | Front matter example and value list (line 53) |
| Modify | `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md` | Dated amendment note covering §3.5.3 note template and §3.5.4 index schema |
| Modify | `docs/designs/003_adr_003_phase1_path_normalisation.md` | Dated amendment note |
| Modify | `docs/designs/004_adr_003_completion_and_semantic_digestion.md` | Dated amendment note |
| Modify | `docs/MIGRATION_GUIDE.md` | Upgrade step: single-writer `oude doctor --fix`, `references.json` field rename |
| Modify | `CHANGELOG.md` | `## [Unreleased]`: `Changed` and `Deprecated` entries |

Amendment note format, appended under the document header:

```markdown
> [!NOTE]
> Amended 2026-11-25 by [Design 007](../designs/007_unified_type_key_for_digests.md): digest notes and `references.json` use `type` (values `index | people | faction | location | creature | artefact | mechanic | table | reference | other`); `entity_type` is a deprecated alias.
```

### Implementation Details

* **Constants:** `VALID_DIGEST_TYPES = {"index", "people", "faction", "location", "creature", "artefact", "mechanic", "table", "reference", "other"}` replaces `VALID_ENTITY_TYPES`. `LEGACY_TYPE_VALUES = {"person": "people"}`. Mapping uses `LEGACY_TYPE_VALUES.get(value, value)`.
* **`_canonical_type(frontmatter) -> (value | None, state)`:** implements the Component 1 table; values are compared as stripped strings.
* **Migration rewrite rules (`migrate_digest_types(drive_dir, dry_run)`):**
  1. Read each `*.md` as UTF-8 with `newline=""` so CRLF is preserved. Locate the front matter block with the same regex as `_parse_frontmatter()` (`\A---\r?\n(.*?)\r?\n---\r?\n?`, line 106). Files without a block go to `no front matter`.
  2. Inside the block only, match column-0 lines with `^entity_type[ \t]*:[ \t]*(?P<q>["']?)(?P<val>[^"'#\r\n]*?)(?P=q)(?P<rest>[ \t]*(?:#[^\r\n]*)?)(?P<eol>\r?\n|$)`.
  3. Conflict (file untouched, listed): zero or more than one match while `yaml.safe_load()` reports `entity_type`; the regex value disagrees with the parsed value; state `both_conflict`; or a mapped value outside `VALID_DIGEST_TYPES`.
  4. `legacy`: replace the line with `type:` plus the original spacing, quote character, mapped value, `rest`, and `eol`. `both_agree`: delete the line, including its `eol`.
  5. Write via a sibling temporary file without the `.md` suffix, then `os.replace()`. `--dry-run` writes nothing.
  6. Exit codes: without `--dry-run`, 1 if any conflicts remain, otherwise 0. With `--dry-run`, 1 if any file would be migrated or conflicts, otherwise 0. A missing digests directory prints a skip notice and exits 0.
* **CLI wiring:** add `--migrate-type` and `--dry-run` to `main()` in `scripts/generate_digests.py` as an `elif args.migrate_type:` branch alongside `--validate`.
* **Doctor:** in `_doctor()`, call `_run_script("generate_digests.py", ["--repo-root", str(vault), "--migrate-type", "--dry-run"])`. If it returns 0, print `✓ Digest type keys`. Otherwise, with `fix`, call it again without `--dry-run` and print `✓` on 0 or `⚠ Digest type conflicts need manual edits` on 1. Without `fix`, print `⚠ Legacy digest type keys (run oude doctor --fix)`. Any `⚠` sets `all_passed = False`.

### Phases

From the repository root, each phase must leave the named tests passing:

1. **Vocabulary, helper, validator:** constants, `_canonical_type()`, Component 2, and fixture updates. Gate: `python3 -m unittest tests.test_generate_digests -v`.
2. **Index:** Component 3. Gate: same command.
3. **Migration:** `migrate_digest_types()` and CLI flags. Gate: same command.
4. **Doctor:** `_doctor()` check. Gate: `python3 -m unittest tests.test_cli -v`.
5. **Documentation:** skill, amendment notes, migration guide, changelog. Gate: the full test suite, the same command CI runs (`python3 -m unittest discover -s tests -v`, `.github/workflows/ci.yml:42`).

### Verification Plan

* **Validator:** canonical `type`; invalid `type`; `type: person` fails; legacy `entity_type: person` passes with a warning; `both_agree` passes with a warning; `both_conflict` fails; neither key fails; `type: reference` passes; no front matter keeps the existing failure.
* **Index:** a legacy `entity_type: person` note produces `"type": "people"` in its `references.json` entry and no `entity_type` key; an invalid value produces a stderr `[WARN]` and an entry without `type`.
* **Migration:** `legacy` rewrite preserving key order and trailing comment; quoted `entity_type: "person"  # note` becomes `type: "people"  # note`; a CRLF file stays CRLF byte-for-byte outside the changed line; `both_agree` drops the legacy line; `both_conflict`, invalid values, and duplicate keys are untouched, listed, and exit 1; a second run is a no-op; `--dry-run` writes nothing and exits 1 while work is pending; a missing digests directory exits 0.
* **Doctor:** warns on legacy keys; `--fix` migrates them; reports conflicts; skips when the digests directory is absent; `oude doctor --vault <other> --fix` run from a different working directory migrates `<other>`, not the working directory.
* **Live-vault acceptance (manual, after merge):** in `charged` and `hostile`, run `oude doctor --fix` on one workstation, then `oude digest --validate _gm-materials/digests`. Among the front-mattered notes (162 as of the 2026-11-25 survey), including the three `reference` notes, there must be zero `[FAIL]` and zero legacy-key `[WARN]` lines. In `charged` the exit code may remain 1 solely because of the 10 legacy flat digests.
