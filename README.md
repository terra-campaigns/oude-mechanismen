# Oude Mechanismen (Ancient Machinery)

Shared campaign engine, procedural agent skills, and Jekyll static site tooling for tabletop RPG campaign vaults.

[![Version](https://img.shields.io/github/v/tag/terra-campaigns/oude-mechanismen?label=version&color=blue)](VERSION)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/terra-campaigns/oude-mechanismen/actions/workflows/ci.yml/badge.svg)](https://github.com/terra-campaigns/oude-mechanismen/actions/workflows/ci.yml)

Powering [Charged](https://github.com/terra-campaigns/charged) and [Hostile](https://github.com/terra-campaigns/hostile).

---

## What is Oude Mechanismen?

`oude-mechanismen` turns a plain **Obsidian vault** and **Jekyll (`just-the-docs`) static site** into an AI-augmented campaign operating system.

It solves the common problem of AI assistants hallucinating setting rules, forgetting past session lore, or flattening distinct campaign voices. It achieves this by decoupling **procedural execution (the engine)** from **creative direction (the campaign vault)**:

- **The Engine (`oude-mechanismen`)**: Provides reusable AI skills (transcription, illustration, session prep, linting) and Jekyll site plugins.
- **The Campaign Vault (Your Repository)**: Contains your Markdown notes, setting gazetteer, player dossiers, and a single parameterisation file (`.agents/AGENTS.md`) defining your setting's tone, vocabulary, and calibration examples.

---

## The Three-Tier Canon Hierarchy & Privacy Air-Gap

To keep LLM token usage low, prevent hallucinations, and protect player privacy, `oude-mechanismen` separates raw table media from campaign canon:

- **Tier 0 (Local Disk Air-Gap)**:
  Raw session audio recordings and verbatim speech transcripts reside strictly on local disk at `~/Private/rpg-sessions/<campaign>/`, completely excluded from Git and all synced or networked storage.
- **Tier 1 (Canonical Published Notes)**:
  Published Markdown notes indexed locally on build into `.agents/context/catalog.json` (gitignored derived cache). This is hard campaign canon.
- **Tier 2 (Behind-the-Screen Rulings & Archival Notes)**:
  Structured GM rulings and faction-turn records in `_gm-materials/rulings/`, compiled by `oude tier2` into the derived `_gm-materials/.cache/tier2.json`, alongside de-personalised extraction notes (`_tactical_facts.md`, `_sensory_textures.md`) and 8-section archival session notes (`_session_notes.md`) in `_gm-materials/session-summaries/`.
- **Tier 3 (Reference Material, Digests & Unplayed Prep)**:
  Offline PDF rulebooks (kept on local disk only), structured digests in `_gm-materials/digests/` indexed into `.agents/context/references.json`, and unplayed prep in `_gm-materials/session-preps/`. Influence and inspiration, never assumed canon unless confirmed at the table.

---

## Procedural Skill Catalogue

When linked to your campaign vault, AI coding assistants (such as Antigravity, Claude Code, or Cursor) gain access to 11 specialised campaign skills:

| Skill | Trigger | Purpose | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **`lookup-context`** | `/lookup-context` | Low-token progressive context retrieval across Tiers 1, 2, and 3 | Targeted file snippets & line ranges |
| **`prep-session`** | `/prep-session` | Guided 8-step GM session prep from current situation to map hooks | Structured session briefing & spark tables |
| **`scribe-session`** | `/scribe-session [file]` | Air-gapped Metal GPU transcription, two-pass local Ollama extraction, and Gemini synthesis | Tier 2 `_gm-materials/session-summaries/` 8-section GM notes + calibrated chapter log + dossier condition updates |
| **`illustrate-entry`** | `/illustrate-entry <note>` | Public-domain archival art curation and graphic-novel styling | Styled gallery artwork with archival attribution |
| **`add-chapter`** | `/add-chapter` | Drafts a session chapter with canonical front matter and links | Setting-calibrated chapter in `campaigns/` |
| **`add-character`** | `/add-character` | Dossier authoring for player characters or recurring NPCs | Linked dossier note in `directory/` |
| **`weave-threads`** | `/weave-threads` | Cross-analyses open threads, faction moves, and economic anomalies | Up to 3 actionable plot tie-ins for future sessions |
| **`review-style`** | `/review-style <note>` | Calibrates prose against setting voice, cadence, and vocabulary | Diff review with anchor-and-veil balance |
| **`lint-wiki`** | `/lint-wiki` | Health-checks the campaign wiki for broken links, stubs, and orphans | Markdown audit report & suggested fixes |
| **`digest-book`** | `/digest-book <pdf_path>` | Deterministic PDF slice extraction + synthesis into a validated `_gm-materials/digests/<source>/` wiki | Hyperlinked entity notes, `manifest.json`, clean `references.json` |
| **`crosslink-tiers`** | `/crosslink-tiers` | Cross-links Tier 1 canon and Tier 3 digests via hidden `{% comment %}` link blocks | Idempotent Obsidian-only cross-tier links, invisible on the Jekyll site |

---

## 5-Minute Quickstart

### Prerequisites

- **macOS or Linux**
- **Git**
- **Ruby 3.1+** and **Bundler** (for local Jekyll preview)
- **Python 3.11+** and **[`uv`](https://docs.astral.sh/uv/)** (for the `oude` CLI and procedural tooling)

*(Optional for `/scribe-session` local air-gapped audio transcription & extraction)*:
```bash
brew install ffmpeg whisper-cpp ollama
ollama pull qwen2.5:14b
mkdir -p ~/.whisper-models
curl -L -o ~/.whisper-models/ggml-large-v3-turbo.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
```

---

### Bootstrapping a New Campaign Vault

1. Install the `oude` CLI and global skills (zero local engine clone required):
   ```bash
   uv tool install git+https://github.com/terra-campaigns/oude-mechanismen.git
   oude install-skills
   ```

2. Initialise your new campaign vault:
   ```bash
   oude init ~/Repos/my-new-campaign
   ```

3. Configure your campaign parameters:
   Navigate to `~/Repos/my-new-campaign/.agents/AGENTS.md` and customise:
   - Setting Genre, Tone, and Cadence
   - Calibration Examples (Too flat vs In voice)
   - Sourcebook PDF path in `.agents/context/tier1_sources.yml` (defaults to `drive_dir: .` for in-vault `_gm-materials/`)

4. Install gems, compile the initial catalogue, verify health, and launch the LAN preview:
   ```bash
   cd ~/Repos/my-new-campaign
   bundle install
   bundle exec jekyll build
   oude doctor
   bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""
   ```
   Open `http://localhost:4000` on the host, or `http://<hostname>.local:4000` (e.g. `http://artemis.local:4000` via `avahi-daemon` mDNS) / `http://<host-ip>:4000` from other devices on the same LAN. Preview one vault at a time on port `4000`.

---

### Connecting an Existing Obsidian Vault

If you already have a Markdown-based Obsidian campaign vault:

1. Run the initialiser against your existing vault folder:
   ```bash
   oude init /path/to/my-existing-vault
   ```
   *`oude init` is non-destructive: it will never overwrite your existing notes or configuration files, and registers global agent skills automatically.*

2. Install gems, build the catalogue, and remediate legacy files:
   ```bash
   cd /path/to/my-existing-vault
   bundle install
   bundle exec jekyll build
   oude doctor --fix
   ```

---

## Guides

- [Vault Migration Guide](docs/MIGRATION_GUIDE.md) — move an existing vault off Google Drive onto `_gm-materials/` + Obsidian Sync (`drive_dir: .`), re-anchor `references.json`, and validate with `oude doctor` / `oude audit`.
- [Dynamic Gem Operator Guide](docs/DYNAMIC_GEM.md) — install, configure, customise, and update the `oude-mechanismen` RubyGem that powers the Jekyll build in-memory.

## Updating the Engine

To update the engine across downstream campaign vaults when a new release of `oude-mechanismen` is published:

1. Update the RubyGem tag in the vault `Gemfile` and rebuild:
   ```bash
   cd ~/Repos/my-campaign
   bundle update oude-mechanismen && bundle exec jekyll build
   ```

2. Update the `oude` CLI, re-sync global skills, and audit the vault:
   ```bash
   uv tool install --force git+https://github.com/terra-campaigns/oude-mechanismen.git
   oude install-skills
   oude doctor --fix
   ```

See the [Dynamic Gem Operator Guide](docs/DYNAMIC_GEM.md) for tag-pinning details and troubleshooting.

---

## Release Process & Versioning

`oude-mechanismen` follows [Semantic Versioning 2.0.0](https://semver.org/):

- `MAJOR`: Breaking changes to front-matter schemas or `_includes/` interfaces.
- `MINOR`: New skills, new art filter capabilities, or backwards-compatible flags.
- `PATCH`: Bug fixes, script performance improvements, or prompt refinements.

All changes are documented in [`CHANGELOG.md`](CHANGELOG.md). Downstream vaults track the active engine version in `.agents/context/catalog.json`.

---

## Contributing & Agent Guidelines

If you are developing inside `oude-mechanismen` or pairing with an AI assistant, refer to [`AGENTS.md`](AGENTS.md) for architectural contracts, data flow specifications, and skill authoring rules.

---

## Licence

This project is licensed under the **MIT Licence** — see the [`LICENSE`](LICENSE) file for details.
