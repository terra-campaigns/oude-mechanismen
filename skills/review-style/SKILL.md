---
name: review-style
description: Review and polish a campaign file against the project's setting voice and tone. Uses the local .agents/AGENTS.md for tone calibration, genre aesthetics, reference source material, and calibration examples. Takes one file path as argument.
argument-hint: path to the markdown file to review (relative to repo root)
---

# Review Style

Apply the campaign setting's voice to a content file using minimal surgical edits that maximise flavour without rewriting.

## Before editing: ask two questions

When invoked, **always ask the user these two questions** before doing any work. Use a multi-choice prompt.

### 1. Depth

> How deep should this review go?

- **Quick** — Use `.agents/AGENTS.md` and nearby repo files only. Fast, good for routine polish.
- **Deep** — Also consult reference PDFs listed under `## Campaign Specification` in `.agents/AGENTS.md` to calibrate tone and lore against source material. Slower, better for important or lore-heavy files.

If **Deep** is selected, read the most relevant PDF(s) from the path specified under `Reference Material` in `.agents/AGENTS.md` following the priority order declared there. Read enough to absorb voice. Treat PDF content as Tier 3 canon: influence for tone and texture, not automatic canon.

### 2. Scope

> How broad should the review be?

- **Single file** — Review only the target file.
- **Vicinity** — Review the target file, then also review files it links to directly and sibling files in the same folder. Edit each file that needs it.
- **Broad** — Review the target file's entire content area (e.g. all of `campaigns/<subfolder>/` or all of `directory/<subfolder>/`). Edit each file that needs it.

## Files to read before editing

**Always required to be in context:**
- `.agents/AGENTS.md` — for canonical style rules, tone, aesthetics, and calibration examples.
- The target file itself.

**Also read for cross-reference (do not edit unless scope includes them):**
- Nearby files in the same folder or parent folder, to absorb local naming conventions, existing tone, and linked content.

## What to change

1. **Prose voice.** Sharpen sentences toward the register defined in `.agents/AGENTS.md`:
   - Follow the target cadence, sentence length rules, and setting vocabulary.
   - British English spelling throughout.
   - Do not over-flourish. A light, precise hand is better than purple parody.

2. **Mechanical text.** Polish for readability, but never alter values, stats, dice, costs, or game meaning. If a hook or stat block reads flatly, you may tighten the wording — but the information must be identical.

3. **Formatting.** Follow existing conventions:
   - Skip a line between paragraphs, not within bulleted lists.
   - Preserve YAML front matter exactly as-is (keys, values, order).
   - Preserve all Liquid includes, Dataview queries, and Jekyll comment blocks verbatim.
   - Preserve all internal links exactly as they are (relative paths, `.md` extensions).
   - Preserve image references and gallery entries exactly.

## What NOT to change

- YAML front matter values (title, parent, nav_order, type, hooks, images, etc.).
- Liquid tags (`{% include ... %}`, `{% comment %}...{% endcomment %}`).
- Dataview code blocks.
- Internal link paths or link text that serves as a proper noun or canonical name.
- Game-mechanical values: dice, costs, hit points, inventory, stat lines.
- Content that is already in good voice — do not edit for the sake of editing.

## Procedure

1. **Ask** the two questions (Depth and Scope).
2. Read `.agents/AGENTS.md` for style rules, tone, and calibration examples.
3. If **Deep**: read reference PDFs as specified in `.agents/AGENTS.md`.
4. Read the target file.
5. Read 2–3 nearby files in the same folder (siblings or parent index) to calibrate local tone and naming.
6. If **Vicinity** or **Broad** scope: identify the full set of files to review based on the selected scope.
7. For each file in scope, identify passages where the prose is flat, generic, overly modern, or out-of-voice. Focus on:
   - Descriptions that lack sensory texture, physical grit, or setting economy.
   - Sentences that are overly long, explanatory, or purple.
   - Mechanical text that is awkward but could be tightened without changing meaning.
8. Edit each file directly. The user will review changes line-by-line in the IDE.
9. If a file is already well-voiced, say so and skip it.

## Rules

- Never invent new lore, names, NPCs, locations, or continuity.
- Never remove content. If something reads poorly, improve it — do not delete it.
- When in doubt, leave it alone. The lightest edit that brings a passage into voice is the best edit.
- If the file is already well-voiced, say so and make no changes.
