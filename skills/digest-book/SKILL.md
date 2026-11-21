---
name: digest-book
description: Turn one Tier 3 sourcebook PDF into a validated, hyperlinked Markdown knowledge wiki under `_gm-materials/digests/<source>/` using deterministic `oude digest --extract` slices plus harness-agnostic synthesis.
argument-hint: <pdf_path> [source slug]
---

# Digest Book

Convert a single external sourcebook PDF (Pillar 3: local disk outside Git and sync) into a semantic Markdown wiki of entity notes inside the git-ignored `_gm-materials/digests/<source>/` (Pillar 2), indexed into `.agents/context/references.json`.

## Guiding Principles

- **One book at a time**: always pass an explicit PDF path; never bulk-scan archives or infer paths from the vault.
- **Deterministic first**: `oude digest --extract` produces bounded, page-tagged slices plus a `manifest.json`. Synthesis (this skill) is the only model-driven step and stays harness-agnostic — no model names, SDKs, API keys, or dispatch commands belong in this file or in the engine.
- **Bounded context**: never read a raw PDF whole (commercial rulebooks exceed agent read limits). Iterate `manifest.json` slices in page order; each text slice is capped below common read limits and tagged with `--- Page N ---` markers.
- **Portable identifiers**: `source_pdf` in frontmatter and `references.json` records a relative path or basename, never a host-specific absolute path.
- **Setting-agnostic**: pull tone, vocabulary, and calibration only from the campaign vault's `## Campaign Specification` in `.agents/AGENTS.md`.

## Procedure

### 1. Extract bounded slices

```bash
oude digest --extract <pdf_path> [--format auto|text|pdf] [--out-dir <DIR>] \
  [--max-depth 1] [--chunk-pages 10] [--pdf-slice-pages 5] [--max-bytes 38000] [--min-chars-per-page 160]
```

- Default `--out-dir` is `<tempdir>/oude-extract/<slug>` (outside Git and sync); slices and `manifest.json` are cleared on each run.
- Read `<out-dir>/manifest.json`: iterate `slices` in `index` order, each with `title`, `start_page`/`end_page`, `format`, `path`, `image_count`, `has_large_images`, `large_image_pages`, and optional `auto_fallback_reason`.
- Slices with `auto_fallback_reason` are low-text-density or sparse image-heavy pages emitted as `.pdf` slices — read those with a vision/OCR-capable reader.
- **Visual & layout quality gate:** Dense two-column tabular pages can pass the density threshold with interleaved text, and prose-rich spreads can still conceal visual-only details that plain-text extraction drops without failing density checks or interleaving:
  - Prioritise any text slice where `has_large_images` is `true` (inspecting the listed `large_image_pages`), and spot-check rollable tables, statblocks, and floor/dungeon spreads for **interleaved columns**, **rasterised/outlined mini-maps and per-floor encounter tables baked into artwork**, **icon-keyed maps**, and **colour-coded tables** (where background colours carry speaker, faction, or severity attribution that text extraction strips).
  - For every slice or spread showing any of these defects, re-extract exactly those pages as `.pdf` into the same output directory (the manifest merges and replaces those pages' slices):
    ```bash
    oude digest --extract <pdf_path> --pages 209-211,261-263 --format pdf --out-dir <out-dir>
    ```
    Empirical note: on a 402-page dense two-column core rulebook, ~25% of text slices showed column interleaving; on a 64-page illustrated dungeon module, ~25% of pages had baked-in map artwork, encounter tables, or colour-coded attribution missing from clean text slices — plan for this quality-gate pass on both archetypes.

### 2. Synthesise the wiki into staging

Write notes under `<out-dir>/staged/<source>/` (never directly into the live digests tree):

- `_index.md` as the entry-point hub: premise, themes, clocks, chapter/page map, and annotated links into the category folders.
- Classify entities in priority order: `factions/` → `locations/` → `people/` → `creatures/` → `artefacts/` → `mechanics/` → `tables/` → `other/` (catch-all). A book may omit categories it does not need.
- Every note carries canonical YAML frontmatter:

  ```yaml
  ---
  source: <source slug>
  source_pdf: <portable relative path or basename>
  pages: "14-18"
  tier: 3
  entity_type: faction   # index | faction | location | person | creature | artefact | mechanic | table | other
  title: Harbour Guild
  tags: [faction, trade]
  related: ["../locations/docking_bay_01.md"]
  ---
  ```

- Body structure: `# <Title>` followed by a blank line, a 1–2 sentence summary, then `## Overview` (with `[p. X]` / `[pp. X–Y]` page citations), `## Key Details / Rules / Hazards` (statblocks and rollable tables as native Markdown tables), and `## Connections / See Also`.
- Links are standard relative Markdown links with a mandatory annotation: `[Harbour Guild](../factions/harbour_guild.md) — controls docking permits.` Wikilinks are not used: relative paths resolve in any renderer and give agents zero-hop paths.
- Hard invariants: a blank line immediately after every heading (`#`–`######`); only relative links that resolve inside the repository; `related:` entries resolve like body links; no `[[wikilinks]]`; `source_pdf` is a portable relative path or basename, never absolute; `pages:` and `[p. N]` / `[pp. N–M]` citations stay within the source book's page count when validated with `--manifest`.
- Soft sizing guidance: aim for roughly 30–120 lines per note; if a category folder would exceed 20 substantial notes, subdivide once (`<category>/<subgroup>/<note>.md`, subgroup of at least 4 notes, all subgroups listed in `_index.md`).

### 3. Validate, then replace atomically

```bash
oude digest --validate <out-dir>/staged/<source> --manifest <out-dir>/manifest.json
```

- Exit code must be `0`. Failures are reported as `file:line: <reason>` and must be fixed in staging, not after publishing. Non-fatal `[INFO]` stats (line counts, auto-fallback counts) and `[WARN]` orphan-note notices (notes unreachable from `_index.md`) never block.
- On pass, replace `_gm-materials/digests/<source>/` atomically: copy the validated `<out-dir>/staged/<source>/` tree to a temporary sibling directory **on the same filesystem outside `digests/`** (e.g. `_gm-materials/.staged-<source>.tmp` — keeping unfinished `.md` files out of `digests/` so `compile_references()` and sync do not index them prematurely, while staying on the same filesystem so an atomic swap works), then swap it into place.
- **Legacy flat-digest cleanup:** If upgrading an older vault from a legacy flat summary (`_gm-materials/digests/<source>.md`), remove the stale `<source>.md` file during the swap. `compile_references()` warns about and excludes such a stub (the nested `<source>/` wiki supersedes it in `.agents/context/references.json`), but `oude digest --validate` still checks every `*.md` under `digests/`, so the stale file must go.

### 4. Optional zero-context audit pass

- Before or alongside final indexing, you may run a read-only zero-context review comparing the staged (or published) wiki against `<out-dir>/manifest.json` and the extracted `.txt`/`.pdf` slices.
- Focus on non-structural fidelity defects that `oude digest --validate` cannot catch: misread map icons, omitted or compressed tactical rules, unattributed colour-coded tables, missing page citations, and British English consistency.
- Fix any confirmed discrepancies in staging (re-validating with `oude digest --validate`) before final swap.

### 5. Re-index and report

- Recompile the routing index with `oude digest` (no flags) so `.agents/context/references.json` picks up every nested note with collision-free relative `slug`s, portable `digest_path`/`source_pdf`, and the `source` field.
- Report: source book, slice counts by format, auto-fallback and visual quality-gate re-extraction counts, notes written per folder, validation result, any spot-checked dense or colour-coded tables, and whether a legacy flat digest was retired.
