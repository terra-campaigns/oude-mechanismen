# Goldfish Review: The Archival Scriptorium (Non-AI Asset Harvester)

**Review Target:** [`docs/designs/001_archival_scriptorium.md`](file:///Users/efsa/.gemini/antigravity/worktrees/oude-mechanismen/next_steps_roadmap/docs/designs/001_archival_scriptorium.md)  
**Reviewer:** Zero-Context Goldfish Reviewer Agent  
**Date:** 2026-11-07  
**Verdict:** Approved  

---

## 1. Executive Summary

This Round 2 Goldfish review evaluates the revised technical specification for **The Archival Scriptorium** ([`docs/designs/001_archival_scriptorium.md`](file:///Users/efsa/.gemini/antigravity/worktrees/oude-mechanismen/next_steps_roadmap/docs/designs/001_archival_scriptorium.md)) following the resolution of all eleven adversarial probes (PROBE-01 to PROBE-11) and eight required revisions identified in Round 1.

The specification provides an exemplary, fully deterministic, and contract-hardened architectural blueprint. The revised design rigorously eliminates all front-matter path resolution hazards against Jekyll's `_plugins/data_extractor.rb`, switches attribution markup to clean HTML hyperlinks compatible with theme layouts, normalises machine-readable licensing and anti-AI blacklist detection against real-world museum API payloads, bounds network queries against rate-limiting hazards, adapts the candidate data model for multi-preset graphic-novel rendering, establishes downstream runner packaging via `sync.sh`, ensures workspace disk hygiene via `.gitignore` declarations, and enforces pure-function decomposition across all parsing and transformation logic for isolated, deterministic unit testing.

Zero logic contradictions, unbounded types, or state-desynchronisation hazards remain. The specification is approved for autonomous Wave 2 implementation handoff.

---

## 2. Invariant & Edge-Case Probing (Round 2 Verification)

| ID | Area / Component | Invariant / Failure Mode Probed | Round 2 Resolution Status |
| :--- | :--- | :--- | :--- |
| PROBE-01 | State Mutation / Front Matter | Note-relative image path calculation breaks Jekyll gallery backlink resolution in `_plugins/data_extractor.rb`. | **Resolved.** Specification mandates directory-depth relative pathing (e.g. `../../imgs/gallery/<slug>.jpg`), ensuring 100% catalog backlink indexing. |
| PROBE-02 | Template Integration | `footer_content:` specified in Markdown syntax, but Jekyll layout renders raw HTML without `markdownify`. | **Resolved.** Standardised on valid HTML hyperlink format (`<a href="..." target="_blank" rel="noopener noreferrer">...</a>`). |
| PROBE-03 | Invariant Check / Licensing | Exact string matching on `LicenseShortName` rejects legitimate Wikimedia Commons licences (`CC BY`, `PD-Art`). | **Resolved.** Evaluates dictionary `extmetadata.LicenseShortName.value` against normalised regex `^(cc0\|cc[ -]by\|pd\|public domain)`. |
| PROBE-04 | Network & Performance | Unbounded sequential `/objects/{id}` requests in The Met API creates an N+1 request storm and rate-limiting risk. | **Resolved.** Inspection bounded to maximum 6 object IDs per search, requiring non-empty `primaryImageSmall`, with a 5.0s per-request timeout. |
| PROBE-05 | State Mutation / Front Matter | Missing non-destructive front-matter patch contract risks overwriting existing gallery arrays or Obsidian metadata. | **Resolved.** Pure function `patch_note_frontmatter` prepends to `images:` list and preserves surrounding comments, Dataview blocks, and YAML fields. |
| PROBE-06 | Repository Architecture | Omission of downstream runner templates (`templates/runners/`) and `sync.sh` distribution protocol. | **Resolved.** Architectural deliverables added for `templates/runners/harvest_archival.py.template`, `sync.sh` `MANAGED_FILES`, and `illustrate-entry`. |
| PROBE-07 | Anti-AI Provenance Invariant | Brittleness of AI category filtering against common subcategories, case variations, and description tags. | **Resolved.** Robust case-insensitive lexical scanner `is_ai_provenance` scans categories and description text against AI markers. |
| PROBE-08 | Data Schema Completeness | `ArchivalCandidate.styled_file_path` is a single path, conflicting with multi-preset generation in `art_filter.py`. | **Resolved.** Updated to `styled_variants: Dict[str, Path] = field(default_factory=dict)` mapping preset names to rendered JPG file paths. |
| PROBE-09 | Workspace Hygiene | Temporary downloads in `.agents/tmp/` risk dirtying Git trees due to absence of `.gitignore` declaration. | **Resolved.** Added `.agents/tmp/` to `.gitignore` specification; automatic unselected temp file purge added upon human selection or cancellation. |
| PROBE-10 | API Governance | Missing mandatory `User-Agent` compliance for Wikimedia Commons Action API. | **Resolved.** Explicit compliant `User-Agent` string declared in Section 5.1 Step 2 per Wikimedia Foundation policy. |
| PROBE-11 | Resolution & Testability | Lack of minimum image resolution bound and lack of pure-function architectural decomposition. | **Resolved.** Mandated image width $\ge 800\text{px}$ and decomposed script into 8 pure functions with explicit deterministic unit test contracts. |

---

## 3. Detailed Verification of Revisions

### 3.1 Data Schema Completeness & Multi-Preset Styling

* **Multi-Preset Representation (PROBE-08):** In Section 3.1, `ArchivalCandidate` now defines `styled_variants: Dict[str, Path] = field(default_factory=dict)`. This allows `art_filter.py` to generate and track all active vault aesthetic presets (such as `classic_graphic_novel`, `ligne_claire`, and `moebius_desert`) simultaneously, enabling the user to evaluate multiple palette variants directly within the chat presentation card.
* **Deterministic Object Mapping:** The schema cleanly decouples raw downloads from styled assets, capturing accession titles, creators, creation dates, institutions, source permalinks, and verified public domain flags without ambiguous fields.

### 3.2 Path Contracts & Front-Matter Mutation

* **Relative Path Calculation for Jekyll Compatibility (PROBE-01):** Section 3.2 and Section 5.1 Step 5 rigorously enforce directory-depth relative pathing. For instance, an entry at `directory/Atles/IronPot.md` calculates `../../imgs/gallery/iron-pot.jpg`. When processed by `_plugins/data_extractor.rb`:
  ```ruby
  dir = File.dirname(file_path) # "directory/Atles"
  resolved_path = Pathname.new(dir).join(clean_target).cleanpath.to_s
  # Correctly evaluates to "imgs/gallery/iron-pot.jpg"
  ```
  This guarantees that `all_gallery_images.key?(resolved_path)` resolves to `true`, ensuring complete, bidirectional backlink compilation in `.agents/context/catalog.json`.
* **Clean HTML Attribution in `footer_content:` (PROBE-02):** Section 3.2 and Section 5.1 Step 5 specify raw HTML attribution hyperlinks (`<a href="..." target="_blank" rel="noopener noreferrer">...</a>`). This matches the unparsed `{{ page.footer_content }}` tag in `_includes/footer_custom.html`, preventing raw Markdown syntax from rendering unparsed on published Jekyll pages.
* **Surgical Front-Matter Patching (PROBE-05):** Section 5.2 defines `patch_note_frontmatter(content: str, rel_image_path: str, footer_html: str) -> str`. The specification mandates prepending new images to existing arrays without clobbering existing gallery entries, preserving YAML comments, and leaving Obsidian Dataview blocks intact.

### 3.3 Rights Verification & Anti-AI Provenance Robustness

* **Resilient Normalisation of Licences (PROBE-03):** Section 5.1 Step 3 and Section 5.2 implement normalised regular expression matching against `^(cc0|cc[ -]by|pd|public domain)`. The parser explicitly extracts the `value` field from Wikimedia's dictionary structure and gracefully accommodates whitespace variations (`CC BY 4.0`), historic public domain mark conventions (`PD-Art`, `PD-old-100`, `PD-US`), and The Met Museum's `isPublicDomain: bool` flag.
* **Bounded API Queries & Rate-Limiting Protection (PROBE-04):** Section 5.1 Step 2 strictly bounds Met Museum search results to a maximum of 6 candidate object IDs per query, filters for objects containing non-empty `primaryImageSmall` (or `primaryImage`), and enforces a 5.0-second network timeout per request.
* **Robust Anti-AI Lexical Scanner (PROBE-07):** Invariant 1 and Section 5.2 mandate `is_ai_provenance`, performing case-insensitive lexical matching across category titles and description texts for `ai-generated`, `midjourney`, `stable diffusion`, `dall-e`, and `generative ai`.

### 3.4 Downstream Distribution, Governance & Hygiene

* **Engine-Vault Packaging via `sync.sh` (PROBE-06):** Section 5.3 formalises the upstream packaging requirements:
  1. Authoring `templates/runners/harvest_archival.py.template` with virtual environment discovery.
  2. Registering `.agents/scripts/harvest_archival.py` in `sync.sh` (`MANAGED_FILES`).
  3. Updating `skills/illustrate-entry/SKILL.md` to reference the automated CLI and presentation workflow.
* **Workspace Disk Hygiene (PROBE-09):** Invariant 7, Section 5.1 Step 5, and Section 5.3 require adding `.agents/tmp/` to `.gitignore` and mandate an automatic purge of unselected candidate downloads upon selection or cancellation, preventing binary churn in Git.
* **Wikimedia User-Agent Compliance (PROBE-10):** Section 5.1 Step 2 mandates a compliant User-Agent header (`OudeMechanismenHarvester/0.3.0 (...)`), preventing HTTP 403 / 429 rejections from Wikimedia infrastructure.

### 3.5 Testability & Pure-Function Decomposition

* **Decomposed Architecture (PROBE-11):** Section 5.2 decomposes the harvester into eight isolated pure functions (`parse_met_object_payload`, `parse_wikimedia_imageinfo`, `validate_licence_string`, `is_ai_provenance`, `calculate_relative_image_path`, `format_footer_html`, `generate_deterministic_fallback_queries`, and `patch_note_frontmatter`).
* **Deterministic Unit Testing:** Section 7 defines comprehensive unit test suites in `tests/test_harvest_archival.py` covering mock JSON payloads, licence string matching, AI keyword rejection, relative path resolution across directory hierarchies, HTML generation, and non-destructive front-matter updates without network dependencies.

---

## 4. Contract Conformance & Section Alignment

All sections conform strictly to the standard EGM design specification template (`references/design-spec-template.md`):
- Section 1: Overview & Objectives
- Section 2: Domain Framing & User/System Experience
- Section 3: State Schema & Data Models
- Section 4: Invariants & Rules
- Section 5: Execution & State Mutation Logic (including 5.3 Downstream Vault Distribution)
- Section 6: Edge Cases & Failure Modes
- Section 7: Verification & Automated Test Strategy
- Section 8: Goldfish Review Gates

Mechanical contract validation via `python3 scripts/validate_egm.py` confirms complete section adherence and approved status with zero validation errors.

---

## 5. Recommendation & Final Sign-Off

* **Verdict:** Approved  
* **Readiness:** The specification is fully mature, architecturally sound, and resistant to edge-case failures. It is ready for immediate handoff to `code-author` ("The Craftsman") for Wave 2 implementation under the contract-first TDD cycle.
