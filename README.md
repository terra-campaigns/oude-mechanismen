# Oude Mechanismen (Ancient Machinery)

Shared campaign engine, procedural agent skills, and Jekyll static site tooling for tabletop RPG campaign vaults.

Powering [Charged](https://github.com/terra-campaigns/charged) and [Hostile](https://github.com/terra-campaigns/hostile).

---

## Architectural Principles

`oude-mechanismen` decouples **procedural workflows (the engine)** from **creative direction (the specification & lore)** across campaign vaults:

1. **Procedural Agent Skills (`skills/`)**:
   - Universal workflows for campaign maintenance: progressive context retrieval (`lookup-context`), wiki structural linting (`lint-wiki`), surgical style reviews (`review-style`), chapter creation (`add-chapter`), NPC/PC dossiers (`add-character`), session preparation (`prep-session`), and narrative thread weaving (`weave-threads`).
   - Dynamically loaded into local Antigravity sessions via `.agents/skills.json` without duplicating code.
   - Parameterised: each skill queries the target project's `.agents/AGENTS.md` (and context layer) for setting tone, genre conventions, PDF reference locations, and calibration examples.

2. **Jekyll Static Site Engine (`jekyll/`)**:
   - Canonical Jekyll plugins (`data_extractor.rb`, `llm_content.rb`) and reusable includes (`connected_to.html`, `header_chapter.md`, `header_directories.md`, `image_gallery.html`).
   - Generates the Tier 1 semantic catalogue (`.agents/context/catalog.json`), backlinks, and gallery links in memory and on disk.
   - Distributed as physical files to campaign repositories via `sync.sh` to ensure GitHub Actions builds succeed natively without cross-repository symlink issues.

3. **Three-Tier Canon Architecture**:
   - **Tier 1 (Canonical Published Notes)**: Published campaign markdown notes indexed by `data_extractor.rb` into `.agents/context/catalog.json`.
   - **Tier 2 (Conversation & Table Rulings)**: Active GM decisions and rulings logged in `.agents/context/decisions.md`.
   - **Tier 3 (External Source Material & Rulebooks)**: Offline PDF digests and routing indices compiled by `scripts/generate_digests.py` into `.agents/context/references.json`.

---

## Repository Structure

```text
oude-mechanismen/
├── README.md
├── sync.sh                     # Syncs Jekyll plugins, includes, and git hooks to campaign repos
├── skills/                     # Shared Antigravity skills
│   ├── lookup-context/
│   ├── lint-wiki/
│   ├── review-style/
│   ├── add-chapter/
│   ├── add-character/
│   ├── prep-session/
│   └── weave-threads/
├── scripts/                    # Shared campaign tooling
│   ├── generate_digests.py     # Compiles Tier 3 Markdown digests and references.json
│   └── audit_coverage.py       # Structural audit of campaign coverage and topology
├── jekyll/                     # Source-of-truth Jekyll engine
│   ├── _plugins/
│   │   ├── data_extractor.rb
│   │   └── llm_content.rb
│   ├── _includes/
│   │   ├── connected_to.html
│   │   ├── header_chapter.md
│   │   ├── header_directories.md
│   │   └── image_gallery.html
│   ├── all-agent.md
│   └── all-content.md
├── githooks/
│   └── pre-commit              # Git hook to refresh catalog.json on commit
└── templates/                  # Scaffolding templates for campaign repositories
    ├── AGENTS.md.template
    ├── tier1_sources.yml.template
    ├── decisions.md.template
    └── skills.json.template
```

---

## Usage

### Linking Skills to a Campaign Repository

In your campaign vault's `.agents/skills.json`:

```json
{
  "entries": [
    {
      "path": "../../oude-mechanismen/skills"
    }
  ]
}
```

### Syncing Jekyll Engine Files

To propagate Jekyll engine updates and Git hooks to your campaign repositories:

```bash
./sync.sh ../charged ../hostile
```
