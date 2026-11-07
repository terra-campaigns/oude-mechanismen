# Tasks

## Incoming Feedback / Inbox

### [SEMI] Contextual Narrative Anchoring for Episode Links (Replace Mechanical Parentheticals)

- **Timestamp:** 2026-11-07
- **Origin:** `charged` on `efsalvarenga/session-012-escaped-biochimera`
- **Component:** `skills/scribe-session/SKILL.md` (Pass 3 & Section 4.3), `skills/add-chapter/SKILL.md`, `skills/add-character/SKILL.md`, `skills/lint-wiki/SKILL.md`
- **Operational Context:** Drafting and updating campaign chronicle prose and directory cross-links referencing previous session episodes.
- **Specific Friction & Defect:** Agents and prose generators frequently introduce mechanical, bibliographical parenthetical citations when referencing past sessions (e.g. `([ep_010](ep_010.md))` or `([ep_012](../../campaigns/UVG24XX/ep_012.md))`). This fractures narrative immersion and reads like an academic paper rather than living setting prose. The human developer established the canon invariant: *"When you mention episodes, make the link text the reason to mention it"* (e.g. `[promised Doda mate](ep_010.md)` rather than `promised Doda mate ([ep_010](ep_010.md))`).
- **Actionable Remediation:**
  1. Update `skills/scribe-session/SKILL.md` under Section 4.3 (Chapter Body & Cadence Invariants) and `skills/add-chapter/SKILL.md`: add an explicit directive on episode cross-linking: "Never append mechanical episode tags like `([ep_010](ep_010.md))` or `([ep_012](ep_012.md))`. Always wrap the anchor link directly around the narrative event, deal, or concept that justifies mentioning that episode (e.g. `[the promised Doda mate](ep_010.md)`, `[the failed assassination contract](ep_011.md)`)."
  2. Apply the same contextual linking directive to `skills/add-character/SKILL.md` for historical biography references.
  3. Add a check in `lint-wiki` (or a pre-commit lint script) to flag naked parenthetical episode patterns `\(\[ep_[0-9]+\]\(.*?\)\)` as candidates for narrative anchor refactoring.
- **Status:** Open

### [SEMI] Automated Archival Image Sourcing, Modification & Review Panel for Unillustrated Wiki Entries

- **Timestamp:** 2026-11-01 (Evaluated & Closed: 2026-11-05)
- **Origin:** `hostile` on `oudemechanismen`
- **Component:** `skills/illustrate-entry`, `skills/lint-wiki`, `scripts/art_filter.py`, `scripts/audit_coverage.py`
- **Operational Context:** Populating missing visual assets across campaign wiki notes (places, NPCs, factions, items, and creatures) without AI hallucination, preserving prose and aesthetic tone.
- **Specific Friction & Defect:** Illustrating entries across a campaign vault currently requires an ad-hoc, manual, one-by-one workflow. A proposal was made to build an automated batch crawler and interactive HTML review panel / studio with real-time sliders and manifest syncing.
- **Resolution & Architectural Ruling (Occam's Razor):**
  1. *Standalone Studio Discarded & Pruned:* An interactive review studio / web app was mocked up and evaluated. It was discarded as over-engineered, cluttered, and unnecessary. All legacy studio plumbing (`resources/filter_studio.html`, generator block in `art_filter.py`, Step 3 in `SKILL.md`, and docs in `AGENTS.md` / `README.md`) was pruned in branch `efsalvarenga/prune-filter-studio`. The conversational, chat-native pair-programming workflow (presenting 3–5 candidate options directly in chat, picking an option, and letting the agent wire up the asset) is faster, cleaner, and superior.
  2. *Fallback Badges Are Canonical:* Entries without custom illustrations rely on geometric fallback badges (`imgs/badges/people.png`, etc.). These are first-class citizens of the engine architecture. Having no custom image is completely valid and must **never** be flagged as a lint failure or build warning.
  3. *Workflow Invariant:* `skills/illustrate-entry` remains 100% chat-native.
- **Status:** Closed (Evaluated & Discarded)

### [AUTO] Delegate Wiki Linting (`lint-wiki`) to Local On-Device Models

- **Timestamp:** 2026-11-01
- **Origin:** `artifice` on `agent/ecosystem-governance-and-coordination`
- **Component:** `skills/lint-wiki/SKILL.md`, `scripts/`
- **Operational Context:** Structural auditing and diagnostic reporting across narrative campaign lore and static site notes.
- **Specific Friction & Defect:** Running `lint-wiki` across dozens or hundreds of vault notes currently consumes frontier cloud model quota. Because this audit is advisory and non-critical (checking for dead links, orphan pages, stubs, image references, and catalogue health), burning cloud API limits on routine vault sweeps is inefficient and risks quota exhaustion during active coding sessions.
- **Actionable Remediation:**
  1. Update `skills/lint-wiki/SKILL.md` to target local Ollama model (`qwen2.5:14b`) for contextual summarisation and diagnostic evaluation.
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

### [AUTO] Add Scribe Session Runner Template to sync.sh Manifest

- **Timestamp:** 2026-11-06
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `sync.sh`, `templates/runners/scribe_session.py.template`
- **Operational Context:** Synchronising the campaign engine with downstream vaults and bootstrapping runner scripts in `.agents/scripts/`.
- **Specific Friction & Defect:** In v0.2.0, `oude-mechanismen` introduced the decomposed session scribing engine (`scripts/scribe_session.py`). Downstream vault `charged` had to manually author a local runner wrapper in `.agents/scripts/scribe_session.py` (commit `8549b74`) because `templates/runners/scribe_session.py.template` does not exist in `oude-mechanismen` and `sync.sh` does not include it in its `MANAGED_FILES` array. Consequently, running `sync.sh` on fresh or existing campaign vaults does not provision or synchronise the `scribe_session.py` runner wrapper.
- **Actionable Remediation:**
  1. Author `templates/runners/scribe_session.py.template` in `oude-mechanismen` matching the standard runner wrapper pattern.
  2. Add `'templates/runners/scribe_session.py.template:.agents/scripts/scribe_session.py:true'` to `MANAGED_FILES` in `sync.sh`.
  3. Ensure `sync.sh` test suites and documentation reflect 15 managed files.
- **Status:** Open

### [AUTO] Remove all-content.md and llm_content.rb from Engine and sync.sh Manifest

- **Timestamp:** 2026-11-06
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `sync.sh`, `jekyll/all-content.md`, `jekyll/_plugins/llm_content.rb`, `skills/lint-wiki/SKILL.md`, `templates/AGENTS.md.template`
- **Operational Context:** Evaluating repository cleanup, static site context dumps, and engine synchronisation across campaign vaults.
- **Specific Friction & Defect:** `all-content.md` was originally designed to render a monolithic plaintext/HTML dump at `/all-content.html` for single-shot LLM ingestion via `_plugins/llm_content.rb`. However, campaign vaults now rely on progressive low-token indexed retrieval (`catalog.json`, `references.json`, `lookup-context` skill, and focused line-range reads) rather than bulk context dumps. The presence of `all-content.md` in `sync.sh` (`MANAGED_FILES`) forces every downstream vault to maintain this file, triggers `sync.sh --check` drift failures if deleted locally, and adds unnecessary template overhead to every Jekyll build.
- **Actionable Remediation:**
  1. Remove `'jekyll/all-content.md:all-content.md:false'` and `'jekyll/_plugins/llm_content.rb:_plugins/llm_content.rb:false'` from `MANAGED_FILES` in `sync.sh`.
  2. Delete `jekyll/all-content.md` and `jekyll/_plugins/llm_content.rb` from `oude-mechanismen`.
  3. Add a cleanup migration in `sync.sh` to remove deprecated `all-content.md` and `_plugins/llm_content.rb` from downstream campaign vaults.
  4. Remove references to `all-content.md` from `templates/AGENTS.md.template`, `skills/lint-wiki/SKILL.md`, and `oude-mechanismen/AGENTS.md`.
  5. Update `sync.sh` test suites and documentation to reflect the updated managed file count.
- **Status:** Open

### [SEMI] scribe-session: GM recap anchor, recap-aware extraction, and name/ledger validation

- **Timestamp:** 2026-11-06
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `scribe-session` (Steps 1-3), `scripts/scribe_session.py` (Pass 2A/2B), `prep-session` (prep artefact hand-off)
- **Operational Context:** Processing `2026-11-06_012_rec.mov` (47.5 minutes of local extraction) for the charged UVG+24XX campaign. The GM's prep note and attendance had changed shortly before play (a player joined last minute).
- **Specific Friction & Defect:**
  1. Pass 2A treated the previous session's recap, spoken at the start of play, as events of the current session (Beat 1 re-narrated the ep_011 embassy audience).
  2. Whisper phonetic drift survived into the extraction (`Yakum` for Iacum, `Kerr` for Kur, `Perla` for Settler, `Last Sarai`, `Ignore Tower`, `Wai folk`), despite the glossary prompt.
  3. Pass 2A invented or compressed chronology (a "week of market research and carousing" for a one-day session) and copied existing `decisions.md` rulings verbatim into the candidate rulings section.
  4. Passes 2A and 2B contradicted each other on the key outcome (who killed the antagonist), and neither mentioned events present in the prep (foreman's death, armour).
  5. No attendance input exists, so ledger entries could be attributed to an absent character, and the GM could not tell which items were unreliable.
- **Actionable Remediation:**
  1. Add an optional `<slug>_gm_recap.md` input (8-12 bullets: attendance, ordered events, outcomes, cash and injuries). Treat it as authoritative; use the extraction passes only for atmosphere and quotes consistent with it.
  2. Feed `<slug>_prep.md` and the attendance list into Pass 2A, and instruct it to ignore the opening recap segment and to flag, never invent, anything not in the transcript.
  3. Add a post-extraction validator that fuzzy-matches names against the glossary and reports unknown names, absent characters in the ledger, and candidate rulings that duplicate `decisions.md`.
  4. Add a Pass 2A/2B contradiction check that surfaces conflicting outcomes as `[UNVERIFIED]` items instead of silently choosing one.
  5. Add a cheap `--dry-run` mode (first 10 minutes only) to check name recognition before committing to the full 47-minute run.
- **Status:** Open

### [SEMI] scribe-session: chunked extraction and link-graph-prioritised glossary (addendum to the GM recap anchor item above)

- **Timestamp:** 2026-11-07
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `scripts/scribe_session.py` (glossary compilation, lines ~316 and ~383; Pass 2A/2B prompts), `.agents/context/catalog.json` link data
- **Operational Context:** Diagnosing poor Pass 2A/2B output for `2026-11-06_012` (recording 6,462 s, transcript ~14,800 words, 47.5 minutes of local processing).
- **Specific Friction & Defect:**
  1. The whole transcript is sent to the local model in one prompt (`num_ctx` 32768, ~20k tokens of transcript), which encourages lost-in-the-middle compression and invented chronology.
  2. The glossary is hard-truncated with `context.get('glossary', '')[:4000]` while the compiled glossary is ~19,000 characters. It is ordered alphabetically, so names late in the list (for example Settler at ~5,400 characters) never reach the model.
- **Actionable Remediation:**
  1. Split the transcript into overlapping 15-20 minute windows, extract per window, then merge and de-duplicate in a final pass.
  2. Replace the hard truncation with a ranked glossary budget. Rank entities by link distance (n hops) in the wiki link graph, starting from the attending characters, the session location and the prep note's entities. Fill the budget with hop-0 entities, then hop-1, then hop-2, and drop the rest.
  3. Weight by recency (appearance in the last 3 chapters) and always include the full attendance list.
  4. Test with a fixture: the glossary budget must contain every attending PC and every entity named in the prep note.
- **Status:** Open

### [SEMI] scribe-session: rolling session add-on glossary between extraction chunks (addendum to the chunked extraction item)

- **Timestamp:** 2026-11-07
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `scripts/scribe_session.py` (Pass 2A/2B orchestration)
- **Operational Context:** GM suggestion while diagnosing the `2026-11-06_012` extraction: summarise the first half of the transcript, build an add-on glossary from it, and feed it with the normal glossary to the second half.
- **Specific Friction & Defect:** Session-specific entities (new NPCs, spellings the table settled on, aliases) are only learnt after they appear, so later passes cannot benefit from earlier ones. A naive add-on glossary can also propagate hallucinated names from the first half into the second.
- **Actionable Remediation:**
  1. Generalise to N rolling chunks: each chunk's extraction emits a small add-on glossary (new proper nouns, alias map such as `Yakum -> Iacum`, running state) passed to the next chunk.
  2. Keep the add-on separate from the canonical glossary and label it `unverified`. Admit a term only if it appears at least twice in the transcript or fuzzy-matches a canonical entity.
  3. Apply the alias map as a final normalisation pass over every output file.
  4. Optionally re-run Whisper on the poorly recognised segments with the add-on as its prompt, since Whisper only sees the pre-built glossary today.
  5. Surface the add-on glossary to the GM for a quick confirm or reject before Pass 2C.
- **Status:** Open

### [SEMI] Investigate the value of maintaining `route_graph.json`

- **Timestamp:** 2026-11-07
- **Origin:** `charged` on `oudemechanismen`
- **Component:** `templates/route_graph.json.template`, `.agents/context/route_graph.json`, `scripts/audit_coverage.py` (`build_adjacency`, `get_directory_status`), `sync.sh` (scaffold line ~121)
- **Operational Context:** After session 012, the GM recorded new places (Pit of Mould, 3 days west of the Last Serai; Qasso Mine, 5 days north) and asked whether the route graph was the right place for them.
- **Specific Friction & Defect:**
  1. The vault already has `catalog.json` (entity index) and a generated link map covering every wiki link. The GM questions what value `route_graph.json` adds on top of them.
  2. Its only visible consumer is `audit_coverage.py`, which reads `weeks`, `direction` and `terrain` per connection. It is not read by `lookup-context` or `prep-session`.
  3. The schema is built for numbered UVG stations and whole weeks. Adding ad-hoc places required extra fields (`days`, fractional `weeks`, `source`, `note`), unclassified `category` and `terrain: unknown`, and a null `dir_folder` for a place with no folder of its own.
  4. Distances and bearings now also live in directory page prose (for example `PitOfMould.md`, `QassoMine.md`) and nowhere is the duplication reconciled.
- **Actionable Remediation:**
  1. Investigate whether any skill or script besides `audit_coverage.py` consumes the graph, and what decisions it informs.
  2. Decide between: (a) retire the file and the template and move distance and bearing into front matter fields on directory pages that the catalogue extracts, (b) keep it but generate it from directory page front matter so there is a single source, or (c) keep it as a hand-maintained map with a documented schema covering days, unnumbered places and unknown terrain.
  3. If kept, give `prep-session` Step 5 (routes) and `lookup-context` a reason to read it.
  4. If retired, remove it from `sync.sh` scaffolding and update `AGENTS.md`.
- **Status:** Open
