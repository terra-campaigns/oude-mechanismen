# Architectural Design 002 — Doctor Remediation & Dynamic LLM Content

Status: Proposed
Addresses: GitHub Issues #13, #14, #15, #16
Author: Principal Architect
Language: British English throughout

---

## 1. Executive Summary & System Architecture

Issues #13–#16 are not four independent defects; they are the four remaining
loose ends of a single architectural migration already decided in ADR 001
(dynamic gem distribution) and ADR 002 (zero-clone `uv` CLI distribution).
Each issue describes a class of artefact that ADR 001/002 made *redundant* but
never *removed* from downstream vaults:

| Issue | Redundant artefact class | ADR that obsoleted it |
|---|---|---|
| #13 | Shadowing duplicate `_includes/` files | ADR 001 (gem `includes_load_paths`) |
| #14 | Legacy runner scripts in `.agents/scripts/` | ADR 002 (unified `oude` CLI) |
| #15 | `.agents/.engine-version` stamp file | ADR 001 (`catalog.json` `engine_version`) |
| #16 | Physical root `all-content.md` | ADR 001 (gem-bundled plugin) |

Collectively, resolving them completes the decoupling: after this work, a
downstream vault contains **only campaign content and configuration**, while
the engine owns **all procedural code, includes, version truth, and generated
endpoints**. `oude doctor` becomes the single enforcement point that detects
drift from this contract and `--fix` converges any vault — clean, legacy, or
partially migrated — to it.

---

## 2. Detailed Design — Issue #13: Shadowing Includes

### 2.1 Asset discovery and packaging

`pyproject.toml` `[tool.hatch.build.targets.wheel.force-include]` currently
maps only `jekyll/all-content.md`. Add:

```toml
"jekyll/_includes" = "oude_mechanismen/jekyll/_includes"
```

`resolve_asset_dir("jekyll/_includes")` in `src/oude_mechanismen/__init__.py`
already implements the correct dual resolution: `PACKAGE_DIR / name` first
(installed wheel), then `ENGINE_ROOT / name` (editable checkout). No change
needed there; the packaging change alone makes the path resolvable in both
modes.

### 2.2 Detection logic in `oude doctor`

New check block in `_doctor()`:

1. `engine_includes = {p.name for p in resolve_asset_dir("jekyll/_includes").iterdir() if p.is_file()}`
2. For each file in `vault/_includes/`, if `file.name in engine_includes` → emit
   `⚠ Shadowing include detected: _includes/<name>` and mark failure.

### 2.3 Remediation logic in `oude doctor --fix`

- **Filename comparison is the primary strategy.** The engine include set is
  a closed, versioned list (`connected_to.html`, `header_chapter.md`,
  `header_directories.md`, `image_gallery.html`). Any vault file whose name
  matches an engine include is by definition a pre-ADR 001 sync copy and is
  deleted. Content comparison is deliberately *not* used as a gate: a
  campaign that hand-edited a synced copy still wants the gem version to win,
  and diffing would only create a third source of truth.
- Genuine campaign-specific overrides (`footer_custom.html`,
  `chapter_header.md`, `nav_footer_custom.html`) have names outside the
  engine set and are preserved untouched.
- After deletion, if `_includes/` exists and is empty, `rmdir` it.

### 2.4 Tests

`tests/test_cli.py`: fixture vault with a shadowing `connected_to.html` plus
a custom `footer_custom.html`; assert warning text, assert `--fix` removes
only the shadow, assert empty-dir pruning.

---

## 3. Detailed Design — Issue #14: Obsolete Runner Scripts

### 3.1 Detection

Define a closed constant in `cli.py`:

```python
LEGACY_RUNNER_SCRIPTS = {
    "lint_chapter.py", "harvest_archival.py", "scribe_session.py",
    "transcribe_session.py", "generate_digests.py", "audit_coverage.py",
    "art_filter.py", "benchmark_models.py",
}
```

Any `*.py` in `vault/.agents/scripts/` whose name is in this set →
`⚠ Legacy runner script detected: .agents/scripts/<name>`.

### 3.2 Remediation

`--fix` unlinks each detected script; if `.agents/scripts/` is empty
afterwards, prune the directory. Non-legacy files in that directory (rare,
bona fide campaign tooling) are preserved.

### 3.3 `templates/runners/` lifecycle

Deprecate in place: stop referencing `templates/runners/` from
`_init_repository` (it is already not in `TEMPLATE_MAPPINGS`), add a
deprecation note to `templates/runners/README` if present, and delete the
directory in the first minor release after this design ships. The engine's
own `scripts/` directory is unaffected — it is the CLI's pass-through
backend, not a vault artefact.

---

## 4. Detailed Design — Issue #15: `.agents/.engine-version` Lifecycle

### 4.1 Trade-off analysis

| Criterion | Option 1: reconcile/update the stamp | Option 2: deprecate in favour of `catalog.json` |
|---|---|---|
| Single source of truth | No — two files can drift again | Yes — `catalog.json` is written by the build itself |
| Failure mode | Silent drift between stamp and build | None; version is derived, not stored |
| Cost | Permanent doctor check + fix path | One-time removal |
| Information value | Duplicates what `catalog.json` already records | — |

### 4.2 Recommendation

**Option 2 — formal deprecation.** `catalog.json`'s `engine_version` is
authoritative because it is stamped by `data_extractor.rb` during the same
build that produces the catalogue; a hand-maintained stamp file can only ever
be a stale copy of that fact. Keeping both invites exactly the drift this
issue reports.

### 4.3 Behaviour

- `oude doctor`: if `.agents/.engine-version` exists →
  `⚠ Deprecated version stamp detected: .agents/.engine-version (catalog.json is authoritative)`.
- `oude doctor --fix`: delete the file.
- Additionally validate consistency: if both `catalog.json`'s
  `engine_version` and the installed `__version__` exist and differ, warn
  that the vault was last built with a different engine version and suggest
  `bundle exec jekyll build`.
- Documentation: update `AGENTS.md` §5 (remove `sync.sh` stamping
  references), `README.md`, and remove the stamp write from `sync.sh`.

---

## 5. Detailed Design — Issue #16: Dynamic `/all-content.html`

### 5.1 Generator architecture

Extend `jekyll/_plugins/llm_content.rb` (already gem-bundled and loaded by
Jekyll as a plugin) with:

```ruby
module Jekyll
  class LlmContentPage < Jekyll::PageWithoutAFile
    def initialize(site, base, dir, name)
      @site = site
      @base = base
      @dir  = dir
      @name = name
      self.data = {
        "layout" => nil,
        "permalink" => "/all-content.html",
        "sitemap" => false,
      }
      self.content = File.read(<gem-bundled all-content.md body>, encoding: "utf-8")
    end
  end

  class LlmContentGenerator < Jekyll::Generator
    priority :low   # run after site.pages is fully populated
    def generate(site)
      return if site.pages.any? { |p| p.url == "/all-content.html" }
      site.pages << LlmContentPage.new(site, site.source, "", "all-content.html")
    end
  end
end
```

The Liquid body of the current `all-content.md` (front matter stripped) is
read from the gem's bundled copy at build time, so the template text remains
single-sourced in `jekyll/all-content.md` while the *page* is synthesised in
memory. `PageWithoutAFile` participates in the normal render pipeline, so
Liquid and Markdown conversion produce output identical to today's physical
page. `priority :low` guarantees all content pages exist before the dump is
generated.

### 5.2 Graceful coexistence

The generator **yields**: if the vault ships its own root `all-content.md`
(or any page resolving to `/all-content.html`), the generator does nothing
and the campaign's custom page wins. This preserves an escape hatch for
campaigns that genuinely customise the dump.

### 5.3 Scaffolding & CLI updates

- Remove `("jekyll/all-content.md", "all-content.md")` from
  `TEMPLATE_MAPPINGS` in `src/oude_mechanismen/cli.py`.
- Remove the corresponding copy from `bin/init_vault.sh`.
- `oude doctor`: root `all-content.md` is no longer required; under `--fix`,
  detect a root `all-content.md` that is byte-identical to the bundled
  template and prune it (custom variants are reported, not deleted).

---

## 6. Cross-Cutting Verification & Test Strategy

- **Python unit tests** (`tests/test_cli.py`, `tests/test_init_vault.py`):
  clean vault (no warnings), legacy vault (all four warning classes fire),
  `--fix` convergence (idempotent second run is clean), preservation of
  genuine custom files, empty-directory pruning, and `init` no longer
  scaffolding `all-content.md`.
- **Ruby verification**: build a fixture Jekyll site with the gem loaded;
  assert `_site/all-content.html` exists, matches the pre-change output
  byte-for-byte, and that a custom root `all-content.md` suppresses the
  generated page.
- **Wheel packaging test**: `uv build` then install the wheel into a clean
  venv and assert `resolve_asset_dir("jekyll/_includes")` resolves inside
  `site-packages`.

---

## 7. Implementation Roadmap

| Phase | Scope | Risk & rollback |
|---|---|---|
| 1 | #16 generator + scaffolding removal + doctor check | Low; generator yields to custom pages. Rollback: restore `all-content.md` scaffolding |
| 2 | #13 packaging + shadowing detection/fix | Low; filename-set comparison is conservative. Rollback: re-sync includes via git history |
| 3 | #14 runner-script audit + `templates/runners/` deprecation | Low; deletions are git-recoverable. Rollback: restore from vault git history |
| 4 | #15 deprecate `.engine-version`, docs + `sync.sh` updates | Low; single-source-of-truth simplification. Rollback: re-add stamp in `sync.sh` |

Each phase is independently mergeable and leaves `oude doctor` green on both
clean and legacy vaults at every step.
