# Oude Mechanismen (Ancient Machinery)

Shared campaign engine, procedural agent skills, and Jekyll static site tooling for tabletop RPG campaign vaults.

Powering [Charged](https://github.com/terra-campaigns/charged) and [Hostile](https://github.com/terra-campaigns/hostile).

---

## Architectural Principles

`oude-mechanismen` decouples **procedural workflows (the engine)** from **creative direction (the specification & lore)** across campaign vaults:

1. **Procedural Agent Skills (`skills/`)**:
   - Universal workflows for campaign maintenance: progressive context retrieval (`lookup-context`), wiki structural linting (`lint-wiki`), surgical style reviews (`review-style`), chapter creation (`add-chapter`), NPC/PC dossiers (`add-character`), session preparation (`prep-session`), narrative thread weaving (`weave-threads`), and automated recording transcription & chapter scribing (`scribe-session`).
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
├── requirements.txt            # Python dependencies for shared scripts (pypdf, pyyaml)
├── sync.sh                     # Syncs Jekyll plugins, includes, and git hooks to campaign repos
├── skills/                     # Shared Antigravity skills
│   ├── lookup-context/
│   ├── lint-wiki/
│   ├── review-style/
│   ├── add-chapter/
│   ├── add-character/
│   ├── prep-session/
│   ├── weave-threads/
│   └── scribe-session/
├── scripts/                    # Shared campaign tooling
│   ├── generate_digests.py     # Scaffolds Tier 3 digests from PDFs & compiles references.json
│   ├── compile_references.py   # Symlink alias for generate_digests.py
│   ├── audit_coverage.py       # Structural audit of campaign coverage and topology
│   └── transcribe_session.py   # Metal GPU ASR & dynamic glossary extraction
├── jekyll/                     # Source-of-truth Jekyll engine
│   ├── _plugins/
│   │   ├── data_extractor.rb
│   │   └── llm_content.rb
│   ├── _includes/
│   │   ├── connected_to.html
│   │   ├── header_chapter.md
│   │   ├── header_directories.md
│   │   └── image_gallery.html
│   └── all-content.md
├── githooks/
│   └── pre-commit              # Git hook to refresh catalog.json on commit
└── templates/                  # Scaffolding templates for campaign repositories
    ├── AGENTS.md.template
    ├── tier1_sources.yml.template
    ├── decisions.md.template
    ├── skills.json.template
    ├── route_graph.json.template
    └── requirements.txt.template
```

---

## Usage

### Setting Up a Campaign Repository

Every campaign vault synchronised with `oude-mechanismen` includes a fast, idempotent setup script at `bin/setup`. In a newly cloned campaign vault:

```bash
./bin/setup
```

This automatically:
1. Detects `oude-mechanismen` across standard paths (or via `$OUDE_MECHANISMEN_DIR`).
2. Configures Git hooks (`.githooks/pre-commit`).
3. Creates `.agents/venv` and installs shared Python dependencies (`pyyaml`, `pypdf`).
4. Verifies Tier 1 catalogue compilation with `data_extractor.rb`.

### Linking Skills to a Campaign Repository

In your campaign vault's `.agents/skills.json`, include redundant fallback paths for local development and shared workspaces:

```json
{
  "entries": [
    {
      "path": "../oude-mechanismen/skills"
    },
    {
      "path": "~/Repos/oude-mechanismen/skills"
    }
  ]
}
```

### Multi-Repository CI Workflow

For GitHub Actions workflows requiring access to shared engine scripts or skills, checkout both repositories side-by-side:

```yaml
- name: Checkout Campaign Vault
  uses: actions/checkout@v4
  with:
    path: charged

- name: Checkout Engine
  uses: actions/checkout@v4
  with:
    repository: terra-campaigns/oude-mechanismen
    path: oude-mechanismen

- name: Setup Campaign Environment
  run: |
    cd charged
    ./bin/setup
```

### Python Dependencies

The procedural scripts (`generate_digests.py`, `audit_coverage.py`, `transcribe_session.py`) require `pyyaml` and `pypdf`. In your campaign vault or virtual environment:

```bash
pip install -r requirements.txt
```

### Tier 3 Reference Scaffolding & Indexing

To scaffold a new Tier 3 Markdown digest directly from a PDF in Google Drive (extracting chapter bookmarks and page ranges):

```bash
python3 .agents/scripts/generate_digests.py --scaffold "cores/MyNewBook.pdf"
```

To recompile `.agents/context/references.json` across all existing Markdown digests in `_digests/`:

```bash
python3 .agents/scripts/generate_digests.py
```

### Syncing Jekyll Engine Files

To propagate Jekyll engine updates, runner wrappers, and Git hooks to downstream campaign repositories:

```bash
./sync.sh ../charged ../hostile
```

#### Safe Auditing & Diffing

`sync.sh` provides built-in drift detection and dirty-tree safety checks:

- **Check status without modifying files**:
  ```bash
  ./sync.sh --check ../charged
  ```
- **Inspect unified diffs of outdated files**:
  ```bash
  ./sync.sh --check --diff ../charged
  ```
- **Force overwrite dirty files with uncommitted local changes**:
  ```bash
  ./sync.sh --force ../charged
  ```

### Audio Transcription & Session Scribe Pipeline (macOS)

`scribe-session` provides a single-pass end-to-end pipeline that transcribes table session recordings locally on Apple Silicon Metal GPUs and synthesises both Google Drive archival notes and an in-voice repository chapter.

#### 1. One-Time macOS Setup

Install the required CLI dependencies and download OpenAI's Whisper Large-v3-Turbo model:

```bash
brew install ffmpeg whisper-cpp
mkdir -p ~/.whisper-models
curl -L -o ~/.whisper-models/ggml-large-v3-turbo.bin \
  "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin"
```

*(Optional)* If capturing Discord voice calls locally, install OBS Studio:

```bash
brew install --cask obs
```

In OBS, configure **macOS Audio Capture** (*Application Capture* $\rightarrow$ `Discord`) and **Audio Input Capture** (hardware microphone) recording to `.mkv` or `.mp4`.

#### 2. Running the Pipeline

From within any campaign repository in Antigravity:

```text
/scribe-session ~/Movies/Session_12.mkv
```

Alternatively, invoke the acoustic pre-processor directly via the command line:

```bash
python3 ../oude-mechanismen/scripts/transcribe_session.py ~/Movies/Session_12.mkv
```

The pipeline:
1. Compiles a dynamic proper-noun glossary from `.agents/context/catalog.json` and prompts Whisper.
2. Normalises the recording to 16 kHz mono WAV and transcribes on Apple Metal GPU in minutes.
3. Synthesises structured archival GM session notes in `<drive_dir>/_sessions/<slug>_session_notes.md`.
4. Drafts a canonical, cross-linked chapter in `campaigns/<Campaign>/<chapter>.md` calibrated to the setting voice.
5. Refreshes `.agents/context/catalog.json` and leaves repository files unstaged for review.
