---
name: lint-wiki
description: Health-check the campaign wiki for structural issues — orphan pages, dead links, empty stubs, unused images, deprecated hooks, and catalogue health. Use periodically (e.g. every few sessions) or after a batch of edits to keep the repo clean. No arguments needed.
argument-hint: none (scans the full repo)
---

# Lint Wiki

Scan the entire campaign repo for structural health issues. Produce a diagnostic report as an artifact with actionable findings grouped by severity.

## Before starting: confirm with the user

When invoked, briefly confirm:

> I'll scan all markdown files, images, and links across the repo. This will take a moment. Proceed?

Then begin.

## Files to read

- `.agents/AGENTS.md` — for conventions and front matter patterns.
- `.agents/context/tier1_sources.yml` (if present) — to identify active content directories.
- All markdown files in content folders (`campaigns/`, `directory/`, `systems/`, `statblocks/`, `trading/`, and `misc/`).
- `index.md` at the repo root.
- `all-content.md` and `all-agent.md` — to understand what feeds the site build.
- Image files in `imgs/` — list filenames (no need to open them).

Do **not** read `_site/`, `.jekyll-cache/`, `_plugins/`, `.obsidian/`, or `.git/`.

## What to check

Run through each check below. Group findings by category in the output.

### 1. Dead internal links

For every internal markdown link (`[text](path.md)`) in every content file:
- Resolve the path relative to the linking file's directory.
- Verify the target file exists on disk.
- Report any link whose target does not exist, with the source file and line.

### 2. Orphan pages

A page is an orphan if:
- It exists in `directory/`, `systems/`, or `statblocks/` (not in `campaigns/`).
- No other markdown file in the repo links to it (no inbound links).
- It is not an `index.md` file.

List orphan pages. These may need incoming links from session logs or directory siblings.

### 3. Empty stubs

A content file is a stub if:
- Its body (after YAML front matter) contains fewer than 3 non-empty, non-whitespace lines.
- Or its body consists only of front matter and includes/liquid tags with no prose.

List stubs. These are candidates to be fleshed out or removed.

### 4. Unused images

For every file in `imgs/` (recursively):
- Check whether any markdown file references it (in front matter `image:`, `images:`, or inline `![]()`).
- Report images that are never referenced. Exclude `imgs/gallery/` from this check (gallery images are surfaced by the gallery include).

### 5. Deprecated hooks

Scan all YAML front matter for the deprecated `hooks:` field.
- Report any file that still declares `hooks:`. Note that `hooks` is deprecated and should be migrated to body prose or removed.

### 6. Catalogue & Semantic Layer Health

- Verify that `.agents/context/catalog.json` exists and matches the current note count in `.agents/context/tier1_sources.yml`.
- Verify that `summary` is not null for non-stub files.
- Report any file whose content hash (`sha`) differs from `catalog.json`.

### 7. Missing front matter

Every content file in `campaigns/`, `directory/`, and `systems/` should have at minimum:
- `title`
- `parent`

Report files missing either field. Also flag files with `layout:` set to something other than `default` (which is the Just the Docs default and normally omitted), unless the file is `all-content.md`, `all-agent.md`, `index.md`, or a `404` page.

### 8. Duplicate titles

Scan all `title:` values in front matter across the repo. Report any exact duplicates — two files with the same title will cause navigation confusion in Just the Docs.

## Procedure

1. Read `.agents/AGENTS.md` to refresh conventions.
2. Use `find` or `ls` to enumerate all markdown files in content folders and all files in `imgs/`.
3. For each markdown file, extract:
   - YAML front matter fields (`title`, `parent`, `image`, `images`). Check if `hooks` is present (flag as deprecated).
   - All internal markdown links (outbound).
   - All image references.
   - Body line count (after front matter).
4. Build the link graph (which files link to which) or inspect `.agents/context/catalog.json`.
5. Run each check from the list above.
6. Write the report as an artifact.

## Output format

Write the report as a markdown artifact. Use this structure:

````markdown
# Wiki Lint Report

Generated: [date]

## Summary

- X dead links
- X orphan pages
- X stubs
- X unused images
- X deprecated hooks
- X catalogue / front matter issues
- X duplicate titles

## Dead Links

| Source file | Line | Broken link target |
|---|---|---|
| ... | ... | ... |

## Orphan Pages

- `path/to/orphan.md` — no inbound links found.

## Stubs

- `path/to/stub.md` — N lines of content.

## Unused Images

- `imgs/unused-image.png`

## Deprecated Hooks

| Declared in | Hook text |
|---|---|
| ... | ... |

## Front Matter Issues

| File | Issue |
|---|---|
| ... | Missing `title` |

## Duplicate Titles

| Title | Files |
|---|---|
| ... | file1.md, file2.md |
````

Omit any section where no issues were found. If the wiki is clean, say so.

## Rules

- **Read only.** This skill does not edit any files. It produces a diagnostic report.
- Do not open or read PDFs. This is a structural check, not a lore check.
- Do not flag style or prose quality issues — that is the `review-style` skill's job.
- Do not flag orphan pages in `campaigns/` — session logs are typically linked only from their parent arc index, and the arc index is their entry point.
- Report findings neutrally. Not everything flagged is a problem — some orphan pages are intentionally standalone, some stubs are placeholders. The GM decides what to act on.
