# Dynamic Gem Operator Guide (`oude-mechanismen` RubyGem)

How the `oude-mechanismen` RubyGem powers a campaign vault's Jekyll site, how to install, configure, customise, and update it. Architecture decisions live in [ADR 001](adr/001_dynamic_engine_vs_sync_distribution.md) and [ADR 002](adr/002_python_cli_distribution_uv.md).

## What the gem provides

- **In-memory Jekyll plugins**: `lib/oude_mechanismen.rb` requires `jekyll/_plugins/data_extractor.rb` (Tier 1 catalogue compiler → `.agents/context/catalog.json`, with `engine_version` stamping) and `jekyll/_plugins/llm_content.rb`. No `_plugins/` directory is ever copied into the vault.
- **Shared Liquid includes**: a `Jekyll::Hooks.register :site, :after_reset` hook appends the gem's `jekyll/_includes/` to `site.includes_load_paths`, so `connected_to.html`, `image_gallery.html`, and the header includes resolve from the gem. Vault-local `_includes/` still take precedence.
- **Version stamping**: the gem reads the engine `VERSION` file at build time and records it as `engine_version` in `catalog.json`.

## Installation

In the vault's `Gemfile`:

```ruby
source "https://rubygems.org"
gem "jekyll", "~> 4.4.1"
gem "just-the-docs", "0.12.0"
gem "oude-mechanismen", git: "https://github.com/terra-campaigns/oude-mechanismen.git", tag: "v0.6.1"
gem "jekyll-relative-links"
gem "jekyll-redirect-from"
gem "webrick"
```

In `_config.yml`:

```yaml
plugins:
  - oude-mechanismen
```

Then:

```bash
bundle install
bundle exec jekyll build   # writes .agents/context/catalog.json in memory during the build
```

Verify the catalogue compiled with zero errors and carries the expected `engine_version`.

## Configuration & customisation

- **Site identity**: `title`, `description`, `url`, `baseurl` in `_config.yml` (production GitHub Pages values; LAN preview works without touching them — see the [Migration Guide](MIGRATION_GUIDE.md#step-7--lan-preview-smoke-check)).
- **Exclusions**: keep `_gm-materials` (and friends) in `_config.yml` `exclude:` — `oude doctor` verifies this.
- **Theme overrides**: `_sass/custom/custom.scss` for just-the-docs overrides; vault-local `_includes/` shadow gem includes of the same name.
- **Art filter presets**: `.agents/context/aesthetics.yml`; **skills discovery**: `.agents/skills.json` paths pointing at the engine `skills/` directory.
- **Procedural tooling**: the Python CLI (`oude init`, `oude doctor`, `oude digest`, `oude audit`, …) is distributed separately via `uv` (ADR 002) — the gem covers only the Jekyll build.

## Updating the engine

1. Bump the `tag:` in the vault `Gemfile` to the new release.
2. `bundle update oude-mechanismen && bundle exec jekyll build`.
3. For engine-managed files that still ship outside the gem (git hooks, `requirements.txt` pin, `bin/setup`), run `./sync.sh --check <vault>` then `./sync.sh <vault>` from the engine checkout. `sync.sh` never overwrites locally modified files unless `--force` is passed.
4. Run `oude doctor --fix` to clean legacy state (notably it deletes the obsolete `.agents/scripts/` runner directory — ADR 002).

## Deprecations

- `bin/init_vault.sh` is **deprecated** in favour of `oude init <target>`; it remains only for CI compatibility.
- `sync.sh --init` is legacy; use `oude init`.
- `.agents/scripts/*.py` runner wrappers are legacy and removed by `oude doctor --fix`; call the `oude` CLI directly.

## Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `bundle exec jekyll build` fails with `cannot load such file -- oude_mechanismen` | The `plugins:` entry in `_config.yml` is missing; add `- oude-mechanismen`. |
| Catalogue is stale after editing notes | Rebuild (`bundle exec jekyll build`) or run `oude doctor --fix`; the catalogue is generated in-memory at build time. |
| `engine_version` in `catalog.json` does not match the gem tag | Update the gem (`bundle update oude-mechanismen`) and rebuild. |
| Private `_gm-materials/` leaks into the built site | Check all four exclusion layers and run `oude doctor --fix`. |
| Gem build fails locally | `gem build oude-mechanismen.gemspec` in the engine checkout; CI validates this on every PR. |
