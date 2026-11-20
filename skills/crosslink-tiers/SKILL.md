---
name: crosslink-tiers
description: Cross-link Tier 1 canonical notes and Tier 3 reference digests by inserting relative Markdown links inside {% comment %}...{% endcomment %} blocks, enabling Obsidian graph navigation while keeping GM-only links hidden from the published Jekyll site.
argument-hint: none (scans the full repo) or specific note paths
---

# Crosslink Tiers

Scan Tier 1 notes (`.agents/context/catalog.json`) and Tier 3 digest notes (`.agents/context/references.json` / `_gm-materials/digests/`) to discover related entities across tiers, then insert idempotent relative Markdown links hidden inside `{% comment %}...{% endcomment %}` blocks.

## Discovery

1. Load `.agents/context/catalog.json` for Tier 1 entries (title, path, aliases, tags).
2. Load `.agents/context/references.json` for Tier 3 digest entries (source, slug, digest_path).
3. Match entities by title, aliases, tags, and related concepts across the two indexes.

## Link Insertion

### Tier 1 → Tier 3

For each Tier 1 note with matching Tier 3 digests:

1. Check if the note already contains a `{% comment %}...{% endcomment %}` block with a cross-tier links section (marked by `<!-- crosslink-tiers -->`).
2. If present, update the block in place. If absent, append a new block at the bottom of the note:

```markdown
{% comment %}
<!-- crosslink-tiers -->
## Tier 3 References
- [Entity Name](../../_gm-materials/digests/<source>/<path>.md) — brief annotation
{% endcomment %}
```

### Tier 3 → Tier 1 (optional/bidirectional)

For matching Tier 3 digest notes, add links under a `## Connections` or `## See Also` section pointing back to Tier 1 canon notes.

## Idempotency

- Never duplicate an existing link to the same target.
- Preserve existing content inside comment blocks; only add or update the cross-tier links section.
- Use relative paths from the source file to the target.

## Rules

- Links inside `{% comment %}...{% endcomment %}` are indexed by Obsidian for navigation but invisible in Jekyll HTML output. Hidden links between Tier 1 notes still feed `site.data.markdown_links` / `connected_to.html`; only targets containing an `_gm-materials/` path segment are excluded from site data (and exempt from dead-link FAIL when `_gm-materials/` is absent on disk).
- Never expose `_gm-materials/` paths outside comment blocks.
- Run `oude lint-wiki` after insertion to confirm no dead-link failures.
