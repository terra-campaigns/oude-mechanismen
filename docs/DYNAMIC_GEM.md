# Dynamic Gem Operator Guide (`oude-mechanismen` RubyGem)

How the `oude-mechanismen` RubyGem powers a campaign vault's Jekyll site, how to install, configure, customise, and update it. Architecture decisions live in [ADR 001](adr/001_dynamic_engine_vs_sync_distribution.md) and [ADR 002](adr/002_python_cli_distribution_uv.md).

## What the gem provides

- **In-memory Jekyll plugins**: `lib/oude_mechanismen.rb` requires `jekyll/_plugins/data_extractor.rb` (Tier 1 catalogue compiler → `.agents/context/catalog.json`, with `engine_version` stamping) and `jekyll/_plugins/llm_content.rb`. No `_plugins/` directory is ever copied into the vault.
- **Shared Liquid includes**: a `Jekyll::Hooks.register :site, :after_reset` hook appends the gem's `jekyll/_includes/` to `site.includes_load_paths`, so `connected_to.html`, `image_gallery.html`, and the header includes resolve from the gem. Vault-local `_includes/` still take precedence.
- **Version stamping**: the gem reads the engine `VERSION` file at build time and records it as `engine_version` in `catalog.json`.

## Installation

Copy `templates/jekyll/Gemfile.template` (or scaffold one with `oude init`) as `Gemfile` in the vault, and set the `oude-mechanismen` `tag:` to the release you want (e.g. `v0.6.0`; list available tags with `git ls-remote --tags https://github.com/terra-campaigns/oude-mechanismen.git`).

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
- **Art filter presets**: `.agents/context/aesthetics.yml`.
- **Agent skills & procedural tooling**: the Python CLI and global skills (`oude init`, `oude install-skills`, `oude doctor`, `oude digest`, `oude audit`, …) are distributed separately via `uv` (ADR 002) and registered in `~/.gemini/config/skills.json` — the gem covers only the Jekyll build.

## Updating the engine

1. Bump the `tag:` in the vault `Gemfile` to the new release.
2. Run `bundle update oude-mechanismen && bundle exec jekyll build`.
3. Update the Python CLI and global skills (if needed): `uv tool install --force git+https://github.com/terra-campaigns/oude-mechanismen.git@<tag>` followed by `oude install-skills`.
4. Run `oude doctor --fix` inside the vault to verify configuration and prune any legacy files (such as `.agents/scripts/` runners, shadowing `_plugins/`, or `.agents/.engine-version`).

## Deprecations

- `sync.sh` is **deprecated**; gem-served Jekyll assets (ADR 001), `oude` CLI distribution (ADR 002), and `oude doctor --fix` replace template syncing.
- `bin/init_vault.sh` is **deprecated** in favour of `oude init <target>`; retained temporarily while legacy references and tests (`tests/test_init_vault.py`) remain.
- `.agents/scripts/*.py` runner wrappers are legacy and removed by `oude doctor --fix`; call the `oude` CLI directly.

## Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `bundle exec jekyll build` fails with `cannot load such file -- oude_mechanismen` | `_config.yml` declares `- oude-mechanismen`, but Bundler cannot find the gem; add it to `Gemfile`, run `bundle install`, and invoke Jekyll via `bundle exec jekyll build`. |
| `catalog.json` is not generated during build | `_config.yml` is missing `- oude-mechanismen` under `plugins:`; add it (or run `oude doctor --fix`). |
| Catalogue is stale after editing notes | Rebuild (`bundle exec jekyll build`) or run `oude doctor --fix`; the catalogue is generated in-memory at build time. |
| `engine_version` in `catalog.json` does not match the gem tag | Update the gem (`bundle update oude-mechanismen`) and rebuild. |
| Private `_gm-materials/` leaks into the built site | Check all four ADR 003 exclusion layers — `.gitignore`, `_config.yml` `exclude:`, the gem's `data_extractor.rb` filter, and updated script/skill/template paths — then run `oude doctor --fix`. |
| Gem build fails locally | `gem build oude-mechanismen.gemspec` in the engine checkout; CI validates this on every PR. |
