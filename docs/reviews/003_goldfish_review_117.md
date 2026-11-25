# Goldfish Review (Step 2) — Issue #117

* **Author:** efsalvarenga
* **Status:** Complete — synthesis of 7 lens reports
* **Date:** 2026-11-24
* **Addresses:** [#117](https://github.com/terra-campaigns/oude-mechanismen/issues/117)

---

Synthesis of the seven-lens Goldfish review of `concepts_brief.md` (Tier 2 Canon Structure, Supersession Tracking, Faction-Turn Records). Lenses: `egm-design`, `egm-codebase-details`, `egm-zoom-out`, `egm-comprehension`, `egm-implementation-readiness`, `egm-structural`, `egm-inventive-catalyst`. All findings below are deduplicated across lenses; full per-lens transcripts remain available to the harness.

## Cross-cutting blockers (settle before implementation)

1. **YAML opinion placement.** Three lenses (structural, zoom-out, design) independently converge: keep actor opinions in YAML front matter (single `yaml.safe_load()` pass, body stays pure narrative), not a fenced body block. **Recommendation: front matter.**
2. **Secrets-bearing index location (design, Major).** `.agents/context/tier2.json` sits in a *tracked* directory; a single-file gitignore entry only guards against `git add .`. Compile the index under the already tree-ignored `_gm-materials/` (e.g. `_gm-materials/.cache/tier2.json`) and still add it to `DERIVED_CACHE_FILES` + `DEFAULT_GITIGNORE` so `oude doctor`'s `git ls-files --error-unmatch` loop catches an already-tracked copy. Note: `references.json` is currently in neither list — the ignore-list itself needs a completeness check.
3. **Supersession schema (structural, design, readiness).** `supersedes: []` (list) vs `superseded_by: null` (scalar) cannot be pairwise "symmetric"; symmetry alone permits cycles. Define an explicit transition graph (active → superseded | retracted | promoted; terminal states immutable), linter checks acyclicity + single active successor + status ⟺ partner-field matrix. Zoom-out adds: store `supersedes` only and derive the inverse at compile time.
4. **`decisions.md` migration (design #2/#3, readiness #5).** Cutover must be atomic in one PR (content + all four skills + `oude init` template); already-pushed public history in `charged`/`hostile` stays exposed (document acceptance, no history rewrite); add a doctor/lint advisory when `decisions.md` and `_gm-materials/rulings/` coexist.

## Recommended decisions on the brief's open questions

| Open question | Lens consensus |
|---|---|
| YAML placement | Front matter (structural, zoom-out, design) |
| CLI surface | No native `oude tier2` subcommand family — one pass-through `scripts/tier2.py` (`PASS_THROUGH_SCRIPTS`) + `check_rulings()` in `lint_wiki.py`; actor queries via `jq`, no query subcommand (zoom-out) |
| `tier2.json` shape | Entries-only `{generated, entries[]}`; groupings derived at read time (zoom-out) — but compile `by_actor` with a recency window and id references instead of duplicated stance text to bound prompt size at 30+ turns (design #6) |
| `_actors.yml` | Not the leanest boundary: shrink to an optional name-only roster for actors without a Tier 1 page (zoom-out); catalyst prefers stable Tier 1 `id`s joined at compile time — bigger change, explicit adopt/reject needed |
| Turn metadata | `trio_tier: Option` is a leaked Rust debug value (structural); typed schema or short summary string; TOME vocab must be declared freeform or copied into this repo (readiness) |

## Inventive catalyst alternative (open question 6)

Cleaner than the brief *as specified* is possible without changing the pillar split: (a) extract actor opinions into per-actor private files so promotion to Tier 1 is a true delete with zero private-data loss; (b) reference entities by stable Tier 1 `id` (requires adding ids in `data_extractor.rb`) instead of path lists + `_actors.yml`, resolving at compile time against `catalog.json`. Cost: Tier 1 id discipline and a compile-time join. Decide explicitly whether to adopt or reject.

## Verification notes

- All "Existing Codebase Surface" claims in the brief verified against the working tree — every named symbol exists at the cited lines; no `tier2`/`rulings` code exists yet (codebase-details).
- Doc drift to fix alongside: `AGENTS.md:15,124` and `skills/scribe-session/SKILL.md:17` still classify `_gm-materials/session-preps/` as Tier 2; the brief's clarified model puts it in Tier 3.
- Comprehension gaps: TOME, faction turn, TRIO/`trio_tier`, spark tags, `vote`/`shifted` semantics, ID grammar, and the `tier2.json` shape are all used before definition — each fixable with one sentence or a sample block.
- Structural: brief header should adopt the repo doc template (`Status:`, `Addresses:` link, `---`); on merge the brief belongs at `docs/designs/006_…` with numbered sections.

## Verdict

The concept is sound and the zero-blast-radius layout is genuinely safe (`_gm-materials/` is already four-layer protected). Six decisions — YAML placement, index location, `tier2.json` schema, supersession rules, CLI surface, `decisions.md` migration — need settling before implementation; most have a clear lens consensus recorded above.
