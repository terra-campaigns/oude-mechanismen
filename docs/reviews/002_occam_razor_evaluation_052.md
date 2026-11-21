# Occam's Razor Evaluation — Issue #52

Zero-context sweep of the engine repo after both downstream vaults (hostile, charged) were confirmed onboarded (pilot results on #21). Method: four read-only scout passes (Python engine, RubyGem, skills/templates, docs/tests) plus manual verification of every scout claim against the working tree — several scout claims were disproved and are marked as such below.

## Evidence base

- hostile vault (pin v0.7.1): `oude doctor` clean apart from auto-fixable Dependabot-ignore and version-mismatch warnings; `bundle exec jekyll build` OK (71 Tier 1 entries, 54 references); audit noise fixed in #98.
- charged vault (pin v0.7.3): `oude doctor` fully clean; build OK (114 Tier 1 entries).
- Engine repo: ~8.4k LOC across `scripts/` (10), `src/oude_mechanismen/cli.py`, `lib/`, `jekyll/`.

## Cut list (prioritised)

1. **`sync.sh`** (repo root) — formally deprecated, `MANAGED_FILES` empty; `oude doctor --fix` already removes downstream copies. No live consumer in-repo. CUT.
2. **`bin/init_vault.sh`** — legacy runner superseded by `oude init` (ADR 002); kept only for old vaults, which `oude doctor` remediates. CUT.
3. **Stale version stamps in `jekyll/_includes/*.html`** (`v0.7.3` headers while `VERSION` on develop is `0.7.2` and `main` is `0.8.0`) — cosmetic drift; either drop the stamps or regenerate at release. LOW priority.

## Keep list (scout "cut" claims disproved)

- **`scripts/link_graph.py`** — imported and used by `scripts/scribe_session.py:29,293,669-670` and tested by `tests/test_link_graph.py`. KEEP.
- **`scripts/benchmark_models.py`** — wired as `oude benchmark` (`cli.py:73`). KEEP.
- **`skills/crosslink-tiers/`** — referenced from root `AGENTS.md` and `weave-threads/SKILL.md`. KEEP.
- **`jekyll/all-content.md`, `jekyll/_plugins/llm_content.rb`** — scout claimed present; already removed (#25/#35), with wheel/jekyll e2e tests guarding absence. Nothing to do.
- All 12 skills, all `PASS_THROUGH_SCRIPTS`, all gem includes/plugins — every one has a live consumer. KEEP.
- `docs/designs/`, `docs/adr/` — historical record, referenced from CHANGELOG and AGENTS.md. KEEP.

## Doc drift

- `docs/MIGRATION_GUIDE.md` / `docs/DYNAMIC_GEM.md` are current but not linked from `README.md`/`AGENTS.md.template` — add links (docs-only change). LOW priority.

## Verdict

No architectural refactor is warranted: the ADR 001/002 decoupling runs clean on both real vaults with zero code changes. The razor finds two deprecated root scripts and cosmetic version stamps — nothing else. Behaviour changes from this evaluation: none; vault-side validation already green on both consumers.
