# Oude Mechanismen — Agentic Architecture & Implementation Manual

This repository contains the shared procedural engine, agent skills library, and Jekyll static site tooling for tabletop RPG campaign vaults.

---

## 1. Core Architectural Contract

`oude-mechanismen` strictly enforces the separation of **procedural execution (the engine)** from **creative lore and setting rules (the campaign vault)**:

1. **Engine Agnosticism**: Never inject setting-specific lore, faction names, or custom house rules into `oude-mechanismen`. All procedural skills, Jekyll templates, and Python scripts must remain generic and parameterised.
2. **Campaign Parameterisation**: Downstream campaign vaults parameterise the engine via `.agents/AGENTS.md` (specifically `## Campaign Specification`), `.agents/context/tier1_sources.yml`, and `.agents/context/aesthetics.yml`.
3. **Storage Separation**: Markdown lore notes remain in the Git repository. Raw session audio, transcripts, and GM archival notes reside in Google Drive (`<drive_dir>/_sessions/`).

---

## 2. Repository Topology

```text
oude-mechanismen/
├── VERSION                     # Engine semver (e.g. 0.1.0)
├── CHANGELOG.md                # Human & agent changelog following Keep a Changelog
├── LICENSE                     # MIT open-source licence
├── requirements.txt            # Python dependencies (pyyaml, pypdf, numpy, Pillow)
├── sync.sh                     # Vault synchronisation and bootstrapper script
├── skills/                     # Universal Antigravity / agent skills
│   ├── lookup-context/         # Progressive multi-tier context retrieval
│   ├── lint-wiki/              # Wiki structural linting & dead-link detection
│   ├── review-style/           # Surgical setting voice & tone reviews
│   ├── add-chapter/            # Session log & chapter scaffolding
│   ├── add-character/          # Character dossier creation
│   ├── prep-session/           # 8-step structured GM session prep
│   ├── weave-threads/          # Narrative thread & faction anomaly analysis
│   ├── scribe-session/         # Metal GPU speech-to-text & chapter scribing
│   └── illustrate-entry/       # Archival art curation, filter studio & styling
│       ├── resources/          # Interactive Generative UI filter studio template
│       └── scripts/            # Core art_filter.py graphic novel engine
├── scripts/                    # Shared campaign tooling
│   ├── generate_digests.py     # Tier 3 PDF digest generator & references.json compiler
│   ├── audit_coverage.py       # Structural audit of campaign coverage and topology
│   └── transcribe_session.py   # Metal GPU ASR & dynamic glossary extraction
├── jekyll/                     # Source-of-truth Jekyll engine
│   ├── _plugins/               # In-memory catalogue & LLM dump generators
│   ├── _includes/              # Reusable galleries, headers, and badge fallbacks
│   └── all-content.md          # Headless LLM context endpoint
├── githooks/                   # Pre-commit hook to recompile catalog.json
└── templates/                  # Scaffolding templates for downstream campaign vaults
    ├── AGENTS.md.template      # Starter instructions for downstream vault agents
    ├── tier1_sources.yml.template
    ├── decisions.md.template   # Starter Tier 2 conversation canon file
    ├── aesthetics.yml.template # Starter art filter presets
    ├── skills.json.template    # Skills discovery path configuration
    ├── route_graph.json.template
    ├── badges/                 # Neutral geometric fallback PNG badges
    ├── bin/setup.template      # Idempotent campaign environment bootstrapper
    ├── runners/                # Lightweight wrapper scripts delegating to engine
    └── jekyll/                 # Vanilla Just the Docs starter config & Gemfile
```

---

## 3. Autonomous Onboarding Protocol

When a user asks an agent: *"Help me set up my new (or existing) campaign vault with oude-mechanismen"*, the agent should execute the following 5-step playbook:

### Step 1: Bootstrap Vault Scaffolding

From the `oude-mechanismen` directory, run the initialisation command:

```bash
./sync.sh --init "/path/to/target/campaign-vault"
```

This creates standard directories (`campaigns/`, `directory/`, `systems/`, `imgs/gallery/`, `imgs/badges/`, `.agents/context/`), copies missing starter templates from `templates/`, copies neutral fallback badges, stamps `.agents/.engine-version`, and executes `./bin/setup`.

### Step 2: Interview the GM for Campaign Parameters

Ask the GM 5 focused questions to populate their campaign specification:

1. **Setting Genre & Tone**: (e.g. "Grimdark industrial sci-fi", "Psychedelic science fantasy", "Gothic horror").
2. **Cadence & Sentence Style**: (e.g. "One sentence per line, terse corporate register, sensory grime").
3. **Reference Sourcebooks**: Absolute path to their Google Drive rulebooks/PDFs folder (for `tier1_sources.yml`).
4. **Chapter Conventions**: Subfolder path (e.g. `campaigns/my-arc/`), naming convention (e.g. `ep_{num:03d}.md` or `{num:03d}.md`), and timestamp format (`YYYY-MM-DD` or `YYYY-MM-DD HH:MM`).
5. **Visual Palette Preferences**: Colour mood for graphic-novel artwork (e.g. amber CRT phosphor, desert turquoise, or monochrome ink).

### Step 3: Populate Campaign Configuration

Write the user's answers into the target vault:
- `.agents/AGENTS.md`: Update `## Campaign Specification` (Style & Tone, Reference Material, Calibration Examples, Structural Defaults).
- `.agents/context/tier1_sources.yml`: Set `drive_dir: "<path_to_rulebooks_folder>"`.
- `.agents/context/aesthetics.yml`: Adjust colour stops and active presets.
- `_config.yml`: Update site `title` and `description`.

### Step 4: Verify Environment & Compilation

Run the vault verification from the target repository root:

```bash
cd "/path/to/target/campaign-vault"
./bin/setup
bundle exec jekyll build
```

Verify that `.agents/context/catalog.json` compiled with zero errors.

---

## 4. Canon & Context Architecture

The engine operates on a strict **Three-Tier Canon Hierarchy**:

- **Tier 1 (Canonical Published Notes)**: Published markdown files indexed by `_plugins/data_extractor.rb` into `.agents/context/catalog.json`. This is hard canon.
- **Tier 2 (Active Table Decisions)**: Confirmed rulings and conventions recorded in `.agents/context/decisions.md`. Outranked by published Tier 1 notes; outranks external reference PDFs.
- **Tier 3 (External Reference Material & Digests)**: Sourcebook PDFs and structured digests in `_digests/*.md`, indexed by `scripts/generate_digests.py` into `.agents/context/references.json`. Influence and inspiration, not automatic canon.

### Low-Token Progressive Retrieval Protocol

When searching for lore, locations, NPCs, or mechanics:
1. Never read all markdown notes or large reference PDFs in bulk.
2. Use the `lookup-context` skill or consult `.agents/context/catalog.json` first to identify target entities and line ranges.
3. Open only the identified note using targeted line-range reads.
4. For external rules or lore, consult `_digests/*.md` via `.agents/context/references.json` before opening raw PDFs.

---

## 5. Synchronisation Engine Rules (`sync.sh`)

- **Managed Files**: Engine updates to plugins, includes, git hooks, runners, and setup scripts are tracked in `sync.sh`'s `MANAGED_FILES` array.
- **Drift Safety**: `sync.sh` never overwrites locally modified (dirty) files in a campaign vault unless `--force` is explicitly passed.
- **Version Stamping**: Every sync stamps the engine version and git commit into `.agents/.engine-version` in the target vault.

---

## 6. Authoring New Skills

When adding a new procedural skill to `skills/<skill-name>/`:

1. **Provide `SKILL.md`**: Must begin with YAML front matter containing `name`, `description`, and `argument-hint`.
2. **Enforce British English**: All instructions, templates, prompts, and code comments must strictly use British English.
3. **Follow Markdown Spacing Rule**: Always leave an empty blank line immediately following any Markdown heading (`#`, `##`, `###`).
4. **Delegate Setting Flavor**: Never hardcode setting tropes. Query `AGENTS.md` for tone, calibration examples, and vocabulary.
