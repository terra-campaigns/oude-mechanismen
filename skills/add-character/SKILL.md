---
name: add-character
description: Create and integrate a new PC or NPC character note into the directory with canonical YAML front matter, navigation parentage, campaign cross-link, Dataview scaffolding, and setting voice.
argument-hint: brief character concept, name, or role (optional)
---

# Add Character

Create and integrate a new character note (PC or NPC) into the campaign directory.

## 1. Intake & Clarification

If the user's initial prompt does not supply all necessary details, ask clarifying questions before writing:

1. **Character Type**: Is this a Player Character (PC) or Non-Player Character (NPC)?
2. **Name & Title**: Full name and any epithets, call-signs, or formal titles.
3. **Role / Vocation**: Setting-appropriate vocation, career, or corporate role (see `Character Archetypes` in `.agents/AGENTS.md`).
4. **Parent Directory Hub**: Which location, hub, caravan, or faction folder does this character belong to?
   - Match the `parent:` field to the exact `title:` of the folder's `index.md` file.
5. **Campaign Affiliation**: Which campaign does this character pertain to?
   - Default is the active primary campaign in `campaigns/`.
   - This determines the relative backlink placed inside the `{% comment %}` block so that Jekyll's data extractor links the character to that campaign.
6. **Key Details**:
   - **For PCs**: Background details, signature equipment, key affiliations, debts, or employer contracts.
   - **For NPCs**: Motivation, physical oddities, debts/patrons, and relationships with existing characters or factions.

## 2. Canon & Collision Check

Before creating the file:

1. Search `.agents/context/catalog.json` and existing files using `rg` for the character's proposed name to avoid duplicate titles or naming clashes.
2. Search for related NPCs, locations, or factions in `catalog.json` or `directory/` to identify potential cross-links.
3. Check the folder's `index.md` to confirm the exact `title:` value to use for `parent:`.

### Entity Relationships & Cross-Linking

When the user mentions or requests a connection between this character and another entity (PC, NPC, faction, or location):
1. **Prompt for relationship type**: If the prompt does not specify the exact dynamic, ask the user for the nature of the relationship rather than inventing continuity.
2. **Confirm link directionality**: Ask whether to update both character/entity files (bidirectional link) or only the newly created note.
3. **Format cross-links**: Use relative markdown links with `.md` extensions embedded naturally within the background sentences.

## 3. Template & Front Matter

Create the file in the designated subfolder (e.g. `directory/<Subfolder>/<ShortName>.md`).

### Front Matter Specification

```yaml
---
layout: default
template: 0.4
type: people
nav_exclude: false

parent: <Exact title of the parent index.md>
title: <Full Character Name>
role: <Vocation / Title / Corporate Affiliation>
status: 

images: 

---
```

> [!IMPORTANT]
> - Do **not** include the `hooks:` field. It has been discontinued.
> - `type:` must always be `people`.
> - `parent:` must exactly match the parent page's front matter `title`.
> - `status:` is reserved strictly for short symbols (such as `†` for deceased or a marker for missing). Never put descriptive text or conditions here, as Jekyll prepends `status` directly to the character's name in galleries and headers.

### Scaffolding & Campaign Backlink

Immediately following the front matter:

```markdown
{% include header_directories.md %}
{% comment %}
`=map(this.images, (x) => "![im|200](" + x + ")")`
```dataview
LIST without ID "["+ title + "](" + regexreplace(file.path, ".md", "") + ")" + ", from " + regexreplace(file.folder, "^[^\/]*\/", "") FROM ([[]]) OR outgoing([[]]) WHERE file.path != this.file.path SORT file.folder DESC
```
---
[campaign-relationship](<relative_path_to_campaign_index.md>)
{% endcomment %}
```

> [!NOTE]
> The link `[campaign-relationship](<relative_path_to_campaign_index.md>)` inside the comment block is parsed by Jekyll's native `_plugins/data_extractor.rb` to generate cross-link backlinks between the character and the campaign page. Calculate the relative path from the character's file location to the target campaign's `index.md` (e.g. `../../campaigns/UVG24XX/index.md` from `directory/Atles/`).

## 4. Prose Formatting

### For Player Characters (PCs)

Format background traits using setting-specific questions from `## Campaign Specification` in `.agents/AGENTS.md` (or general background questions if unspecified), separated by empty Markdown lines, followed by any debt contract or corporate indenture:

```markdown
**[Question 1]:** [Detail].

**[Question 2]:** [Detail].

**Signature Item / Trait:** [Detail].

[Contract / Debt / Indenture terms].
```

> [!IMPORTANT]
> - Always leave an empty blank line between each prompt item.
> - Ignore system stats, dice pools, and mechanical inventories when creating narrative character notes.

### For Non-Player Characters (NPCs)

Write 2–4 short, punchy sentences in the campaign's setting voice (one sentence per line where practical):
- Connect the NPC to existing characters or factions using relative markdown links.
- Emphasise sensory texture and setting-faithful details from `.agents/AGENTS.md`.

## 5. Verification Checklist

After writing the file:
1. Verify that all internal links resolve to existing files.
2. Confirm the heading spacing rule (blank line after any markdown headings).
3. Ensure British English spelling throughout.
4. Refresh the Tier 1 catalogue: `ruby --disable-gems _plugins/data_extractor.rb`.
5. Leave the created file unstaged in git for user review.
