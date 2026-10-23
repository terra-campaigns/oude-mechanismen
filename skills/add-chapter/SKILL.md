---
name: add-chapter
description: Create and integrate a new campaign chapter or session log file with canonical YAML front matter, navigation ordering, region metadata, directory cross-links, and setting voice.
argument-hint: session notes, title, or episode brief (optional)
---

# Add Chapter

Create and integrate a new chapter or session log into the campaign chronicles.

## 1. Intake & Clarification

If the user's prompt does not supply all required details, ask clarifying questions before writing:

1. **Campaign**: Which campaign does this chapter belong to?
   - Check available subfolders in `campaigns/` (or check `Default Campaign Subfolder` in `.agents/AGENTS.md`).
2. **Episode Number**: Automatically determine the next episode number by checking existing files in `campaigns/<Campaign>/` (e.g. `ep_010.md` -> `ep_011.md`).
3. **Chapter Title**: An evocative title matching the episode's central dilemma, creature, hazard, or weird event.
4. **In-Universe Date (`nav_order`)**: Date of the session in `YYYY-MM-DD` format (e.g. `3025-08-19`). Check the previous episode's date to maintain chronological order.
5. **Region & Location**: Where did the session take place? (e.g. station sector, trail station, landmark).
6. **Hub / Base**: Which hub or base index should be linked in the comment block? (Check `Campaign Hub Page` in `.agents/AGENTS.md`).
7. **Session Notes**: Raw player actions, discoveries, trades, NPC interactions, debts, and mechanical consequences.

## 2. Entity Resolution & Cross-Linking

Before drafting the chapter prose:

1. **Identify mentioned entities**: Scan the session notes for all PCs, NPCs, factions, locations, and creatures.
2. **Search Directory**: Consult `.agents/context/catalog.json` (or use `rg`) to locate the exact filenames and paths in `directory/`.
3. **Format relative links**: Ensure every entity is linked on its first significant mention using relative paths (e.g. `[Kur (Barista)](../../directory/Atles/Barista.md)`).
4. **Clarify new connections**: If a new relationship between characters or factions emerges during the session, prompt the user for the specific relationship dynamic and whether to document it bidirectionally.

## 3. Template & Front Matter

Create the file as `campaigns/<Campaign>/ep_<NNN>.md`.

### Front Matter Specification

```yaml
---
layout: default
type: session
nav_exclude: false

parent: <Exact title of the campaign index>
title: <Chapter Title>
region: <Region or Location Name>
nav_order: <YYYY-MM-DD>
narration: 
footer_content: 

images:

---
```

> [!NOTE]
> - `type:` must be `session`.
> - `nav_order:` must be the in-universe date string (`YYYY-MM-DD`). Jekyll uses this to format the date in the chapter header and order episodes chronologically.
> - `narration:` is an optional list of character names if dedicated individual narrative sub-logs exist (e.g. `ep_011_Pilik.md`). Leave empty if none.

### Scaffolding & Comment Block

Immediately following front matter:

```markdown
{% include header_chapter.md %}
{% comment %}
`=map(this.images, (x) => "![im|200](" + x + ")")`
```dataview
LIST without ID "["+ title + "](" + regexreplace(file.path, ".md", "") + ")" + ", from " + regexreplace(file.folder, "^[^\/]*\/", "") FROM ([[]]) OR outgoing([[]]) WHERE file.path != this.file.path SORT file.folder DESC
```
---

- [index](<relative_path_to_hub_index.md>)

{% endcomment %}
```

> [!NOTE]
> The hub link (e.g. `- [index](../../directory/Atles/index.md)`) inside the comment block ensures Jekyll's `_plugins/data_extractor.rb` builds bidirectional links connecting the base/hub to this session.

## 4. Structure, Prose Formatting & Voice

Chapter writing must adhere to setting conventions defined in `.agents/AGENTS.md`:

### Structural Rules

1. **2 to 4 Subheaders**:
   - Structure the chapter body into 2 to 4 themed subsections using `## Heading`.
   - Always leave an empty blank line immediately following any Markdown heading (`#`, `##`, `###`).

2. **2 to 4 Paragraphs per Subheader**:
   - Each subsection must contain between 2 and 4 distinct paragraphs.
   - Separate distinct paragraphs with a blank line. Do not combine multiple paragraphs into a single block.

3. **2 to 4 Sentences per Paragraph**:
   - Each paragraph must consist of between 2 and 4 sentences.
   - Place each sentence on its own line (one sentence per line) where practical.

4. **Prose Voice**:
   - Align vocabulary and aesthetic descriptions with the setting rules in `.agents/AGENTS.md`.

## 5. Verification Checklist

After writing the file:
1. Verify that all internal links resolve to existing files.
2. Confirm the heading spacing rule (blank line after any markdown headings).
3. Ensure British English spelling throughout.
4. Refresh the Tier 1 catalogue: `ruby --disable-gems _plugins/data_extractor.rb`.
5. Leave the created file unstaged in git for user review.
