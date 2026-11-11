---
name: illustrate-entry
description: Find open-source archival cultural imagery (no AI) for a campaign entity or accept an image input, apply a campaign-tailored graphic-novel art filter, and integrate into the entry with full attribution.
argument-hint: path to target markdown file, entity name, or direct image file/URL
---

# Illustrate Entry

Acquire, style, and integrate visual artwork for a campaign entry using genuine open-source archival cultural materials and campaign-defined aesthetic filters. Never generate or use artificial intelligence imagery.

## Philosophy & Core Invariants

1. **Strictly NO Artificial Intelligence Imagery**: All visual assets must be genuine historical artefacts, paintings, engravings, sketches, technical diagrams, archaeological finds, or period photography from public domain or open-access cultural collections.
2. **Campaign-Driven Aesthetics**: The visual identity (palettes, inking weights, grain, optical distortions, and lens flares) is defined by the target campaign repository via `.agents/context/aesthetics.yml` and `.agents/AGENTS.md`. The skill provides the generic image processing engine.
3. **Traceable Attribution**: Every integrated image must include unambiguous provenance in the page's YAML `footer_content:` citing the original creator, work title, cultural institution, and licence.

---

## Workflow Steps

### Step 0: Ingestion & Lore Analysis

Determine the target entity note and input source:

1. **Identify the target note**: Read the target file in `directory/`, `campaigns/`, `creatures/`, or locate it using `.agents/context/catalog.json`.
2. **Read campaign aesthetic configuration**:
   - Check `.agents/context/aesthetics.yml` for active presets, colour ramps, and effect parameters.
   - Read `.agents/AGENTS.md` (specifically `## Aesthetics` and `## Style & Tone`) for the visual tone and reference artists.
3. **Determine input mode**:
   - **Mode A (Image Provided)**: The user provided a local file path (`.jpg`, `.png`, `.webp`) or a direct image URL. Proceed directly to Step 2.
   - **Mode B (Autonomous Archival Search)**: No image was supplied. Extract the entity's role, visual hooks, culture, materials, and connected factions to formulate search parameters in Step 1.

---

### Step 1: Open-Source Archival Discovery (Mode B Only)

Search public domain cultural archives matching the entity's specific nature using the automated harvester or manual query:

1. **Automated Archival Harvesting (Recommended)**:
   Run the Archival Scriptorium harvester via the `oude` CLI:
   ```bash
   oude harvest --entity "path/to/note.md" --max-candidates 3
   ```
   *(Or direct script fallback: `python3 scripts/harvest_archival.py --entity "path/to/note.md" --max-candidates 3`).*
   The engine autonomously:
   - Derives 3 pre-20th-century historical search terms via local Ollama (`qwen2.5:14b`).
   - Queries keyless open collections (Wikimedia Commons Action API and The Met Museum Open Access API).
   - Verifies machine-readable CC0 / Public Domain licensing and rejects generative AI markers.
   - Downloads top candidates and renders multi-preset styled variants to `.agents/tmp/`.
   - Skip to **Step 3** to showcase the resulting candidates to the user.

2. **Manual Discovery Fallback**:
   If running offline without access to museum APIs:
   - Formulate search queries tailored to the entity's nature (e.g. 18th-century automata, botanical plates, Renaissance ruins).
   - Search public domain archives manually (Wikimedia Commons, Met Museum, Wellcome Collection).
   - Verify licensing (CC0, Public Domain, CC BY) and resolution (minimum 800px width).
   - Proceed to **Step 2** with the acquired image.

---

### Step 2: Apply Graphic-Novel Art Filter

Run the graphic-novel filter engine via `oude filter`:

```bash
oude filter \
  --input "<path_or_url>" \
  --config ".agents/context/aesthetics.yml" \
  --output-dir "imgs/gallery" \
  --name-prefix "<entity_clean_name>" \
  --preset "all"
```

*(Or direct script fallback: `python3 scripts/art_filter.py ...`).*

The engine applies:
- **Difference of Gaussians (DoG) comic inking & luminous edge glow**: Normalised edge-detection extracting organic black pen contours along rivets, joints, folds, and anatomical features, or additive neon emission tracing over dark bulkheads.
- **Tonal remapping & Sabattier solarisation**: Linear colour interpolation using the campaign's custom gradient ramps, with optional tone-folding inversion for medical tomographic scans (`--solarise`).
- **Optical & texture effects**: Polar-coordinate singularity vortex pinching (`--polar-vortex`), chromatic aberration channel splitting, risograph stipple grain, liquid light mirage wave warping, and diffraction lens flares.

---

### Step 3: Curated Options Showcase & User Selection

Present the filtered results directly to the user in chat:

1. **Copy generated assets to artifacts**:
   Copy the generated candidate images into `<appDataDir>/brain/<conversation-id>/` for artifact viewing.
2. **Present options in chat**:
   Display 2 to 4 styled candidate variants directly in chat (with high-resolution markdown image links or carousel, preset names, and full archival provenance).
3. **Gather user decision**:
   The user selects their preferred look (e.g. "Option 2 in Nostromo Grime") or requests adjustments. Capture the winning selection for Step 4.

---

### Step 4: Integration & Attribution

Once the user selects their preferred style:

1. **Confirm the winning image**:
   Ensure the chosen file is stored at `imgs/gallery/<clean_name>.jpg`.
2. **Wire into front matter**:
   Update `images:` in the target markdown file with the relative path:
   ```yaml
   images: 
   - ../../imgs/gallery/<clean_name>.jpg
   ```
3. **Add footer attribution**:
   Set `footer_content:` in the target markdown front matter with clean HTML:
   ```yaml
   footer_content: Image adapted from <a href="<CANONICAL_SOURCE_URL>" target="_blank"><WORK_TITLE> (<YEAR>)</a>, <INSTITUTION> (photo by <CREATOR>, <LICENCE>).
   ```
4. **Housekeeping**:
   - Delete temporary/discarded candidate variants from `imgs/gallery/`.
   - Leave only the selected artwork in the working tree.
5. **Verify site build**:
   Run `bundle exec jekyll build` to ensure data extracts refresh and the page renders without errors.

---

## Operational Checklist for New Campaign Artwork

Before selecting and integrating filtered archival artwork into any campaign entry:

- [ ] **Establish Archival Provenance**: Confirm the source image is a genuine historical artefact, museum specimen, technical plate, patent illustration, or period photograph (strictly no AI generation). Verify public domain (CC0, CC BY, or CC BY-SA) status and record the canonical attribution URL.
- [ ] **Establish Subject Grounding**: Does the image align with the campaign's visual motifs, themes, and technology level specified in `.agents/AGENTS.md`? Avoid generic or incongruous tropes.
- [ ] **Enforce Palette Purity**: Constrain the colour ramp to established campaign presets in `.agents/context/aesthetics.yml`. Do not mix arbitrary colours outside the defined palette.
- [ ] **Verify Line & Edge Treatment**: Ensure edges exhibit either organic ink contours (DoG inking) or luminous neon discharge tracing. Avoid flat digital fills.
- [ ] **Apply Analogue Texture**: Confirm film grain, scanlines, or stipple dispersion are present to prevent sterile digital gradients.
- [ ] **Verify Attribution Integrity**: Check that YAML `footer_content:` contains full canonical attribution linking to the contributing cultural institution or open archive.
