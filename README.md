# Oude Mechanismen (Ancient Machinery)

Shared campaign engine, procedural agent skills, and Jekyll static site tooling for tabletop RPG campaign vaults.

[![Version](https://img.shields.io/badge/version-0.1.0-blue.svg)](VERSION)
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

## The Three-Tier Canon Hierarchy

To keep LLM token usage low and prevent hallucinations, `oude-mechanismen` structures information into three explicit tiers:

1. **Tier 1 (Canonical Published Notes)**:
   Published Markdown notes indexed automatically into `.agents/context/catalog.json`. This is hard campaign canon.
2. **Tier 2 (Active Table Decisions)**:
   Confirmed GM rulings, procedural interpretations, and table consensus logged in `.agents/context/decisions.md`.
3. **Tier 3 (External Reference Material & Sourcebooks)**:
   Offline PDF rulebooks and setting digests in `_digests/`, indexed into `.agents/context/references.json`. Influence and inspiration, never assumed canon unless confirmed at the table.

---

## Procedural Skill Catalogue

When linked to your campaign vault, AI coding assistants (such as Antigravity, Claude Code, or Cursor) gain access to 9 specialised campaign skills:

| Skill | Trigger | Purpose | Key Deliverables |
| :--- | :--- | :--- | :--- |
| **`lookup-context`** | `/lookup-context` | Low-token progressive context retrieval across Tiers 1, 2, and 3 | Targeted file snippets & line ranges |
| **`prep-session`** | `/prep-session` | Guided 8-step GM session prep from current situation to map hooks | Structured session briefing & spark tables |
| **`scribe-session`** | `/scribe-session <file>` | Single-pass session recording transcription and synthesis | Dual output: Google Drive GM notes + in-voice chapter log |
| **`illustrate-entry`** | `/illustrate-entry <note>` | Public-domain archival art curation and graphic-novel styling | Styled gallery artwork + interactive slider studio |
| **`add-chapter`** | `/add-chapter` | Drafts a session chapter with canonical front matter and links | Setting-calibrated chapter in `campaigns/` |
| **`add-character`** | `/add-character` | Dossier authoring for player characters or recurring NPCs | Linked dossier note in `directory/` |
| **`weave-threads`** | `/weave-threads` | Cross-analyses open threads, faction moves, and economic anomalies | Up to 3 actionable plot tie-ins for future sessions |
| **`review-style`** | `/review-style <note>` | Calibrates prose against setting voice, cadence, and vocabulary | Diff review with anchor-and-veil balance |
| **`lint-wiki`** | `/lint-wiki` | Health-checks the campaign wiki for broken links, stubs, and orphans | Markdown audit report & suggested fixes |

---

## 5-Minute Quickstart

### Prerequisites

- **macOS or Linux**
- **Git**
- **Ruby 3.1+** and **Bundler** (for local Jekyll preview)
- **Python 3.10+** (for procedural runners)

*(Optional for `/scribe-session` audio transcription)*:
```bash
brew install ffmpeg whisper-cpp
mkdir -p ~/.whisper-models
curl -L -o ~/.whisper-models/ggml-large-v3-turbo.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
```

---

### Bootstrapping a New Campaign Vault

1. Clone `oude-mechanismen`:
   ```bash
   git clone https://github.com/terra-campaigns/oude-mechanismen.git ~/Repos/oude-mechanismen
   ```

2. Initialize your new campaign vault:
   ```bash
   cd ~/Repos/oude-mechanismen
   ./sync.sh --init ~/Repos/my-new-campaign
   ```

3. Configure your campaign parameters:
   Navigate to `~/Repos/my-new-campaign/.agents/AGENTS.md` and customize:
   - Setting Genre, Tone, and Cadence
   - Calibration Examples (Too flat vs In voice)
   - Sourcebook PDF directory in `.agents/context/tier1_sources.yml`

4. Launch Jekyll locally:
   ```bash
   cd ~/Repos/my-new-campaign
   bundle install
   bundle exec jekyll serve
   ```
   Open `http://localhost:4000` to browse your campaign site.

---

### Connecting an Existing Obsidian Vault

If you already have a Markdown-based Obsidian campaign vault:

1. Run the initialiser against your existing vault folder:
   ```bash
   cd ~/Repos/oude-mechanismen
   ./sync.sh --init /path/to/my-existing-vault
   ```
   *`sync.sh` is non-destructive: it will never overwrite your existing notes or configuration files.*

2. Run the environment setup:
   ```bash
   cd /path/to/my-existing-vault
   ./bin/setup
   ```

3. Ensure `.agents/skills.json` points to your `oude-mechanismen/skills` folder.

---

## Updating the Engine

To update downstream campaign vaults when a new release of `oude-mechanismen` is published:

1. Pull the latest engine code:
   ```bash
   cd ~/Repos/oude-mechanismen
   git pull origin main
   ```

2. Synchronise downstream vaults:
   ```bash
   # Inspect what will change without modifying files:
   ./sync.sh --check ~/Repos/my-campaign

   # View unified diffs of updated engine templates:
   ./sync.sh --check --diff ~/Repos/my-campaign

   # Apply updates:
   ./sync.sh ~/Repos/my-campaign
   ```

---

## Release Process & Versioning

`oude-mechanismen` follows [Semantic Versioning 2.0.0](https://semver.org/):

- `MAJOR`: Breaking changes to front-matter schemas or `_includes/` interfaces.
- `MINOR`: New skills, new art filter capabilities, or backwards-compatible flags.
- `PATCH`: Bug fixes, script performance improvements, or prompt refinements.

All changes are documented in [`CHANGELOG.md`](CHANGELOG.md). Downstream vaults track the active engine version in `.agents/.engine-version`.

---

## Contributing & Agent Guidelines

If you are developing inside `oude-mechanismen` or pairing with an AI assistant, refer to [`AGENTS.md`](AGENTS.md) for architectural contracts, data flow specifications, and skill authoring rules.

---

## Licence

This project is licensed under the **MIT Licence** — see the [`LICENSE`](LICENSE) file for details.
