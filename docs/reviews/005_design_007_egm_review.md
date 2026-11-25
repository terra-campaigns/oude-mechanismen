# EGM Review Summary — Design 007 (Issue #115)

* **Author:** `efsalvarenga`
* **Status:** Complete — Round 1 Findings Resolved
* **Date:** 2026-11-25
* **Addresses:** [#115](https://github.com/terra-campaigns/oude-mechanismen/issues/115)
* **Target Document:** [007_unified_type_key_for_digests.md](../designs/007_unified_type_key_for_digests.md)

---

## Overview

[007_unified_type_key_for_digests.md](../designs/007_unified_type_key_for_digests.md) underwent one uninterrupted five-stage Elephant-Goldfish Model review: Initial Zoom Out and Inventive Catalyst (Stage 5), Comprehension (Stage 6), Design, Structural and Style Critique (Stage 7), Intermediate Zoom Out (Stage 8), and Implementation Readiness and Codebase Details (Stage 9).

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
