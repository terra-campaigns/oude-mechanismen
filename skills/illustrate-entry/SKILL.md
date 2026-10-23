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

Search public domain cultural archives matching the entity's specific nature:

1. **Formulate search queries**:
   - Do not restrict queries to one genre; tailor to the entity's nature (e.g. 18th-century automata for polibodies, 16th-century grotesque armour for combatants, antique botanical plates for toxic steppe flora, medieval bestiaries for mutants, Renaissance architectural ruins for forgotten serais, astronomical maps for star-clerics).
   - Search Wikimedia Commons, Rijksmuseum, Metropolitan Museum of Art Open Access, or Wellcome Collection.
2. **Verify licensing and resolution**:
   - Ensure the licence is Public Domain, CC0, CC BY, or CC BY-SA.
   - Prioritise high-resolution assets (minimum 1200px width).
3. **Gather metadata**:
   - Record author/artist, title, date, institution/source, licence type, and canonical URL for mandatory attribution.
4. **Offer selection**:
   - If multiple compelling candidates exist, present 2 to 4 options to the user with archive links and visual reasoning before filtering.

---

### Step 2: Apply Graphic-Novel Art Filter

Run the generic filter engine in `scripts/art_filter.py`:

```bash
python3 .agents/scripts/art_filter.py \
  --input "<path_or_url>" \
  --config ".agents/context/aesthetics.yml" \
  --output-dir "imgs/gallery" \
  --name-prefix "<entity_clean_name>" \
  --preset "all"
```

The engine applies:
- **Difference of Gaussians (DoG) comic inking**: Normalised edge-detection extracting organic black pen contours along rivets, joints, folds, and anatomical features.
- **Tonal remapping**: Linear colour interpolation using the campaign's custom gradient ramps.
- **Optical & texture effects**: Chromatic aberration channel splitting, risograph stipple grain, liquid light mirage wave warping, and diffraction lens flares.

---

### Step 3: Showcase Carousel & User Review

Present the filtered results to the user using an artifact carousel:

1. Copy the generated candidate images into `<appDataDir>/brain/<conversation-id>/`.
2. Create or update a showcase artifact using ````carousel syntax comparing each filtered preset alongside the original archival source.
3. Highlight open choices (e.g. which preset style fits best, or if flare positions/colours require fine-tuning).

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
