# Tests

Automated test suites for the `oude-mechanismen` engine. CI runs them via `.github/workflows/ci.yml` (the `validate` job).

## Python unit tests

Discovered and run with:

```bash
python3 -m unittest discover -s tests -v
```

The end-to-end suites for issue #34 live in `tests/test_e2e_jekyll.py` (real `bundle exec jekyll build` of a fixture vault) and `tests/test_e2e_wheel.py` (`uv build` + clean-venv install outside the checkout, `resolve_asset_dir` checks); they are part of `unittest discover` and skip automatically when `ruby`/`bundle`/`uv` are unavailable (landed for #34 on `develop`).

## Headless dynamic-gem integration test (issue #23)

`tests/test_dynamic_gem.rb` (`JekyllHeadlessTest`, minitest) validates the packaged RubyGem in isolation:

1. `gem build oude-mechanismen.gemspec` and assert the archive bundles `lib/`, `jekyll/_plugins/`, and `jekyll/_includes/` (and no `tests/` or `.github/` clutter).
2. Install the built gem into a scratch `GEM_HOME` and load it in isolation (`require "oude-mechanismen"` from the installed location only).
3. Run a headless `jekyll build` of `tests/fixtures/vault/` driven by that installed gem: assert layout and page rendering, the gem-served `connected_to.html` include, `site.data.markdown_links` output from `_plugins/data_extractor.rb`, and the `.agents/context/catalog.json` catalogue (engine version stamp, Tier 1 entries, links).

Run locally:

```bash
gem install --no-document jekyll -v '~> 4.4.1'
ruby tests/test_dynamic_gem.rb
```

CI runs it in the `validate` job (Ruby is set up and Jekyll installed there).
