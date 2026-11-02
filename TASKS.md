# Tasks

## Incoming Feedback / Inbox

### [SEMI] Benchmark & Select Optimal Local Models for Session Scribing Workflow

- **Timestamp:** 2026-11-01
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `scripts/transcribe_session.py`, `scripts/scribe_session.py`, `skills/scribe-session`, local Ollama & MLX model profiles
- **Operational Context:** Running local automated session transcription and chapter synthesis without cloud dependency.
- **Specific Friction & Defect:** The scribing workflow relies on default local model configurations (Whisper `large-v3` / `large-v3-turbo` for ASR transcription, and `scribe-14b` / `scribe-14b-bilingual` for LLM synthesis) without an empirical benchmark comparing alternative local model architectures. The operator raised whether we are using the best local models or if we should run multiple models and benchmark them side-by-side. Key trade-offs in ASR transcription accuracy (especially multilingual Portuguese-English table dialogue and RPG terminology), LLM context retention (15k–25k token transcripts), bilingual translation fidelity, adherence to the 8-section GM notes structure, and Apple Silicon Metal GPU generation throughput remain unmeasured.
- **Actionable Remediation:**
  1. Build an empirical test harness in `scripts/` (e.g. `scripts/benchmark_models.py` or extending `scribe_session.py --benchmark`) running candidate local models against standardised session audio and transcript samples.
  2. Benchmark local ASR transcription models (e.g. `mlx-community/whisper-large-v3`, `large-v3-turbo`, `whisper-base/small/medium`) for Metal GPU speed, memory footprint, and multilingual word error rate (WER).
  3. Benchmark local LLM synthesis candidates via Ollama (e.g. `qwen2.5:14b`, `qwen2.5:32b`, `mistral-nemo:12b`, `llama3.3:70b`, `command-r`) on context retention, structural compliance, translation quality, and tokens/second.
  4. Publish benchmark results and document the optimal model choices and recommended Ollama `Modelfile` definitions in `oude-mechanismen`.
  5. Update model resolution in `scripts/scribe_session.py` and downstream campaign templates with the empirically selected models.
- **Status:** Open

### [AUTO] Add Pre-Flight Repo State Identification Step to Session Scribing Workflow

- **Timestamp:** 2026-11-01
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `scripts/scribe_session.py`, `scripts/transcribe_session.py`, `skills/scribe-session`
- **Operational Context:** Initiating the automated session scribing and chapter synthesis workflow.
- **Specific Friction & Defect:** The session scribing workflow currently initiates audio processing, transcription, and LLM drafting immediately without first evaluating the target vault's repository state. If the working tree contains uncommitted human edits, unmerged chapter branches, outdated catalogue indices, or an in-progress session prep draft (e.g. `prep_ep_003.md`), the script may misidentify the next chapter number, overwrite uncommitted changes, or synthesise prose against an out-of-date catalogue.
- **Actionable Remediation:**
  1. Add an empirical Stage 0 pre-flight repository reconnaissance step (inspired by the `coordinate-fronts` Step 1 recon pattern) to `scripts/scribe_session.py` and `skills/scribe-session`.
  2. In Stage 0, empirically inspect:
     - Active Git branch and working tree status (`git status --short`).
     - Presence of uncommitted chapter files or pending prep notes in the target campaign subfolder.
     - Build and catalogue health check (`data_extractor.rb` validation).
     - Target chapter number resolution and collision check before touching any files.
  3. Output a clean pre-flight status card before transcription begins. If a blocking collision or dirty state is detected, warn the operator and require confirmation (or a `--force` flag) rather than writing into a conflicted working tree.
- **Status:** Open

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

### [AUTO] Automated Character Dossier Conditions Reconciliation in Post-Session Pipeline

- **Timestamp:** 2026-11-01
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `scripts/scribe_session.py`, `skills/scribe-session`, `directory/` character YAML front matter
- **Operational Context:** Executing post-session transcription, session notes logging, and canonical chapter publishing.
- **Specific Friction & Defect:** The post-session scribing pipeline (`scripts/scribe_session.py` and `skills/scribe-session`) synthesises comprehensive archival GM notes (`_sessions/<slug>_session_notes.md`) and drafts the bilingual campaign chapter (`campaigns/<campaign>/<num>.md`). However, physiological, cybernetic, and psychological conditions sustained during play (such as Olmo's leaking abdominal ballistic trauma or Ezekiel's acute panic and withdrawal tremors) recorded in Section 5 (Combat, Hazards & Encounters) and Section 2 (Plot Beats) of the session notes are not reflected in character records. The user explicitly decided against automated equipment/inventory tracking in dossiers, requiring that only **conditions** are reconciled, and that they must reside strictly in the **YAML front matter** of the character markdown file (e.g. `conditions:` list), leaving body text notes untouched.
- **Actionable Remediation:**
  1. Extend `scripts/scribe_session.py` and `skills/scribe-session` with an automated character conditions reconciliation stage:
     - Identify active player characters and key NPCs attending the session from the session glossary and plot beats.
     - Parse Section 5 (Combat, Hazards & Encounters) and Section 2 (Plot Beats) from the synthesised session notes for newly sustained, aggravated, or cleared conditions (wounds, trauma, psychological states).
     - Autonomously update the YAML front matter of the respective character notes in `directory/<hub>/<character>.md` by populating or updating the `conditions:` list (leaving the markdown body and equipment sections untouched).
     - Synchronise associated YAML front matter trackers (`status`, `stress`, `bends`) when modified during play.
  2. Present the reconciled YAML conditions diff to the GM as part of the post-session completion summary.
  3. Document the YAML `conditions:` specification in `skills/scribe-session/SKILL.md` and `templates/AGENTS.md.template`.
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

### [AUTO] Refactor Scribing Pipeline into Decomposed, Air-Gapped Local Multi-Pass Architecture

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `efsalvarenga/session-003-the-deep-dive`
- **Component:** `scripts/scribe_session.py`, `scripts/transcribe_session.py`, `skills/scribe-session`
- **Operational Context:** User-triggered post-session transcription, archival GM notes generation, chapter drafting, and character reconciliation with strict air-gapped privacy safeguarding.
- **Specific Friction & Defect:** The existing implementation of `scripts/scribe_session.py` relied on monolithic single-shot prompting—feeding an entire 20,000-word raw transcript into a local 14B model to simultaneously generate front matter, Liquid includes, Dataview queries, 8-section GM notes, Portuguese narrative prose, and a mirror British English translation. In practice, this caused context saturation, sentence repetition loops, language layout confusion (alternating PT/EN paragraphs instead of clean sectioning below `---`), and misspellings (e.g. "Silas" instead of "Silus"). Furthermore:
  1. *Air-Gap Privacy Mandate:* Raw session recordings and verbatim transcripts contain private table audio and player banter. They must never enter cloud LLM contexts or external APIs. All speech and transcript processing must execute 100% on-device (Apple Metal GPU Whisper + local Ollama).
  2. *Trigger Model:* Background folder watchers (`launchd`) and daemon hooks introduce unnecessary operational fragility. The pipeline must be cleanly user-triggered (e.g. telling the agent in chat or running a single CLI command).
  3. *Unnecessary LLM Hallucinations:* Front matter, Dataview blocks, Liquid tags, and relative directory links should never be generated by an LLM when Python can construct them deterministically from `catalog.json` with 100% mathematical accuracy.
- **Actionable Remediation:**
  1. *Pass 1 (Deterministic Acoustic Extraction):*
     - Normalise audio with `ffmpeg` and extract proper-noun glossary from `catalog.json` / `AGENTS.md`.
     - Transcribe locally via `whisper-cli` (`ggml-large-v3-turbo.bin`, `-l pt`) on Apple Metal GPU.
     - Save audio and transcript strictly to `~/Private/rpg-sessions/<campaign>/` (local disk air-gap, never uploaded or ingested into cloud chat).
  2. *Pass 2 (Local Structured GM Notes Extraction):*
     - Call local Ollama (`qwen2.5:14b` / `mistral-nemo:12b` on `localhost:11434`) to extract the 8 canonical archival sections into Google Drive `_sessions/<slug>_session_notes.md` (Tier 2 Canon).
     - Condenses 20k words of conversational dialogue into ~1,500 words of structured timeline beats, combat encounters, sustained wounds, and candidate rulings.
  3. *Pass 3 (Local Bilingual Chapter Generation):*
     - Decompose prose drafting into two focused local calls:
       - Step 3A: Generate Portuguese narrative prose from condensed GM notes + `AGENTS.md` style calibration.
       - Step 3B: Generate British English mirror translation below `---`.
     - Generate YAML front matter, Dataview blocks, and relative directory links deterministically via Python glue (not LLM), guaranteeing 0 hallucinations and valid Jekyll syntax.
  4. *Pass 4 (Deterministic Character Conditions Reconciliation):*
     - Parse Section 4/5 of the GM notes for sustained conditions, wounds, and stress changes.
     - Autonomously update YAML front matter `conditions:` and `stress:` in `directory/.../<character>.md` without modifying markdown body text.
  5. *Pass 5 (Local Build Gate & Git Drafting):*
     - Verify local build via `bundle exec jekyll build` (ensuring 0 errors and valid catalogue).
     - Switch to feature branch `efsalvarenga/session-<num>-<slug>`, commit, push to origin, and open a Draft PR via `gh pr create --draft` for human review (`[HUMAN]`).
- **Status:** In Progress (Phase 1 completed)

### [AUTO] Multi-Pass / Dual-Model Sensory & Fact Extraction from Session Transcripts

- **Timestamp:** 2026-11-02
- **Origin:** `hostile` on `efsalvarenga/session-003-the-deep-dive`
- **Component:** `scripts/transcribe_session.py`, `skills/scribe-session`, local Ollama model ensemble
- **Operational Context:** Processing raw session transcripts into archival GM notes and narrative chapter prose with high fidelity to spoken table descriptions.
- **Specific Friction & Defect:** A single-pass extraction prompt over a raw 20,000-word conversational transcript inevitably focuses on broad chronological plot beats (e.g. "fled up duct, found shotgun") while omitting vital environmental and sensory details, subtle table rulings, and tactile descriptions. During Session 3, human review revealed that the single pass missed crucial atmospheric elements: flickering dying white fluorescent tubes, the heavy rancid metallic reek of copper and oxidised iron, coarse zero-G walls encrusted in dark dried blood, Olmo's explicit hybrid android composition (minor human, major machine), and the specific improvised defense of wedging a sword into rotary hatch gears to bar hostile androids. A single LLM pass suffers from selective attention; executing a targeted second pass (or leveraging a complementary local model architecture, such as `mistral-nemo:12b` for sensory/narrative mining alongside `qwen2.5:14b` for chronological facts) extracts substantially higher-fidelity campaign lore.
- **Actionable Remediation:**
  1. Refactor the post-transcription extraction stage in `skills/scribe-session` and the scribing pipeline to incorporate a structured **two-pass / dual-model extraction architecture**:
     - *Pass 1 (Chronological & Tactical Extraction):* Target hard structural facts—timeline sequence, mechanical checks, combat actions, sustained wounds/stress, and item acquisitions (ideal for `qwen2.5:14b`).
     - *Pass 2 (Sensory, Environmental & Canon Extraction):* Target evocative atmospheric details—lighting conditions, ambient odours, tactile materials, room acoustics, environmental stains, and implicit table worldbuilding/character rulings (ideal for `mistral-nemo:12b` or a specialised sensory prompt).
  2. Implement an automated reconciliation step that merges Pass 1 tactical beats with Pass 2 sensory textures into the canonical 8-section GM notes before chapter drafting.
  3. Benchmark extraction fidelity and token efficiency between single-model two-pass prompt chaining versus dual-model ensembling in `scripts/`.
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
