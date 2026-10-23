---
name: lookup-context
description: Consult campaign lore, characters, locations, rulings, and rules across Tier 1 (canonical notes), Tier 2 (active rulings), and Tier 3 (reference digests) using low-token progressive retrieval.
argument-hint: topic, entity name, or question
---

# Lookup Context

Perform progressive, token-efficient context lookups across all tiers of campaign knowledge without reading files in bulk.

## Procedure

### 1. Consult Tier 1 & Tier 2 Indexes First

- **Tier 1 (Catalogue):** Inspect `.agents/context/catalog.json`. Search the `entries` list for matches against `title`, `type`, `region`, or `parent`.
- **Tier 2 (Rulings Log):** Inspect `.agents/context/decisions.md` to check if a table ruling or conversational decision has already been agreed with the GM.

### 2. Targeted Reading

- If an entry is found in `catalog.json`, open only the relevant file (`path`) using `view_file`.
- Use line ranges where practical rather than loading entire long files.
- If the file's current SHA does not match `sha` in `catalog.json`, read the file directly as the entry may be slightly stale.

### 3. Consult Tier 3 Reference Digests (When Needed)

- If the topic relates to unvisited sectors/trail stations, weird rules, external sourcebooks, or general setting lore not yet found in Tier 1:
  1. Inspect `.agents/context/references.json` to find the relevant source and section.
  2. Open the matching digest file using the path specified under `digest_path` in `references.json`.
  3. Only inspect raw source PDFs if exact table entries or art details on a specific cited page (`[p. X]`) are strictly needed.

### 4. Response & Grounding Rules

- **Label Canon Tiers:** Always mark facts by their canon status:
  - **Tier 1 (Established Canon):** Drawn directly from published campaign notes.
  - **Tier 2 (Agreed Ruling):** Recorded in `.agents/context/decisions.md`.
  - **Tier 3 (Influence / Possibility):** From reference PDFs and digests; not canon until adopted by the GM.
- **Mark Gaps:** If an entity or fact is not found in the indexes, report it clearly as unestablished. Never invent lore or continuity without explicitly marking it as a proposal for the GM.
