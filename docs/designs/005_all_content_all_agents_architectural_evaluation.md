# Architectural Evaluation 005 — `all-content` Retirement & `all-agents` Surface

* **Author:** `efsalvarenga`
* **Status:** Accepted (2026-11-20; removal implemented via #25/#35 in PR #72)
* **Date:** 2026-11-20
* **Addresses:** GitHub Issue #32 (reconciles #16, #25, #34, #35, PR #31, and the retired `TASKS.md`)

---

## 1. Executive Summary

This evaluation finalises the role of the legacy `all-content` endpoint and
the proposed `all-agents` surface in the modern engine:

1. **Monolithic `/all-content.html` is retired.** Both `jekyll/all-content.md`
   and `jekyll/_plugins/llm_content.rb` (the `raw_markdown` Liquid filter and,
   later, `Jekyll::LlmContentGenerator`) are removed (PR #72, closing #25 and
   #35). Progressive retrieval — `catalog.json` (Tier 1), `references.json`
   (Tier 3), and the `lookup-context` skill with bounded line-range reads — is
   the single context-loading mechanism.
2. **No `all-agents` page or manifest is required.** Agent-facing metadata
   already surfaces through `.agents/AGENTS.md` (campaign specification),
   the bundled `skills/` catalogue installed via `oude install-skills`, and
   the `oude` CLI itself. If a machine-readable agent registry is ever needed,
   it should be added as a CLI/JSON surface (e.g. `oude agents --json`), not
   as a wiki page: Jekyll pages are Tier 1 campaign canon, not engine plumbing.
3. **Issue #34 is re-scoped to the post-removal reality.** Its original
   `LlmContentGenerator` rendering checks were superseded by PR #72. The e2e
   coverage now proves the post-removal invariants instead and runs in CI:
   `tests/test_e2e_jekyll.py` (real `bundle exec jekyll build` of a fixture
   vault) and `tests/test_e2e_wheel.py` (clean-venv wheel smoke), both executed
   by the `validate` job in `.github/workflows/ci.yml`.

## 2. Background & Decision History

- **Early engine:** `jekyll/all-content.md` plus `jekyll/_plugins/llm_content.rb`
  rendered `/all-content.html` as a monolithic plaintext dump of the whole wiki
  for single-shot LLM context loading. Downstream vaults were scaffolded with a
  physical root copy of `all-content.md`.
- **#16 / PR #31 (merged):** a memory-based `Jekyll::LlmContentGenerator`
  synthesised `/all-content.html` inside the gem, yielding to vault-supplied
  overrides; `pyproject.toml` force-included the assets in the wheel.
- **Reversal — #25 / #35 (closed), PR #72 (merged):** the dump was redundant
  with progressive retrieval and added build overhead plus per-vault
  scaffolding. Both artefacts were deleted engine-side, all packaging,
  scaffolding, and documentation references were removed, and `oude doctor
  --fix` was made to prune residual root `all-content.md` and
  `_plugins/llm_content.rb` in downstream vaults.
- **`TASKS.md`:** retired in PR #31; the backlog lives in GitHub issues
  (#13–#35), so no roadmap file requires reconciliation.

## 3. Evaluation: Progressive Retrieval vs Monolithic LLM Dump

| Dimension | Monolithic `/all-content.html` | Progressive retrieval (`catalog.json` + `lookup-context`) |
|---|---|---|
| Token cost per session | Entire wiki loaded every time (multi-MB dumps) | Index lookup, then bounded line-range reads of only the target notes |
| Staleness | Frozen at last site build | `catalog.json` regenerated on every `jekyll build`; entries carry `sha` and `summary` |
| Privacy (Tier 0 air-gap) | Risk of sweeping private material into a published page | Tier 0 audio/transcripts never enter the repo; only de-personalised Tier 2 notes exist to be indexed |
| Build overhead | Extra page + filter per vault build | `data_extractor.rb` generator already runs; catalogue is a by-product |
| Distribution clutter | Root `all-content.md` scaffolded into every vault | None; gem serves plugins and includes in memory (ADR 001) |
| Debuggability | One opaque blob | Structured entries (`path`, `type`, `links_in`/`links_out`, `tier`) queryable by `lint-wiki`/`audit` |

Progressive retrieval wins on every dimension that matters for an agentic
workflow; the monolith's only advantage (single-shot loading) is exactly the
anti-pattern the low-token protocol exists to avoid.

## 4. `all-agents` Requirements Analysis

A hypothetical `all-agents` page would aggregate `.agents/AGENTS.md`, available
skills, tools, and personas for external agents or human GMs. Requirements
check:

- **Campaign specification** — already at `.agents/AGENTS.md` in every vault
  (scaffolded by `oude init`), read directly by agents at session start.
- **Skill catalogue** — bundled in `skills/` and installed globally by
  `oude install-skills`; discoverable via the filesystem and `lookup-context`,
  not via a rendered page.
- **CLI/tool surface** — `oude --help` and subcommand `--help` output.
- **Machine-readable registry** — not currently required by any consumer.

**Verdict:** no `all-agents` endpoint is needed now. Wiki pages are for Tier 1
campaign canon; agent plumbing belongs to the repo/CLI surface. If an external
consumer later requires a machine-readable manifest, add `oude agents --json`
rather than a Jekyll page.

## 5. Final Removal Scope (`all-content` & `llm_content.rb`)

Explicitly covering both artefacts named in #32:

- `jekyll/all-content.md` — **deleted** from the engine.
- `jekyll/_plugins/llm_content.rb` — **deleted** from the engine (both the
  `raw_markdown` filter and the PR #31 `Jekyll::LlmContentGenerator`).
- `lib/oude_mechanismen.rb` — `require_relative` of `llm_content` removed; the
  gem loads only `data_extractor.rb` and injects `jekyll/_includes` in memory.
- `pyproject.toml` — `force-include` of `jekyll/all-content.md` removed; the
  wheel ships `jekyll/_includes`, `scripts/`, `skills/`, `templates/`, `VERSION`.
- `sync.sh` (`MANAGED_FILES`), `bin/init_vault.sh` (`MAPPINGS`),
  `src/oude_mechanismen/cli.py` (`TEMPLATE_MAPPINGS`) — scaffolding entries
  removed; `oude init` no longer creates a root `all-content.md`.
- `AGENTS.md`, `skills/lint-wiki/SKILL.md`, `docs/DYNAMIC_GEM.md`,
  `docs/MIGRATION_GUIDE.md`, Design 002 — references reconciled.
- `oude doctor` / `--fix` — flags and removes residual root `all-content.md`
  and `_plugins/llm_content.rb` in downstream vaults (unit-tested in
  `tests/test_cli.py`).
- `tests/test_cli.py`, `tests/test_init_vault.py` — assert the artefacts are
  neither scaffolded nor bundled.

## 6. Cross-Issue Reconciliation

| Reference | Status | Resolution |
|---|---|---|
| #16 (dynamic `/all-content.html`) | Closed | Superseded by #25; the PR #31 generator was itself removed in PR #72 |
| PR #31 | Merged | `oude doctor` remediations retained; `llm_content.rb` generator later removed by PR #72; `TASKS.md` retired |
| #25 (remove `all-content.md` + `llm_content.rb`) | Closed | Implemented in PR #72 |
| #35 (residual reference cleanup) | Closed | Implemented in PR #72 |
| #34 (e2e rendering + wheel assets) | Open | Re-scoped post-removal: `tests/test_e2e_jekyll.py` + `tests/test_e2e_wheel.py` in CI `validate`; Design 002 §6 updated |
| #32 (this evaluation) | Open | This document; recommend closing on merge |
| `TASKS.md` | Retired | Removed in PR #31; backlog tracked as GitHub issues |

## 7. Verification & Test Coverage

- **Unit suite:** `python3 -m unittest discover -s tests` — 219 tests OK
  (local run, 2026-11-20), including the 6 new e2e tests.
- **`tests/test_e2e_jekyll.py`** (issue #34): builds a fixture vault in a temp
  dir with a path Gemfile pointing at the checkout, runs a real
  `bundle exec jekyll build`, and asserts `_site/` pages render,
  `.agents/context/catalog.json` is emitted with the fixture's Tier 1 entry,
  `_site/all-content.html` is NOT generated, and a vault-supplied root
  `all-content.md` still builds as an ordinary page. Skips when
  `ruby`/`bundle` are absent.
- **`tests/test_e2e_wheel.py`** (issue #34): `uv build`, install the wheel
  into a clean venv created outside the checkout, and assert
  `resolve_asset_dir` resolves `jekyll/_includes`, `scripts/`, `skills/`,
  `templates/`, `VERSION` inside `site-packages`, that `jekyll/all-content.md`
  and `jekyll/_plugins/llm_content.rb` are absent from the wheel, and that the
  installed `oude --version` runs from outside the checkout. Skips when `uv`
  is absent.
- **CI:** the `validate` job in `.github/workflows/ci.yml` now installs `uv`
  and Ruby before `unittest discover`, so both e2e suites execute on every
  push/PR to `main` and `develop` (the required `validate` check).
- **Docs:** Design 002 §5.4 marks the dynamic generator superseded and §6 now
  states the post-removal verification contract.
