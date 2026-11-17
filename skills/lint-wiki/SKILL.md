---
name: lint-wiki
description: Health-check the campaign wiki for structural issues — orphan pages, dead links, empty stubs, unused images, deprecated hooks, and catalogue health. Runs the deterministic `lint_wiki.py` CLI (Gate 3) and interprets its findings. Use periodically (e.g. every few sessions) or after a batch of edits to keep the repo clean. No arguments needed.
argument-hint: none (scans the full repo)
---

# Lint Wiki

Run the deterministic structural linter over the campaign repo, then interpret its findings into a diagnostic report artifact with actionable findings grouped by severity.

## Running the linter

The structural checks are deterministic and execute locally with zero token burn. Prefer the unified CLI, falling back to the engine script directly:

```bash
oude lint-wiki --format json          # full repo scan, machine-readable output
python3 scripts/lint_wiki.py --format json
python3 scripts/lint_wiki.py campaigns/ directory/foo.md   # targeted scan of specific paths
python3 scripts/lint_wiki.py --strict  # treat WARN findings as failures (exit 1)
```

- Full scan (no paths) covers: dead internal links, orphan pages, empty stubs, unused images, deprecated `hooks:` front matter, catalogue health (`catalog.json` hashes, unindexed/stale notes), missing front matter (`title`, `parent`, non-default `layout`), and duplicate titles.
- Targeted mode (explicit paths) runs the file-level checks only and skips repo-wide checks (orphans, unused images, catalogue), which are reported under `checks_skipped`.
- Exit code is 1 on any FAIL finding (or any finding under `--strict`), 0 when clean, 2 on usage errors.

Do **not** read `_site/`, `.jekyll-cache/`, `_plugins/`, `.obsidian/`, `.git/`, or `_gm-materials/`.

## Interpreting findings

Parse the JSON `findings` array (or the text report tables). Group by `check` in the output. The CLI is the source of truth for what was found; your job is triage, not re-detection:

- **dead-link (FAIL):** resolve the path relative to the linking file; fix the target or the link.
- **orphan (WARN):** no inbound links from `directory/`, `systems/`, or `statblocks/` notes (never `campaigns/` session logs). May be intentional; the GM decides.
- **stub (WARN):** fewer than 3 prose lines after front matter. Flesh out or remove.
- **unused-image (WARN):** file under `imgs/` (excluding `imgs/gallery/`) referenced nowhere.
- **deprecated-hook (WARN):** migrate `hooks:` front matter to body prose or remove it.
- **catalogue (FAIL/WARN):** missing/stale `catalog.json`, sha mismatches (recompile via the `data_extractor` plugin or `oude doctor --fix`), unindexed notes, null summaries.
- **front-matter (FAIL/WARN):** missing `title`/`parent` in `campaigns/`, `directory/`, `systems/`; non-default `layout` outside the exempt pages.
- **duplicate-title (FAIL):** identical `title:` values cause navigation confusion in Just the Docs.

## Output format

Write the report as a markdown artifact. Use this structure:

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
