# EGM Review Summary — Design 007 (Issue #115)

* **Author:** `efsalvarenga`
* **Status:** Complete — Round 1 & Round 2 Findings Resolved
* **Date:** 2026-11-25
* **Addresses:** [#115](https://github.com/terra-campaigns/oude-mechanismen/issues/115)
* **Target Document:** [007_unified_type_key_for_digests.md](../designs/007_unified_type_key_for_digests.md)

---

## Overview

[007_unified_type_key_for_digests.md](../designs/007_unified_type_key_for_digests.md) underwent two full Elephant-Goldfish Model review rounds: Round 1 (uninterrupted five-stage flow covering Stages 5–9) and Round 2 (fresh-context eight-lens review posted on [PR #124](https://github.com/terra-campaigns/oude-mechanismen/pull/124#issuecomment-7175022728)).

## Round 1 Verdict and Resolutions

**Verdict:** implement-with-changes. 2 Blockers, 13 Majors, about 30 Nits. The architecture (single `type` key, aligned values, read-time canonical index, line-preserving doctor migration) was confirmed as the simplest root-cause fix.

### Blockers

1. **B-1 (release-count deprecation window):** Accepted. Legacy `entity_type` on its own is now a `[WARN]` in every version, with no expiry. Pressure to migrate comes from `oude doctor` exit code 1. Retiring legacy support is listed under Future Improvements and needs its own issue. This relaxes the workshop's one-release window, and Alternative E (vault-state stamp) records why the stamp was not adopted.
2. **B-2 (false "gitignored derived cache" claim):** Accepted. The rationale is now the verified one: `compile_references()` rewrites `references.json` wholesale, and no bundled consumer reads `entity_type`. The gitignore gap is deferred to the existing [#118](https://github.com/terra-campaigns/oude-mechanismen/issues/118) rather than folded in.

### Majors

1. **M-1, M-2 (doctor vault and `drive_dir`):** Accepted. The doctor delegates both detection (`--migrate-type --dry-run`) and repair to `generate_digests.py --repo-root <vault>`, so `find_drive_dir()` is the single resolver. A `--vault` different from the working directory is covered by a test.
2. **M-3 (both-keys stricter than #115):** Accepted. Agreeing pairs warn and are fixed automatically; only genuine conflicts fail. This overrides the workshop's "error when both keys are present", aligning with the issue text.
3. **M-4 (Obsidian Sync conflict copies):** Partially accepted. The design documents single-writer migration as a precondition and notes that reintroduced legacy keys are surfaced by the validator warning and doctor. Excluding `*conflict*` filenames from every scan was rejected as a behaviour change for all digest edits, beyond this design's scope.
4. **M-5 (rewrite rules):** Accepted. Exact regex, front matter bounds, `newline=""` CRLF preservation, quote preservation, identity fallback mapping, a parse-agreement conflict rule, and exit codes for `--dry-run` are specified.
5. **M-6 (phases):** Accepted. Five phases, each with a gate command.
6. **M-7 (acceptance ambiguity):** Accepted. Exit code 1 may remain only because of the legacy flat digests; the 162 count is labelled as a dated survey with its command.
7. **M-8 (Target Files paths and actions):** Accepted.
8. **M-9 (verification edge cases):** Accepted. Quoted, commented, CRLF, duplicate-key, and dry-run cases are listed.
9. **M-10, M-13 (alternatives):** Accepted. Added Alternative D (alias at read time, the issue's own proposal) and Alternative E (vault stamp); all alternatives use the Pros, Cons, and Reason for Rejection template.
10. **M-11 (undefined vocabulary):** Accepted. Added Background and Terminology.
11. **M-12 (overclaims):** Accepted. Corrected the `crosslink-tiers` claim, the present-tense test claims, the review-record header, and the issue paraphrase. Extended the amendment list to design 003 and ADR 003 §3.5.3–3.5.4. `compile_references()` now warns and omits invalid types.

### Nits

* Kept the `file:1:` message convention (N-1).
* Moved the Python constants and rewrite mechanics into the Detailed Implementation Plan (N-2).
* Renamed the heading to `Technical Plan (Architecture)` (N-3). The CUJ section and data-flow diagram were consciously omitted given the scope.
* Applied the comprehension and style nits (N-4, N-5): full paths, `session` instead of `epilogue`, collapsed Open Questions, a grep command for the no-reader claim, the exit-code wording, and an amendment-note example.
* N-6 needed no change.


## Round 2 Verdict and Resolutions (PR #124)

**Verdict:** revisions-required — 0 Blockers, 8 technical Majors, 3 comprehension Majors, and 4 Nit groups (`egm-codebase-details` approved with all 12 codebase claims verified; `egm-zoom-out`, `egm-inventive-catalyst`, `egm-structural` approved with nits).

All 15 findings were resolved via `/egm-resolve` in the Round 2 revision of [007_unified_type_key_for_digests.md](../designs/007_unified_type_key_for_digests.md):

1. **Pathological values & duplicate keys (Major 1):** Added `invalid` (non-string/`None`/empty values guarded with `isinstance(..., str)`) and `duplicate_key` (column-0 duplicate `type:`/`entity_type:` detection in raw front matter) states to `_canonical_type()` and Component 2, aligning `--validate`, `compile_references()`, and `--migrate-type`.
2. **Malformed YAML in migration (Major 2):** Routed `_parse_frontmatter()` `yaml.YAMLError` and non-mapping headers into `conflicts` (untouched, listed, exit 1).
3. **Named spacing capture group (Major 3):** Captured `(?P<colon>[ \t]*:[ \t]*)` in the `re.MULTILINE` migration regex so original spacing around `:` is preserved byte-for-byte.
4. **CLI flag dispatch (Major 4):** Placed `--extract`, `--validate`, `--scaffold`, and `--migrate-type` in an `argparse` mutually exclusive group and rejected `--dry-run` without `--migrate-type` via `parser.error()`.
5. **In-place rewrite durability (Major 5):** Guarded symlinks as conflicts, switched temp files to dot-prefixed siblings (`f".{md_file.name}.{os.getpid()}.tmp"`), preserved file mode (`os.chmod`), added `fsync()` before `os.replace()`, and ensured exception-path cleanup.
6. **Obsidian Sync conflict copies in index (Major 6):** Documented the extra `.agents/context/references.json` entry outcome and operator cleanup step in `Risks & Mitigations`, while keeping global conflict-copy scan exclusion out of scope.
7. **Termination enforcement point & local/self-hosted CI hazard (Major 7):** Clarified that enforcement is local-workstation `oude doctor` (and warned about exit 1 on local hooks / self-hosted runners with `_gm-materials/` mounted), while declining a public vault-CI gate because `_gm-materials/` is gitignored and skipped on public CI runners.
8. **`templates/` clause (Major 8):** Recorded in `Non-Goals` that `grep -rn entity_type templates/` is empty and no template migration is needed.
9. **Comprehension Majors (9–11):** Defined and exemplified YAML front matter, added full reproducible survey commands, and defined GM, ADR, CI, CRLF, engine, sourcebook, skill, Obsidian Sync / conflict copy / Properties view, `catalog.json` vs `references.json`, and `.agents/context/tier1_sources.yml`.
10. **Nits (12–15):** Extracted shared `FRONTMATTER_BLOCK_RE`, aligned headings/footer with Design 006 (`## Risks & Mitigations`, `### Additional Resources`, `### Target Files to Create/Modify`, EGM provenance footer), switched unimplemented behaviour to proposed/future tense, corrected the line citation (`scripts/generate_digests.py:1070-1096`), extended the evidence grep to include `scripts/`, fixed doctor wording, pinned empty-value and case-variant behaviour, confirmed `both_agree` increments `migrated`, and specified `re.MULTILINE`.
