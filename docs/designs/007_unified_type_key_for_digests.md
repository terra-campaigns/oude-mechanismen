# Unified `type` Front Matter Key Across Tier 1 Notes and Tier 3 Digests

* **Author:** `efsalvarenga`
* **Status:** Proposed (Post-Review Revision — Round 2 Resolved)
* **Date:** 2026-11-25
* **Addresses:** [#115](https://github.com/terra-campaigns/oude-mechanismen/issues/115)
* **Review Records:** [005_design_007_egm_review.md](../reviews/005_design_007_egm_review.md)

---

## Overview

This design proposes making `type` the single front matter key that classifies a note on every canon tier, aligning the values shared between tiers, adding `reference` to the Tier 3 vocabulary, and migrating existing digest notes in place through `oude doctor --fix`.

Issue #115 proposes picking one canonical key and deriving the other at read time. This design combines both approaches: `oude digest` will derive `type` at read time from either key (making the transition safe), and a one-command physical migration will end the dual-key state on disk.

### Background and Terminology

* **Engine (`oude-mechanismen`):** this repository — the shared procedural tooling, agent skills, and Jekyll plugin bundle that parameterises downstream tabletop RPG campaign vaults.
* **Campaign vault:** a downstream Git repository that acts as both an Obsidian vault (Obsidian is the local Markdown editor, whose *Properties view* edits YAML front matter visually) and a Jekyll static website. The two live vaults are `charged` and `hostile`. Their private `_gm-materials/` folder is synchronised peer-to-peer between two Game Master (GM) workstations, `ryu` and `artemis`, via *Obsidian Sync* (see [Architecture Decision Record (ADR) 003](../adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md) for the sync topology; concurrent edits can produce `*conflicted copy*.md` sibling files).
* **Front matter:** the leading YAML metadata block delimited by `---` lines at the top of a Markdown note, for example:

  ```yaml
  ---
  source: harbour_guide
  tier: 3
  type: faction
  title: Harbour Guild
  ---
  ```

* **Canon tiers & compiled indices** (see [AGENTS.md §4](../../AGENTS.md#4-canon--context-architecture)):
  * **Tier 1** is published, player-facing notes (`campaigns/`, `directory/`, `systems/`), indexed by Jekyll into `.agents/context/catalog.json` (the Tier 1 note catalogue).
  * **Tier 2** is behind-the-screen GM rulings and session notes; it does not use `type` or `entity_type` and is out of scope.
  * **Tier 3** is distilled reference material under `_gm-materials/digests/`, indexed by `oude digest` into `.agents/context/references.json` (the Tier 3 digest index).
* **Digest note & sourcebook:** a *sourcebook* is a commercial tabletop RPG rulebook PDF stored locally outside Git. A *digest note* is a front-mattered Markdown summary of one entity distilled from a sourcebook under `_gm-materials/digests/<source>/` by the `digest-book` skill (a *skill* is a reusable agent procedure file under `skills/<name>/SKILL.md`). A *legacy flat digest* is an older single-file summary (`_gm-materials/digests/<source>.md`) with no front matter.
* **`oude` CLI:** the command-line tool installed from this repository. `oude digest` (`scripts/generate_digests.py`) compiles `.agents/context/references.json` from digests, and `oude digest --validate` checks them. `oude doctor` (`src/oude_mechanismen/cli.py`) audits and, with `--fix`, repairs vault health.
* **`drive_dir` & `tier1_sources.yml`:** `.agents/context/tier1_sources.yml` is a per-vault configuration file scaffolded from `templates/tier1_sources.yml.template`. Its `drive_dir:` setting points to the root containing `_gm-materials/`, resolved by `find_drive_dir()` in `scripts/generate_digests.py` (`.` in standard vaults since ADR 003).
* **CI & CRLF:** *CI* is Continuous Integration (automated checks such as GitHub Actions). *CRLF* is the Windows two-byte line ending (`\r\n`).

## The Problem

Tier 1 notes classify themselves with `type`. That key is consumed by `jekyll/_plugins/data_extractor.rb`, `jekyll/_includes/connected_to.html`, `scripts/audit_coverage.py`, and the `add-character`, `add-chapter`, and `scribe-session` skills. Tier 3 digests use `entity_type` instead, validated by `oude digest --validate` and copied into `.agents/context/references.json`.

Issue #115 warns that the two keys *can* drift apart on digest notes. A manual survey of the live vaults on 2026-11-25 found no note carrying both keys yet, but confirmed the underlying inconsistency:

| Vault | Digest `*.md` | With `entity_type:` | With `type:` | Both | No front matter (legacy flat) |
| --- | --- | --- | --- | --- | --- |
| `charged` | 118 | 108 | 0 | 0 | 10 |
| `hostile` | 54 | 54 | 0 | 0 | 0 |

Reproducible survey commands, run per vault from its repository root:

```bash
d=_gm-materials/digests
find "$d" -name '*.md' | wc -l                                                         # Digest *.md
grep -rlE '^entity_type:' "$d" --include='*.md' | wc -l                                # With entity_type:
grep -rlE '^type:' "$d" --include='*.md' | wc -l                                       # With type:
grep -rlE '^type:' "$d" --include='*.md' | xargs -r grep -lE '^entity_type:' | wc -l   # Both
comm -23 <(find "$d" -name '*.md' | sort) <(grep -rlE '^---$' "$d" --include='*.md' | sort) | wc -l  # No front matter
grep -rlE '^entity_type:[[:space:]]*reference' "$d" --include='*.md' | wc -l           # reference notes
```

1. **Two keys for one concept:** classification lives in `type` in `.agents/context/catalog.json` but in `entity_type` in `.agents/context/references.json`, so any cross-tier query on classification must translate between both keys.
2. **Divergent values:** Tier 1 uses `people`; Tier 3 uses `person`.
3. **Vocabulary gap:** three `charged` digests (`dungeon_full_of_monsters/framework/*.md`) use `entity_type: reference`, which `VALID_ENTITY_TYPES` (`scripts/generate_digests.py:974`) rejects, so `oude digest --validate` fails on them today.

Jekyll never renders digests: `_gm-materials` is underscore-prefixed, gitignored, and listed under `exclude` in each vault's `_config.yml` (enforced by `oude doctor`). Choosing `type` therefore unifies the vocabulary for agents, skills, and Obsidian's front matter Properties view; it does not affect site rendering.

## Goals

* `type` is the only classification key written by the engine and its skills, and the only one emitted into `.agents/context/references.json`.
* Shared concepts use the Tier 1 values: `people`, `faction`, `location`, `creature`.
* Tier 3 keeps its additional values: `index`, `artefact`, `mechanic`, `table`, `reference`, `other`.
* Front-mattered digests migrate with one command (`oude doctor --fix`), without hand edits except for genuinely conflicting or malformed notes.
* No engine upgrade ever turns an unmigrated legacy `entity_type` digest into a validation failure.

## Non-Goals

* Enforcing a Tier 1 `type` vocabulary (Tier 1 values such as `session` stay free-form).
* Migrating files under `templates/`: verified empty for `entity_type` (`grep -rn entity_type templates/` returns zero matches), so no template changes are required.
* Migrating the 10 legacy flat digests in `charged`. They keep failing `--validate` with the existing `missing YAML frontmatter block` error until retired under the legacy flat-digest guidance in `skills/digest-book/SKILL.md`.
* Adding `.agents/context/references.json` to `DERIVED_CACHE_FILES` / `DEFAULT_GITIGNORE`, which is tracked separately in [#118](https://github.com/terra-campaigns/oude-mechanismen/issues/118).
* Excluding Obsidian Sync conflict copies from digest scans (see `Risks & Mitigations`).
* Changing the Jekyll plugin, includes, or `.agents/context/catalog.json` schema, or rewriting Git history, published Tier 1 notes, or past `CHANGELOG.md` entries.

## Open Questions

None. The key, the value alignment, `reference`, and doctor-driven migration were decided in the GM workshop on 2026-11-25. Round 1 and Round 2 review resolutions are recorded in [005_design_007_egm_review.md](../reviews/005_design_007_egm_review.md).

## Technical Plan (Architecture)

### Component 1: Vocabulary and Canonical-Type Resolution

The Tier 3 vocabulary will become `index`, `people`, `faction`, `location`, `creature`, `artefact`, `mechanic`, `table`, `reference`, `other`. The single legacy value mapping will be `person` → `people`; any other legacy string value passes through unchanged.

One shared helper will resolve a note's canonical type from its parsed front matter mapping and raw front matter block, returning the canonical value and a state. The validator, index compiler, and migrator will all call it, so they agree by construction.

| State | Front matter | Resolved value |
| --- | --- | --- |
| `canonical` | single `type` string only | stripped `type` |
| `legacy` | single `entity_type` string only | mapped stripped `entity_type` |
| `both_agree` | single `type` and single `entity_type` strings; `type` equals mapped `entity_type` | stripped `type` |
| `both_conflict` | single `type` and single `entity_type` strings; values differ after mapping | none |
| `duplicate_key` | more than one column-0 `type:` or `entity_type:` line in the raw front matter block | none |
| `invalid` | present `type` or `entity_type` whose parsed YAML value is `None` or not a `str` (e.g. list, mapping, bool, int), or empty after stripping | none |
| `missing` | neither key present | none |

### Component 2: Validator (`oude digest --validate`)

| State | Result |
| --- | --- |
| `canonical`, value in vocabulary | Pass |
| `canonical`, value not in vocabulary (including `person`) | `[FAIL] file:1: frontmatter 'type' must be one of [...]` |
| `legacy`, mapped value in vocabulary | Pass with `[WARN] file:1: legacy 'entity_type' key; run 'oude doctor --fix' to migrate to 'type'` |
| `legacy`, mapped value not in vocabulary | `[FAIL]` (same message as invalid `type`) |
| `both_agree`, value in vocabulary | Pass with `[WARN] file:1: redundant legacy 'entity_type' key; run 'oude doctor --fix' to remove it` |
| `both_agree`, value not in vocabulary | `[FAIL]` (same message as invalid `type`) |
| `both_conflict` | `[FAIL] file:1: frontmatter 'type' and legacy 'entity_type' disagree; keep only 'type'` |
| `duplicate_key` | `[FAIL] file:1: duplicate frontmatter key '<key>'; keep a single 'type'` |
| `invalid` | `[FAIL] file:1: frontmatter 'type' must be one of [...]` |
| `missing` | `[FAIL] file:1: frontmatter 'type' must be one of [...]` |

`file:1:` follows the existing validator convention (`scripts/generate_digests.py:1070-1096`), where line 1 denotes the front matter block. Warnings will never change the exit code, and the legacy warning has no expiry: retiring legacy support would need its own issue and release note. Notes with no front matter keep the existing `missing YAML frontmatter block` failure.

### Component 3: Index (`compile_references()`)

`compile_references()` in `scripts/generate_digests.py` will write the resolved value as `type` into each `.agents/context/references.json` entry and will no longer write `entity_type`. When the resolved value is absent or outside the vocabulary (including `invalid`, `duplicate_key`, and `both_conflict`), it will print a `[WARN]` to stderr and omit `type` for that entry, closing today's gap where invalid values are copied unvalidated.

No compatibility alias will be emitted: `compile_references()` rewrites `.agents/context/references.json` wholesale on every `oude digest` run, and no bundled skill or script reads its `entity_type` field (`git grep -n entity_type -- scripts/ skills/ src/ jekyll/` matches only `skills/digest-book/SKILL.md`, which documents note front matter, and `scripts/generate_digests.py`, which writes and validates the field itself). Vault-local scripts that read `entry["entity_type"]` must switch to `entry["type"]` on the first recompile after upgrading; `docs/MIGRATION_GUIDE.md` and `CHANGELOG.md` will state this.

### Component 4: Migration and Doctor Check

* **`oude digest --migrate-type [--dry-run]`:** will rewrite legacy digests under `<drive_dir>/_gm-materials/digests/` in place. A `legacy` note with a valid mapped value will have its `entity_type:` line renamed to `type:` with the mapped value. A `both_agree` note with a valid value will have its `entity_type:` line removed (counting towards `migrated`). Every other note will be left untouched; front-mattered `missing`-state notes are intentionally outside migrator scope because `oude digest --validate` already rejects them. The rewrite will be line-level, not a YAML load-and-dump round-trip, so comments, key order, quoting, spacing, permissions, and line endings survive. It will report counts for `migrated`, `conflicts`, `already canonical`, and `no front matter`, and list each conflicting file.
* **`oude doctor`:** will add a `Digest type keys` check. Detection and repair will both run through `scripts/generate_digests.py` (`--migrate-type --dry-run` during audit; `--migrate-type` when `oude doctor --fix` is passed) with `--repo-root <vault>`, so `drive_dir` resolution and the rewrite rules live in one place. Pending migrations or conflicts will set the doctor exit code to 1. That is intentional: on local GM workstations (where `_gm-materials/digests/` exists), `oude doctor` provides the migration prompt until `oude doctor --fix` runs, while the validator, which gates `digest-book` publishing, only warns. When the digests directory does not exist (as on public vault CI runners, where `_gm-materials/` is gitignored), the script prints a skip notice and exits 0, and `oude doctor` passes cleanly.

### Component 5: Documentation and Skills

* `skills/digest-book/SKILL.md` will document `type:` and the new vocabulary.
* ADR 003 and designs 003 and 004 will each get a dated amendment note pointing here; accepted text will not be rewritten.
* `docs/MIGRATION_GUIDE.md` will gain an upgrade step, and `CHANGELOG.md` will get `Changed` and `Deprecated` entries.

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

* **Privacy:** the migration will read and write only `_gm-materials/digests/` on local disk; no content leaves the machine.
* **Performance:** one pass over at most a few hundred small Markdown files; negligible.
* **Rollback:** reverting the engine restores `entity_type` handling. Migrated notes carry `type:`, which the old validator rejects, so rollback after migration needs `--migrate-type` reversed by hand or a vault snapshot. `docs/MIGRATION_GUIDE.md` Step 1 (snapshot the vault) already covers this.

## Risks & Mitigations

* **Front matter edge cases (quoted values, trailing comments, CRLF, non-string/null values, malformed YAML, duplicate keys, symlinks):** the rewrite rules in the Detailed Implementation Plan pin the anchor, bounds, newline handling, permission preservation, and symlink guard; any parse error, duplicate key, non-string/empty value, or disagreement with `yaml.safe_load()` is classed as a conflict and fails loudly. New tests will cover each case.
* **Obsidian Sync race between `ryu` and `artemis`:** single-writer migration (run `oude doctor --fix` on one workstation only and let Sync propagate it) will be documented as an operator precondition in `docs/MIGRATION_GUIDE.md`; per ADR 003 Pillar 2, the CLI cannot enforce Obsidian Sync state. The rewrite is designed to be idempotent, and dot-prefixed temp files avoid Sync upload during writes. If Sync still produces a conflict copy (`*conflicted copy*.md`), `compile_references()` will index it as an extra `.agents/context/references.json` entry and any reintroduced `entity_type` will trigger validator warnings and doctor failure until the operator deletes the conflict copy and re-runs `oude digest`. Excluding conflict-copy filenames from every digest scan would alter behaviour for all digest editing beyond #115 and stays a non-goal.
* **Local / self-hosted `oude doctor` enforcement hazard:** termination of the dual-key state relies on running `oude doctor` locally on a workstation (where `_gm-materials/digests/` exists). Standard public vault CI skips the check because `_gm-materials/` is gitignored, so public CI will not break on upgrade; however, any local hook or self-hosted runner that mounts `_gm-materials/` and gates on `oude doctor` will exit 1 after upgrading until `oude doctor --fix` runs. `docs/MIGRATION_GUIDE.md` will document this explicitly.
* **External consumers of `.agents/context/references.json`:** the field rename is immediate on recompile; flagged in the migration guide and changelog.

### Additional Resources

* Issue [#115](https://github.com/terra-campaigns/oude-mechanismen/issues/115) — *Unify `entity_type` and `type` on digest stubs*.
* Issue [#118](https://github.com/terra-campaigns/oude-mechanismen/issues/118) — *Audit `.agents/context/references.json` against `DERIVED_CACHE_FILES` and `DEFAULT_GITIGNORE`*.
* [ADR 003: Dual-Workstation Topology, Four-Pillar Storage, and Semantic Wiki Ingestion](../adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md).
* [005_design_007_egm_review.md](../reviews/005_design_007_egm_review.md) — Round 1 and Round 2 EGM review findings and resolutions.

### Future Improvements

* Retire legacy `entity_type` reading once no supported vault carries it (separate issue and release note).

## Detailed Implementation Plan

### Target Files to Create/Modify

| Action | File | Change |
| --- | --- | --- |
| Modify | `scripts/generate_digests.py` | Shared `FRONTMATTER_BLOCK_RE`, vocabulary constants, `_canonical_type()` helper, validator rows (Component 2), `compile_references()` output (Component 3), mutually exclusive CLI mode group + `--migrate-type [--dry-run]` flag, and `migrate_digest_types()` function |
| Modify | `src/oude_mechanismen/cli.py` | `Digest type keys` check in `_doctor()` |
| Modify | `tests/test_generate_digests.py` | Switch fixtures from `entity_type` to `type`; add validator, index, CLI dispatch, and migration cases |
| Modify | `tests/test_cli.py` | Doctor check cases |
| Modify | `skills/digest-book/SKILL.md` | Front matter example and value list (line 53) |
| Modify | `docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md` | Dated amendment note covering §3.5.3 note template and §3.5.4 index schema |
| Modify | `docs/designs/003_adr_003_phase1_path_normalisation.md` | Dated amendment note |
| Modify | `docs/designs/004_adr_003_completion_and_semantic_digestion.md` | Dated amendment note |
| Modify | `docs/MIGRATION_GUIDE.md` | Upgrade step: single-writer `oude doctor --fix`, local/self-hosted doctor exit-1 note, and `references.json` field rename |
| Modify | `CHANGELOG.md` | `## [Unreleased]`: `Changed` and `Deprecated` entries |

Amendment note format, appended under the document header:

```markdown
> [!NOTE]
> Amended 2026-11-25 by [Design 007](../designs/007_unified_type_key_for_digests.md): digest notes and `references.json` use `type` (values `index | people | faction | location | creature | artefact | mechanic | table | reference | other`); `entity_type` is a deprecated alias.
```

### Implementation Details

* **Constants & shared regex:**
  * Extract `FRONTMATTER_BLOCK_RE = re.compile(r"\A---\r?\n(.*?)\r?\n---\r?\n?", re.DOTALL)` and use it in both `_parse_frontmatter()` and `migrate_digest_types()`.
  * `VALID_DIGEST_TYPES = {"index", "people", "faction", "location", "creature", "artefact", "mechanic", "table", "reference", "other"}` replaces `VALID_ENTITY_TYPES`.
  * `LEGACY_TYPE_VALUES = {"person": "people"}`. Mapping uses `LEGACY_TYPE_VALUES.get(value, value)` only after confirming `isinstance(value, str)`.
* **`_canonical_type(frontmatter, raw_block="") -> (value | None, state)`:** implements the Component 1 table:
  1. Scan `raw_block` (with `re.MULTILINE`) for column-0 `^type[ \t]*:` and `^entity_type[ \t]*:` lines; if either key appears more than once, return `(None, "duplicate_key")` (recording the offending key name for the validator error).
  2. Inspect `frontmatter` for `"type"` and `"entity_type"`. If a present key's value is `None` or not a `str` (or empty after `.strip()`), return `(None, "invalid")` — never calling `.strip()` on non-strings or indexing `LEGACY_TYPE_VALUES` with unhashable types.
  3. Otherwise compare stripped strings (with `entity_type` mapped through `LEGACY_TYPE_VALUES`) to return `canonical`, `legacy`, `both_agree`, `both_conflict`, or `missing`.
  4. Case-variant keys (e.g. `Entity_Type:`) are intentionally ignored and resolve as `missing` (failing validation; untouched by migration).
* **Migration rewrite rules (`migrate_digest_types(drive_dir, dry_run)`):**
  1. Read each `*.md` under `<drive_dir>/_gm-materials/digests/` as UTF-8 with `newline=""` so CRLF is preserved. Locate the front matter block with `FRONTMATTER_BLOCK_RE`, setting `raw_block = match.group(0)` (the full `---`…`---` matched block, so every key line inside it terminates with a line ending before the closing `---`). Files without a leading `---` block go to `no front matter`.
  2. Parse front matter with `_parse_frontmatter()` to obtain `loaded` and resolve via `_canonical_type(loaded, raw_block)`. Inside `raw_block` only, match column-0 lines with `re.compile(r'^entity_type(?P<colon>[ \t]*:[ \t]*)(?P<q>["\']?)(?P<val>[^"\'#\r\n]*?)(?P=q)(?P<rest>[ \t]*(?:#[^\r\n]*)?)(?P<eol>\r?\n|$)', re.MULTILINE)`.
  3. Conflict (file untouched, listed, exits 1), evaluated in order so non-string values never reach `.strip()`: (a) `md_file.is_symlink()`; (b) `_parse_frontmatter()` reports malformed YAML (`yaml.YAMLError`) or a non-mapping header; (c) state is `duplicate_key`, `invalid` (including empty `entity_type:` where YAML parses `None` and regex captures `""`), or `both_conflict`; (d) state is `legacy` or `both_agree` and either the regex yields zero or more than one match, `m["val"].strip()` disagrees with `loaded["entity_type"].strip()`, or the resolved value is outside `VALID_DIGEST_TYPES`.
  4. `legacy` (valid): replace the matched line inside `raw_block` with `f"type{m['colon']}{m['q']}{mapped}{m['q']}{m['rest']}{m['eol']}"` and increment `migrated`. `both_agree` (valid): delete the matched line including its `eol` inside `raw_block` (leaving no stray blank line before the closing `---`) and increment `migrated`. `canonical` (valid): increment `already canonical`. `missing`: leave untouched (handled by `--validate`).
  5. Durable atomic write (skipped on `--dry-run`): write to a dot-prefixed sibling temporary file (`f".{md_file.name}.{os.getpid()}.tmp"`, excluded from both `rglob("*.md")` and Obsidian Sync's default dotfile exclusion), preserve file mode via `os.chmod(tmp_path, stat.S_IMODE(md_file.stat().st_mode))`, flush and `os.fsync()` the temp file (and parent directory fd where supported on POSIX) before `os.replace(tmp_path, md_file)`, and unlink `tmp_path` in an exception handler if anything fails before replace.
  6. Exit codes: without `--dry-run`, 1 if any conflicts remain, otherwise 0. With `--dry-run`, 1 if any file would be migrated or conflicts, otherwise 0. A missing digests directory prints a skip notice and exits 0.
* **CLI wiring (`scripts/generate_digests.py:main()`):** place `--extract`, `--validate`, `--scaffold`, and `--migrate-type` in an `argparse` mutually exclusive group; add `--dry-run` and reject `--dry-run` without `--migrate-type` via `parser.error("--dry-run requires --migrate-type")` so `--dry-run` can never fall through to `compile_references()`.
* **Doctor (`src/oude_mechanismen/cli.py:_doctor()`):** call `_run_script("generate_digests.py", ["--repo-root", str(vault), "--migrate-type", "--dry-run"])`. If it returns 0, print `✓ Digest type keys`. Otherwise, when `fix` is true, call `_run_script("generate_digests.py", ["--repo-root", str(vault), "--migrate-type"])` and print `✓` on 0 or `⚠ Digest type conflicts need manual edits` on 1. When `fix` is false, print `⚠ Legacy digest type keys (run oude doctor --fix)`. Any `⚠` sets `all_passed = False`.

### Phases

From the repository root, each phase must leave the named tests passing:

1. **Vocabulary, helper, validator:** shared `FRONTMATTER_BLOCK_RE`, constants, `_canonical_type()`, Component 2, and fixture updates. Gate: `python3 -m unittest tests.test_generate_digests -v`.
2. **Index:** Component 3. Gate: same command.
3. **Migration & CLI dispatch:** `migrate_digest_types()`, mutually exclusive CLI flags, and `--dry-run` guard. Gate: same command.
4. **Doctor:** `_doctor()` check. Gate: `python3 -m unittest tests.test_cli -v`.
5. **Documentation:** skill, amendment notes, migration guide, changelog. Gate: the full test suite, the same command CI runs (`python3 -m unittest discover -s tests -v`, `.github/workflows/ci.yml:42`).

### Verification Plan

* **Validator:** canonical `type`; invalid `type`; `type: person` fails; legacy `entity_type: person` passes with a warning; out-of-vocabulary `legacy` (`entity_type: bogus`) and `both_agree` (`type: bogus` + `entity_type: bogus`) fail; valid `both_agree` passes with a warning; `both_conflict` fails; neither key fails; `type: reference` passes; non-string values (`entity_type: [a, b]`, `type: 42`) and null/empty values (`type:`, `entity_type:`) fail without raising exceptions; duplicate column-0 `type:`/`entity_type:` keys fail consistently with the migrator; no front matter keeps the existing failure.
* **Index:** a legacy `entity_type: person` note writes `"type": "people"` into its `.agents/context/references.json` entry and no `entity_type` key; an invalid, duplicate-key, or conflicting value prints a stderr `[WARN]` and omits `type` from the entry.
* **Migration & CLI dispatch:** `legacy` rewrite preserving key order, spacing around `:`, and trailing comment; quoted `entity_type: "person"  # note` becomes `type: "people"  # note`; a CRLF file stays CRLF byte-for-byte outside the changed line; file permissions (`0600`) are preserved; `both_agree` (including when `entity_type:` is the last line before `---`) drops the legacy line cleanly with no stray blank line and counts as `migrated`; `both_conflict`, invalid/empty/non-string values, out-of-vocabulary values (`entity_type: bogus`), regex/YAML disagreement (`entity_type: per#son`), malformed YAML (`entity_type: "person'`), duplicate keys, and symlinked digests are untouched, listed, and exit 1; case-variant keys (`Entity_Type:`) and `missing`-state notes are left untouched; a second run is a no-op; `--dry-run` writes nothing and exits 1 while work is pending; `--dry-run` without `--migrate-type` exits non-zero without touching `references.json`; combined mode flags (e.g. `--validate --migrate-type`) exit non-zero; a missing digests directory exits 0.
* **Doctor:** warns on legacy keys; `--fix` migrates them; reports conflicts; skips when the digests directory is absent; `oude doctor --vault <other> --fix` run from a different working directory migrates `<other>`, not the working directory.
* **Live-vault acceptance (manual, after merge):** in `charged` and `hostile`, run `oude doctor --fix` on one workstation, then `oude digest --validate _gm-materials/digests`. Among the front-mattered notes (162 as of the 2026-11-25 survey), including the three `reference` notes, there must be zero `[FAIL]` and zero legacy-key `[WARN]` lines. In `charged` the exit code may remain 1 solely because of the 10 legacy flat digests.

---

<!-- Provenance: Indicates initial structural drafting via Elephant-Goldfish Model (EGM). -->

*Drafted with Elephant-Goldfish Model (EGM)*
