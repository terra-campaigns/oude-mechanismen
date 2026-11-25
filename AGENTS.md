# Oude Mechanismen — Agentic Architecture & Implementation Manual

This repository contains the shared procedural engine, agent skills library, and Jekyll static site tooling for tabletop RPG campaign vaults.

---

## 1. Core Architectural Contract

`oude-mechanismen` strictly enforces the separation of **procedural execution (the engine)** from **creative lore and setting rules (the campaign vault)**:

1. **Engine Agnosticism**: Never inject setting-specific lore, faction names, or custom house rules into `oude-mechanismen`. All procedural skills, Jekyll templates, and Python scripts must remain generic and parameterised.
2. **Campaign Parameterisation**: Downstream campaign vaults parameterise the engine via `.agents/AGENTS.md` (specifically `## Campaign Specification`), `.agents/context/tier1_sources.yml`, and `.agents/context/aesthetics.yml`.
3. **Storage Separation & Privacy Air-Gap**:
   - **Tier 0 (Local Disk Air-Gap)**: Raw session audio recordings and verbatim speech transcripts reside strictly on local disk at `~/Private/rpg-sessions/<campaign>/`, completely excluded from Git, Obsidian Sync, and all networked storage for player privacy.
   - **Tier 1 Canon (Campaign Repository)**: Finalised, published markdown wiki notes (`campaigns/`, `directory/`, `systems/`) reside exclusively in the Git repository.
   - **Tier 2 Canon (`_gm-materials/`):** De-personalised tactical facts (`<slug>_tactical_facts.md`), sensory textures (`<slug>_sensory_textures.md`), synthesised archival GM session notes (`<slug>_session_notes.md`), and acoustic glossaries (`<slug>_glossary.md`) in `_gm-materials/session-summaries/`; structured GM rulings and faction-turn records in `_gm-materials/rulings/`, compiled by `oude tier2` into the derived `_gm-materials/.cache/tier2.json`. The gitignored `.agents/context/rolling_glossary.md` also sits at Tier 2 until promoted.
  - **Tier 3 Canon (`_gm-materials/digests/` & `_gm-materials/session-preps/`):** Distilled reference digests and unplayed session prep (`<slug>_prep.md`). Raw commercial sourcebook PDFs sit outside Tier 3 on local disk in [ADR 003](docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md) **Pillar 3** — the central static archive: local OneDrive on `ryu` (or a permanent local archive on `artemis`), outside both Git and Obsidian Sync.

---

## 2. Repository Topology

```text
oude-mechanismen/
├── VERSION                     # Single-source engine semver (e.g. 0.6.1)
├── CHANGELOG.md                # Human & agent changelog following Keep a Changelog
├── LICENSE                     # MIT open-source licence
├── pyproject.toml              # Python package & `oude` CLI distribution (ADR 002)
├── oude-mechanismen.gemspec    # Jekyll RubyGem specification (ADR 001)
├── requirements.txt            # Python dependency pin for CI and legacy setups
├── src/oude_mechanismen/       # Unified `oude` CLI dispatcher & package helpers
├── lib/                        # RubyGem entrypoint (`oude_mechanismen.rb`, `version.rb`)
├── docs/                       # ADRs, design specs, MIGRATION_GUIDE.md, DYNAMIC_GEM.md
├── skills/                     # Universal Antigravity / agent skills
│   ├── lookup-context/         # Progressive multi-tier context retrieval
│   ├── lint-wiki/              # Wiki structural linting & dead-link detection
│   ├── review-style/           # Surgical setting voice & tone reviews
│   ├── add-chapter/            # Session log & chapter scaffolding
│   ├── add-character/          # Character dossier creation
│   ├── prep-session/           # 8-step structured GM session prep
│   ├── weave-threads/          # Narrative thread & faction anomaly analysis
│   ├── scribe-session/         # Decomposed air-gapped speech-to-text & chapter scribing
│   ├── illustrate-entry/       # Archival art curation & graphic-novel styling
│   │   └── scripts/            # Core art_filter.py graphic novel engine
│   ├── crosslink-tiers/        # Tier 1 ↔ Tier 3 cross-linking inside {% comment %} blocks
│   └── digest-book/            # Sourcebook PDF → validated semantic digest wiki (Design 004 Stage C)
├── scripts/                    # Shared campaign tooling (invoked via `oude <cmd>`)
│   ├── generate_digests.py     # Tier 3 PDF digest extractor/validator & references.json compiler
│   ├── audit_coverage.py       # Structural audit of campaign coverage and topology
│   ├── transcribe_session.py   # Metal GPU ASR & dynamic glossary extraction (Tier 0 air-gap)
│   ├── scribe_session.py       # Local Ollama two-pass de-personalised extractor (Pass 2A & 2B)
│   ├── benchmark_models.py     # Empirical local model extraction benchmark harness
│   ├── lint_wiki.py            # Deterministic structural wiki linter (Gate 3: dead links, orphans, stubs, catalogue, rulings)
│   └── tier2.py                # Tier 2 rulings compiler & validator (`oude tier2` → _gm-materials/.cache/tier2.json)
├── tests/                      # Automated unit & integration test suite (`test_*.py`)
├── jekyll/                     # Source-of-truth Jekyll engine
│   ├── _plugins/               # In-memory Tier 1 catalogue & backlink generator
│   └── _includes/              # Reusable galleries, headers, and badge fallbacks
└── templates/                  # Scaffolding templates for downstream campaign vaults
    ├── AGENTS.md.template      # Starter instructions for downstream vault agents
    ├── tier1_sources.yml.template
    ├── aesthetics.yml.template # Starter art filter presets
    ├── route_graph.json.template
    ├── badges/                 # Neutral geometric fallback PNG badges
    ├── github/                 # Vault .github/dependabot.yml (oude-mechanismen ignore guard)
    └── jekyll/                 # Vanilla Just the Docs starter config & Gemfile
```

---

## 3. Autonomous Onboarding Protocol

When a user asks an agent: *"Help me set up my new (or existing) campaign vault with oude-mechanismen"*, the agent should execute the following 5-step playbook:

### Step 1: Bootstrap Vault Scaffolding

From the `oude-mechanismen` directory, run the initialisation command:

```bash
oude init "/path/to/target/campaign-vault"
```

This creates standard directories (`campaigns/`, `directory/`, `systems/`, `imgs/gallery/`, `imgs/badges/`, `.agents/context/`, `_gm-materials/`), copies missing starter templates from `templates/`, copies neutral fallback badges, and installs global skills.

### Step 2: Interview the GM for Campaign Parameters

Ask the GM 5 focused questions to populate their campaign specification:

1. **Setting Genre & Tone**: (e.g. "Grimdark industrial sci-fi", "Psychedelic science fantasy", "Gothic horror").
2. **Cadence & Sentence Style**: (e.g. "One sentence per line, terse corporate register, sensory grime").
3. **Reference Sourcebooks**: Path to their rulebooks/PDFs and `_gm-materials/` root (defaults to `.` in `tier1_sources.yml`).
4. **Chapter Conventions**: Subfolder path (e.g. `campaigns/my-arc/`), naming convention (e.g. `ep_{num:03d}.md` or `{num:03d}.md`), and timestamp format (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`).
5. **Visual Palette Preferences**: Colour mood for graphic-novel artwork (e.g. amber CRT phosphor, desert turquoise, or monochrome ink).

### Step 3: Populate Campaign Configuration

Write the user's answers into the target vault:
- `.agents/AGENTS.md`: Update `## Campaign Specification` (Style & Tone, Reference Material, Calibration Examples, Structural Defaults).
- `.agents/context/tier1_sources.yml`: Set `drive_dir: .` (or custom path if using an external rulebooks directory).
- `.agents/context/aesthetics.yml`: Adjust colour stops and active presets.
- `_config.yml`: Update site `title` and `description`.

### Step 4: Verify Environment & Compilation

Run the vault verification from the target repository root:

```bash
cd "/path/to/target/campaign-vault"
bundle install
bundle exec jekyll build
oude doctor
```

Verify that `.agents/context/catalog.json` compiled with zero errors.

- **Guides**: [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) (Google Drive → `_gm-materials/` cutover) and [DYNAMIC_GEM.md](docs/DYNAMIC_GEM.md) (RubyGem operator guide).

---

## 4. Canon & Context Architecture

The engine operates on a strict **Four-Tier Canon Hierarchy (Tiers 0–3)**:

- **Tier 0 (Raw Table Evidence)**: Raw session recordings and verbatim transcripts kept strictly on local disk at `~/Private/rpg-sessions/<campaign>/` (Pillar 0); never committed to Git, never synced via Obsidian Sync, never published. Exposed only at the table.
- **Tier 1 (Canonical Published Notes)**: Published markdown files indexed on build by the `oude-mechanismen` RubyGem (`jekyll/_plugins/data_extractor.rb`) into the gitignored local cache `.agents/context/catalog.json`. This is hard canon. Notes may carry an optional explicit `id:` front-matter field (indexed as `"id"` in `catalog.json`, `null` when absent — never derived from the filename); grammar and uniqueness are enforced by `check_duplicate_ids()` in `scripts/lint_wiki.py`, and Tier 2 rulings join on it at compile time.
- **Tier 2 (Behind-the-Screen Working Canon & Unverified Records)**: Structured GM rulings and faction-turn records in `_gm-materials/rulings/` (validated and compiled by `oude tier2` / `scripts/tier2.py` into the derived `_gm-materials/.cache/tier2.json`), synthesised archival GM session notes (`_gm-materials/session-summaries/`), and the gitignored `.agents/context/rolling_glossary.md` (which retains `tier: 2` in `catalog.json`). Outranked by published Tier 1 notes; outranks Tier 3.
- **Tier 3 (Defined Campaign Influences & Unplayed Prep)**: Structured digests in `_gm-materials/digests/`, indexed by `scripts/generate_digests.py` into `.agents/context/references.json`, and unplayed session prep in `_gm-materials/session-preps/`. Raw commercial sourcebook PDFs sit outside Tier 3 on local disk ([ADR 003 Pillar 3](docs/adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md)). Influence and inspiration, not automatic canon.

- **Route graph (optional)**: `.agents/context/route_graph.json` (scaffolded from `templates/route_graph.json.template`) encodes station topology — stations, aliases, connections, `station_lore` — and is consumed only by `scripts/audit_coverage.py` for the *Geographic Proximity & Destination Gaps* section of `oude audit`. It is not canon and not part of progressive retrieval; when absent, the audit simply skips that section (audit findings on issue #29).

### Low-Token Progressive Retrieval Protocol

When searching for lore, locations, NPCs, or mechanics:
1. Never read all markdown notes or large reference PDFs in bulk.
2. Use the `lookup-context` skill or consult `.agents/context/catalog.json` first to identify target entities and line ranges.
3. Open only the identified note using targeted line-range reads.
4. For external rules or lore, consult `_gm-materials/digests/` via `.agents/context/references.json` before opening raw PDFs.

---

## 5. Legacy Synchronisation & Version Stamping

- **Retired Template Sync (`sync.sh`)**: the legacy `sync.sh` and `bin/init_vault.sh` scripts have been removed from this repo (see `docs/reviews/002_occam_razor_evaluation_052.md`). Jekyll plugins and includes are served in-memory by the `oude-mechanismen` RubyGem (ADR 001), Python tooling and skills are distributed globally via `oude` / `uv` (ADR 002), and `oude doctor --fix` removes legacy `.agents/scripts/` runners, shadowing `_plugins/`, `_includes/`, and deprecated `all-content.md` downstream.
- **Version Stamping**: Dynamic static site generation via `oude-mechanismen` records the authoritative active engine version directly into `.agents/context/catalog.json`. The legacy `.agents/.engine-version` file is formally deprecated and audited by `oude doctor`.

---

## 6. Authoring New Skills

When adding a new procedural skill to `skills/<skill-name>/`:

1. **Provide `SKILL.md`**: Must begin with YAML front matter containing `name`, `description`, and `argument-hint`.
2. **Enforce British English**: All instructions, templates, prompts, and code comments must strictly use British English.
3. **Follow Markdown Spacing Rule**: Always leave an empty blank line immediately following any Markdown heading (`#`, `##`, `###`).
4. **Delegate Setting Flavour**: Never hardcode setting tropes. Query `AGENTS.md` for tone, calibration examples, and vocabulary.
5. **Mandatory Pre-Publishing Audit Gate**: Any procedural skill creating or finalising session chronicles (`add-chapter`, `scribe-session`) must integrate the 3-Gate Pre-Publishing Protocol (Gate 1: `scripts/lint_chapter.py`; Gate 2: `review-style`; Gate 3: `scripts/lint_wiki.py` via `oude lint-wiki`, surfaced by the `lint-wiki` skill). To prevent unnecessary LLM token consumption, full 3-Gate execution is strictly reserved for pre-PR drafting and pre-final-review checkpoints, rather than routine intermediate commits. Deterministic Gates 1 and 3 (`scripts/lint_chapter.py`, `scripts/lint_wiki.py`) execute locally with zero token burn.

---

## 7. Published-Canon Delivery Policy (Package C, #91)

- **Notebook-Centric Prep (#20):** Session prep (`skills/prep-session`) is written for the GM's physical paper notebook used during planning and play — terse bullet cues only; boxed read-aloud text (`> Table Read-Aloud`) is never generated. No Python-notebook input restriction exists; scribe input remains audio/transcript.
- **Narrative-Anchored Episode Links (#18):** Episode cross-references in published chapters must be narrative-anchored markdown links (e.g. `[exploding banana seller](ep_008.md)`), never mechanical parentheticals like `(See Episode 3)`. Enforced at the episode-authoring gate: `lint_chapter.py` emits a `mechanical-parenthetical` WARN (Gate 1 of the pre-publishing protocol). Narrative markdown links are indexed in `catalog.json` via `links_out`/`links_in` as before — no render-time rewriting.

## 8. Git Hygiene & Branch Lifecycle

### Two-Branch Flow: `develop` (Integration) vs `main` (Release-Only)

1. **`develop` is the integration branch**: Cut all feature and fix branches from `develop`, and target every day-to-day feature/fix Pull Request at `develop` (the default PR base). Unreleased work must never land directly on `main`.
2. **`main` is release-only**: `main` receives ONLY release-cut Pull Requests (from `develop`) carrying the `VERSION` bump and the dated `CHANGELOG.md` section; merge via PR, then tag the merged `main` commit as `vX.Y.Z` and publish the release.
3. **Transition note**: the first PRs landed directly on `main` ahead of a release and shipped together in the next tagged version. From the two-branch flow onward, all unreleased work goes to `develop`; `main` stays exactly at tagged releases. Pull Requests already open against `main` when this flow was introduced may still merge to `main`; otherwise retarget them to `develop`.

### Branch Protection (GitHub Rulesets)

The two-branch flow is enforced by repository [rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets), whose definitions are committed in `.github/rulesets/` for audit and reproduction:

- `main-release-only` (active, targets `refs/heads/main`): require pull request, non-fast-forward, required status check `validate`.
- `protect-develop` (active, targets `refs/heads/develop`): same rules.

On pushes, the `rulesets` CI job fails if any live repository ruleset is not `enforcement: active`, and verifies each committed `.github/rulesets/*.json` matches its live ruleset (target refs, rule types, required check `validate`). To change a ruleset, update the JSON in `.github/rulesets/` and apply it via the GitHub API or Settings UI, then verify with `gh api repos/terra-campaigns/oude-mechanismen/rulesets`.

### Standing Hygiene Rules

1. **Branch Deletion Invariant**: Feature branches must be deleted immediately after their corresponding Pull Request is merged or closed. Never retain merged remote or local feature branches.
2. **Automated Remote Deletion**: Campaign vaults with GitHub remotes must enable automatic branch deletion on merge (`gh repo edit --delete-branch-on-merge`).
3. **Post-Merge Local Cleanup**: Once a Pull Request is merged, check out its base branch (`develop` for feature/fix PRs, `main` for release-cut PRs), pull the latest remote changes (`git checkout <base> && git pull`), delete the local branch (`git branch -d <branch>`), and prune remote tracking references (`git fetch --prune`).
4. **Pull-Request-Only Policy**: Never push commits directly to `main` or `develop`, and never bypass branch protection rules—including for release bumps (`VERSION`, `CHANGELOG.md`). Always push to a feature branch, open a Pull Request against the correct base (`develop` for features and fixes, `main` for release cuts only), merge it, and only then tag and publish a release.
