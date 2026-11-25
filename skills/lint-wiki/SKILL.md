---
name: lint-wiki
description: Health-check the campaign wiki for structural issues — orphan pages, dead links, empty stubs, unused images, deprecated hooks, and catalogue health. Runs the deterministic `lint_wiki.py` CLI (Gate 3) and interprets its findings. Use periodically (e.g. every few sessions) or after a batch of edits to keep the repo clean. No arguments needed.
argument-hint: none (scans the full repo)
---

# Lint Wiki

Run the deterministic structural linter over the campaign repo, then interpret its findings into a diagnostic report artefact with actionable findings grouped by severity.

## Running the linter

The structural checks are deterministic and execute locally with zero token burn. Prefer the unified CLI, falling back to the engine script directly:

```bash
oude lint-wiki --format json          # full repo scan, machine-readable output
python3 scripts/lint_wiki.py --format json
python3 scripts/lint_wiki.py campaigns/ directory/foo.md   # targeted scan of specific paths
python3 scripts/lint_wiki.py --strict  # treat WARN findings as failures (exit 1)
```

- Full scan (no paths) covers: dead internal links, orphan pages, empty stubs, unused images, deprecated `hooks:` front matter, catalogue health (`catalog.json` hashes, unindexed/stale notes), missing front matter (`title`, `parent`, non-default `layout`), duplicate titles, duplicate Tier 1 `id:` values (`duplicate-id`), Tier 2 ruling validation (`rulings`: schema and supersession-DAG (directed acyclic graph) checks over `_gm-materials/rulings/` plus `_gm-materials/.cache/tier2.json` freshness), and `.agents/context/rolling_glossary.md` entries (`rolling-glossary`).
- Targeted mode (explicit paths) runs the file-level checks only and skips repo-wide checks (`orphan`, `unused-image`, `catalogue`, `duplicate-title`, `rolling-glossary` unless `.agents/context/rolling_glossary.md` is explicitly targeted, and `duplicate-id`/`rulings` unless a path resolves inside `_gm-materials/rulings/`), which are reported under `checks_skipped`.
- Exit code is 1 on any FAIL finding (or any finding under `--strict`), 0 when clean, 2 on usage errors.

Do **not** read `_site/`, `.jekyll-cache/`, `_plugins/`, `.obsidian/`, `.git/`, or `_gm-materials/`. The CLI deterministically inspects `_gm-materials/rulings/` locally (and `_gm-materials/.cache/tier2.json` freshness) on its own; the skill itself must still never bulk-read `_gm-materials/`.

## Interpreting findings

Parse the JSON `findings` array (or the text report tables). Group by `check` in the output. The CLI is the source of truth for what was found; your job is triage, not re-detection:

- **dead-link (FAIL):** resolve the path relative to the linking file; fix the target or the link.
- **orphan (WARN):** no inbound links from `directory/`, `systems/`, or `statblocks/` notes (never `campaigns/` session logs). May be intentional; the GM decides.
- **stub (WARN):** fewer than 3 prose lines after front matter. Flesh out or remove.
- **unused-image (WARN):** file under `imgs/` (excluding `imgs/gallery/` and the engine fallback badges in `imgs/badges/`, which are consumed dynamically) referenced nowhere.
- **deprecated-hook (WARN):** migrate `hooks:` front matter to body prose or remove it.
- **catalogue (FAIL/WARN):** missing local `catalog.json` cache is `WARN` (run `bundle exec jekyll build` or `oude doctor --fix` to generate); invalid JSON or `sha` mismatches when present are `FAIL`; unindexed notes, stale entries, and null summaries are `WARN`.
- **front-matter (FAIL/WARN):** missing `title`/`parent` in `campaigns/`, `directory/`, `systems/`; non-default `layout` outside the exempt pages.
- **duplicate-title (FAIL):** identical `title:` values cause navigation confusion in Just the Docs.
- **rolling-glossary (FAIL/WARN):** entries in `.agents/context/rolling_glossary.md` with a missing definition line or a casing conflict against published `catalog.json` titles are `FAIL`; entries carrying `- Definition: Pending canonical definition.` are `WARN` until defined, or promoted to a Tier 1 note and removed from the glossary.
- **duplicate-id (FAIL):** two or more Tier 1 notes share the same explicit `id:` front matter; rename one. Invalid `id:` grammar is reported under `front-matter` (FAIL).
- **rulings (FAIL/WARN):** schema, supersession-DAG, or `opinions` violations in `_gm-materials/rulings/*.md` are FAIL; an absent `_gm-materials/.cache/tier2.json` is WARN (run `oude tier2` or `oude doctor --fix`); a corrupt/unknown-schema or stale `tier2.json` (ruling `sha`, entry, `superseded_by`, or `catalog_sha` drift) is FAIL; coexistence of legacy `.agents/context/decisions.md` with an existing `_gm-materials/rulings/` directory (even when empty) is WARN; unresolved entity/actor slugs and filename-prefix mismatches are WARN.

## Output format

Write the report as a markdown artefact. Use this structure:

````markdown
# Wiki Lint Report

Generated: [date]
Command: `oude lint-wiki --format json`

## Summary

- X dead links
- X orphan pages
- X stubs
- X unused images
- X deprecated hooks
- X catalogue / front matter issues
- X duplicate titles
- X duplicate ids
- X Tier 2 ruling issues
- X rolling-glossary issues

## Findings

| Check | Severity | File | Line | Detail |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

## Recommended actions

- ...
````

Omit any section where no issues were found. If the wiki is clean, say so.

## Rules

- **Read only.** This skill does not edit any files. It produces a diagnostic report.
- Do not open or read PDFs. This is a structural check, not a lore check.
- Do not flag style or prose quality issues — that is the `review-style` skill's job.
- Do not flag orphan pages in `campaigns/` — session logs are typically linked only from their parent arc index, and the arc index is their entry point.
- Report findings neutrally. Not everything flagged is a problem — some orphan pages are intentionally standalone, some stubs are placeholders. The GM decides what to act on.
