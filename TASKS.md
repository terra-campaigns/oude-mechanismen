# Tasks

## Incoming Feedback / Inbox

### [SEMI] Benchmark & Select Optimal Local Models for Session Scribing Workflow

- **Timestamp:** 2026-11-01
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `scripts/transcribe_session.py`, `scripts/scribe_session.py`, `skills/scribe-session`, local Ollama & MLX model profiles
- **Operational Context:** Running local automated session transcription and chapter synthesis without cloud dependency.
- **Specific Friction & Defect:** The scribing workflow relies on default local model configurations (Whisper `large-v3` / `large-v3-turbo` for ASR transcription, and `scribe-14b` / `scribe-14b-bilingual` for LLM synthesis) without an empirical benchmark comparing alternative local model architectures. The operator raised whether we are using the best local models or if we should run multiple models and benchmark them side-by-side. Key trade-offs in ASR transcription accuracy (especially multilingual Portuguese-English table dialogue and RPG terminology), LLM context retention (15k–25k token transcripts), bilingual translation fidelity, adherence to the 8-section GM notes structure, and Apple Silicon Metal GPU generation throughput remain unmeasured.
- **Actionable Remediation:**
  1. Build an empirical test harness in `scripts/benchmark_models.py` running candidate local models against standardised session audio and transcript samples. *(Delivered)*
  2. Benchmark local ASR transcription models (e.g. `mlx-community/whisper-large-v3`, `large-v3-turbo`, `whisper-base/small/medium`) for Metal GPU speed, memory footprint, and multilingual word error rate (WER).
  3. Benchmark local LLM synthesis candidates via Ollama (e.g. `qwen2.5:14b`, `qwen2.5:32b`, `mistral-nemo:12b`, `llama3.3:70b`, `command-r`) on context retention, structural compliance, translation quality, and tokens/second.
  4. Publish benchmark results and document the optimal model choices and recommended Ollama `Modelfile` definitions in `oude-mechanismen`.
  5. Update model resolution in `scripts/scribe_session.py` and downstream campaign templates with the empirically selected models.
- **Status:** Staged for Overnight Run (Harness delivered)

### [SEMI] Automated Archival Image Sourcing, Modification & Review Panel for Unillustrated Wiki Entries

- **Timestamp:** 2026-11-01
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `skills/illustrate-entry`, `skills/lint-wiki`, `scripts/art_filter.py`, `scripts/audit_coverage.py`
- **Operational Context:** Populating missing visual assets across campaign wiki notes (places, NPCs, factions, items, and creatures) without AI hallucination, preserving prose and aesthetic tone.
- **Specific Friction & Defect:** Illustrating entries across a campaign vault currently requires an ad-hoc, manual, one-by-one workflow: identifying unillustrated notes, formulating search queries, querying open-source archives, downloading files, running `art_filter.py`, modifying front matter (`images:` and `footer_content:`), and validating Jekyll builds. As vaults scale to dozens or hundreds of notes, manually auditing coverage and sourcing imagery individually introduces substantial operational friction. There is no automated batch crawler to discover all unillustrated entries across `directory/` and `campaigns/`, query open-source archival databases (e.g. Wikimedia Commons, museum APIs) using note metadata, render styled candidates via `art_filter.py`, and present a consolidated post-processing human review panel (YES/NO / approve / reject / adjust) prior to updating front matter and catalogue indices.
- **Actionable Remediation:**
  1. **Audit & Discovery Pipeline:** Extend `scripts/audit_coverage.py` or build a batch runner (`scripts/populate_imagery.py` / `skills/illustrate-entry`) that crawls all markdown notes in `directory/`, `campaigns/`, and `systems/`, identifying entries where `images:` is missing, empty, or pointing to placeholder badges.
  2. **Automated Non-AI Archival Sourcing:** Formulate structured search queries from entity front matter (title, role, tags, parent) and body keywords, querying open-source cultural/museum repositories (e.g. Wikimedia Commons Action API, Library of Congress, NASA archives) with strict non-AI filtering directives and public-domain / Creative Commons licensing enforcement.
  3. **Batch Graphic-Novel Styling:** Automatically process retrieved candidates through `art_filter.py` using the vault's active aesthetic presets (`aesthetics.yml`), generating high-resolution styled assets with lens flares disabled by default.
  4. **Post-Processing Human Selection Panel:** Render an interactive Generative UI / HTML review studio (or CLI prompt table) displaying the original archival candidate against the styled version with a clear YES/NO selection control, alternate preset switcher, and custom crop/framing options per candidate.
  5. **Atomic Population & Attribution:** Upon human approval (YES), autonomously copy the asset to `imgs/gallery/<slug>.jpg`, update the target note's front matter (`images:` array and formatted `footer_content:` with hyperlink and licence attribution), regenerate `.agents/context/catalog.json`, and run Jekyll build validation.
- **Status:** Open

### [AUTO] Delegate Wiki Linting (`lint-wiki`) to Local On-Device Models

- **Timestamp:** 2026-11-01
- **Origin:** `artifice` on `agent/ecosystem-governance-and-coordination`
- **Component:** `skills/lint-wiki/SKILL.md`, `scripts/`
- **Operational Context:** Structural auditing and diagnostic reporting across narrative campaign lore and static site notes.
- **Specific Friction & Defect:** Running `lint-wiki` across dozens or hundreds of vault notes currently consumes frontier cloud model quota. Because this audit is advisory and non-critical (checking for dead links, orphan pages, stubs, image references, and catalogue health), burning cloud API limits on routine vault sweeps is inefficient and risks quota exhaustion during active coding sessions.
- **Actionable Remediation:**
  1. Update `skills/lint-wiki/SKILL.md` to target local Ollama models (`qwen2.5:14b` or `mistral-nemo:12b`) for contextual summarisation and diagnostic evaluation.
  2. Offload deterministic mechanical checks (verifying relative link existence, stub line counts, missing frontmatter keys) to a fast local Python script, reserving the local LLM strictly for contextual analysis and report formatting.
  3. Ensure execution runs 100% on-device with zero cloud API token burn.
- **Status:** Open

### [AUTO] Upstream Engine Enforcement of Notebook-Centric Delivery & Read-Aloud Text Prohibition

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `AGENTS.md`, `skills/` (all procedural skills), `templates/`
- **Operational Context:** Authoring procedural skills, session prep, and GM-facing outputs across campaign vaults.
- **Specific Friction & Defect:** The rule prohibiting boxed read-aloud narrative text (`> Table Read-Aloud`) and mandating terse, notebook-centric delivery (1-line sensory cues, 1-line tactical facts, and sharp, bulleted player choices) was empirically established in `hostile` and patched locally into `skills/prep-session/SKILL.md` and `templates/AGENTS.md.template`. However, this invariant has not been codified upstream into the engine's core architectural contract in `oude-mechanismen/AGENTS.md` (specifically `## 6. Authoring New Skills`), nor audited systematically across all procedural skills (`weave-threads`, `prep-session`, `scribe-session`, `add-chapter`). Unaware agents executing or developing skills may still default to generating verbose boxed narrative or scripted monologue paragraphs unsuited for physical GM notebooks.
- **Actionable Remediation:**
  1. Update `oude-mechanismen/AGENTS.md` under `## 6. Authoring New Skills` to enshrine the prohibition of read-aloud boxed text and the requirement for notebook-centric delivery as universal engine-wide standards.
  2. Audit all procedural skills in `skills/` to ensure none recommend, template, or generate boxed read-aloud paragraphs or conversational monologues.
  3. Ensure `templates/AGENTS.md.template` strictly enforces this invariant for all newly bootstrapped campaign vaults.
  4. Finalise, verify, and merge the `v0.1.1` release branch upstream to `main` with these changes.
- **Status:** Open

### [SEMI] Architectural Evaluation: Dynamic Engine Usage vs Sync-Based Distribution

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `efsalvarenga/session-003-the-deep-dive`
- **Component:** `sync.sh`, `scripts/`, `templates/`, `_plugins/`, `skills/`, distribution architecture
- **Operational Context:** Synchronising engine updates between `oude-mechanismen` and downstream campaign vaults (e.g. `hostile`), maintaining `.engine-version`, and evaluating engine maintainability compared with the `artifice` dynamic ecosystem model.
- **Specific Friction & Defect:** `oude-mechanismen` currently mirrors the `arete` / `arete-engine` file-synchronisation model: it copies managed files (`_plugins/data_extractor.rb`, `_includes/`, `githooks/`, `runners/`, `bin/setup`) and template files directly into each downstream campaign repository via `sync.sh`, tracking version drift and stamping `.engine-version`. While this ensures downstream repositories remain self-contained for standalone builds, it incurs substantial operational overhead:
  1. *Maintenance Overhead:* Any bug fix, enhancement, or refactoring in `_plugins/data_extractor.rb`, `sync.sh`, or runner scripts requires running `sync.sh` across every campaign vault and authoring repetitive PRs.
  2. *Drift & Reconciliation Risk:* Downstream repositories risk silent divergence if local edits occur, requiring `--force` overrides or manual file diffing.
  3. *Repository Clutter:* Downstream vaults accumulate duplicate copies of engine plumbing files rather than focusing purely on narrative notes and campaign parameters.
  Conversely, `artifice` operates dynamically: capabilities, agents, and skills are mounted globally or discovered directly from the centralised repository, completely eliminating file copying and synchronisation overhead.
- **Actionable Remediation:**
  1. Conduct an architectural feasibility study comparing the sync-based model (`sync.sh`, file copying) against a dynamic model (like `artifice` global mounting, Ruby gems, or symlinks).
  2. Evaluate dynamic decoupling mechanisms across each layer:
     - *Agent Skills & Personas:* Mount `oude-mechanismen/skills/` globally via Antigravity discovery paths or project-level pointer configs (`skills.json`) without copying templates into vault trees.
     - *Jekyll Plugins & Includes:* Investigate packaging `_plugins/data_extractor.rb` and shared `_includes/` as a local Bundler path gem (`gem 'oude-mechanismen', path: '...'`), a Rubygems/GitHub gem, or dynamic Jekyll load paths (`plugins_dir`), auditing GitHub Pages / CI build compatibility.
     - *Scripts & CLI Tooling:* Provide a centralised CLI or execution wrapper (`oude transcribe ...`, `oude digest ...`) that downstream vaults call directly from `oude-mechanismen/scripts/` without duplicating runner scripts.
     - *Git Hooks:* Evaluate configuring `git config core.hooksPath` to point directly to `oude-mechanismen/githooks/`.
  3. Analyse CI/CD and air-gap boundaries: Determine how a dynamic model behaves in headless CI (GitHub Actions) where sibling repositories are not cloned by default.
  4. Author an Architectural Decision Record (ADR) detailing options (Pure Dynamic, Hybrid, or Refined Sync) with migration costs and trade-offs for GM review.
- **Status:** Open

### [AUTO] Codify Mandatory Pre-Publishing Audit Gate (2-4 Framework, Tone Polish, and Wiki Linting)

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `efsalvarenga/session-003-the-deep-dive`
- **Component:** `skills/add-chapter/SKILL.md`, `skills/lint-wiki/SKILL.md`, `skills/review-style/SKILL.md`, pre-publishing audit workflow
- **Operational Context:** Evaluating campaign readiness and finalising session logs before publishing / merging to `main`.
- **Specific Friction & Defect:** When the operator asked *"What is still left before publishing?"*, the agent checked only Git branch cleanliness, CI passing, and Jekyll compilation, completely forgetting three essential campaign quality gates:
  1. *Structural Framework Enforcement (The 2-4 Rule):* Verifying that chapter prose strictly adheres to 2–4 headings total, 2–4 paragraphs per heading, 2–4 sentences per paragraph, and one sentence per line. In Session 3, paragraphs had drifted to 7 and 5 sentences without automated detection.
  2. *Setting Voice & Tone Review (`review-style`):* Reviewing Portuguese and British English prose against `AGENTS.md` setting conventions (workplace realism, terse industrial cadence, sensory grime, zero read-aloud boxed prose).
  3. *Wiki Structural Linting (`lint-wiki`):* Verifying that internal relative markdown links resolve to existing notes and confirming that all referenced image assets exist on disk.
  The human operator had to manually intervene and remind the agent of these missing gates. This failure occurred because pre-publishing requirements were scattered across disconnected skills rather than bound into a single mandatory pre-flight publishing gate.
- **Actionable Remediation:**
  1. Author a dedicated static chapter linter in `scripts/lint_chapter.py` (or integrate into `skills/lint-wiki`) that mathematically parses chapter files to verify:
     - Heading count (2 to 4).
     - Paragraph count per heading (2 to 4).
     - Sentence count per paragraph (2 to 4, each on its own line).
     - Reporting precise line numbers and sentence counts upon deviation.
  2. Codify a formal **3-Gate Pre-Publishing Protocol** in `skills/add-chapter/SKILL.md` and `templates/AGENTS.md.template`:
     - *Gate 1 (Prose Architecture):* Mathematical verification of the 2-4 framework and one-sentence-per-line cadence.
     - *Gate 2 (Tone & Style Calibration):* Tone check against `AGENTS.md` specifications in both languages.
     - *Gate 3 (Wiki & Asset Lint):* Complete resolution check of all relative markdown links and image references on disk.
  3. Mandate that whenever an agent is asked if a chapter or session is ready to publish, it must autonomously execute and report the results of this 3-Gate Audit before declaring readiness.
- **Status:** Open

### [AUTO] Enforce Automatic Branch Deletion Upon PR Closure Across Campaign Vaults

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `efsalvarenga/session-003-the-deep-dive`
- **Component:** `sync.sh`, `templates/AGENTS.md.template`, GitHub repo configuration
- **Operational Context:** Managing feature branches, pull request lifecycles, and git hygiene across campaign vaults.
- **Specific Friction & Defect:** Feature branches created for session scribing, chapter additions, or gazetteer updates often persist on remote repositories after pull requests are merged or closed. Retaining stale, merged feature branches clutters git topology and requires manual branch deletion passes.
- **Actionable Remediation:**
  1. Update `templates/AGENTS.md.template` under `## Agent Behaviour` to enshrine the invariant:
     - *"Branch Lifecycle: Feature branches must be deleted immediately after their corresponding Pull Request is merged or closed. Never retain merged remote or local feature branches."*
  2. In `sync.sh --init`, configure the target GitHub repository to enable automatic head branch deletion on merge (`gh repo edit "$REPO" --delete-branch-on-merge`).
  3. Ensure post-merge cleanup instructions in all procedural skills (`add-chapter`, `scribe-session`) explicitly instruct local branch deletion (`git branch -d <branch>`).
- **Status:** Open
