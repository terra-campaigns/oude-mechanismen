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
  [--max-depth 1] [--chunk-pages 10] [--pdf-slice-pages 5] [--max-bytes 38000] [--min-chars-per-page 80]
```

- Default `--out-dir` is `<tempdir>/oude-extract/<slug>` (outside Git and sync); slices and `manifest.json` are cleared on each run.
- Read `<out-dir>/manifest.json`: iterate `slices` in `index` order, each with `title`, `start_page`/`end_page`, `format`, `path`, and optional `auto_fallback_reason`.
- Slices with `auto_fallback_reason` are low-text-density (scanned or image-heavy) pages emitted as `.pdf` slices — read those with a vision/OCR-capable reader. Dense two-column tabular pages can still pass the density threshold with interleaved text, so spot-check rollable tables and statblocks. For every slice that looks interleaved or unreadable, re-extract exactly those pages as `.pdf` into the same output directory (the manifest merges and replaces those pages' slices):
  ```bash
  oude digest --extract <pdf_path> --pages 209-211,261-263 --format pdf --out-dir <out-dir>
  ```
  Empirical note: on a 402-page dense two-column core rulebook, ~25% of text slices showed column interleaving, so plan for this quality-gate pass on such books.

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
- Hard invariants: a blank line immediately after every heading (`#`–`######`); only relative links that resolve inside the repository.
- Soft sizing guidance: aim for roughly 30–120 lines per note; if a category folder would exceed 20 substantial notes, subdivide once (`<category>/<subgroup>/<note>.md`, subgroup of at least 4 notes, all subgroups listed in `_index.md`).

### 3. Validate, then replace atomically

```bash
oude digest --validate <out-dir>/staged/<source> --manifest <out-dir>/manifest.json
```

- Exit code must be `0`. Failures are reported as `file:line: <reason>` and must be fixed in staging, not after publishing. Non-fatal `[INFO]` stats (line counts, auto-fallback counts) never block.
- On pass, replace `_gm-materials/digests/<source>/` atomically: copy the validated `<out-dir>/staged/<source>/` tree to a temporary sibling directory **on the same filesystem** as `_gm-materials/digests/` (e.g. `_gm-materials/digests/.staged-<source>.tmp` — an atomic rename/`os.replace` never works across filesystems, and `<out-dir>` defaults to the temp dir), then swap it into place, so an interrupted run never exposes a partial tree over peer-to-peer sync.

### 4. Re-index and report

- Recompile the routing index with `oude digest` (no flags) so `.agents/context/references.json` picks up every nested note with collision-free relative `slug`s, portable `digest_path`/`source_pdf`, and the `source` field.
- Report: source book, slice counts by format, auto-fallback count, notes written per folder, validation result, and any spot-checked dense tables.
