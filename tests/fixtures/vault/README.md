# Fixture vault

Minimal, deterministic Jekyll site used by `tests/test_dynamic_gem.rb` (`JekyllHeadlessTest`, issue #23) to prove the *packaged* `oude-mechanismen` gem end to end:

- `index.md`, `directory/alpha.md`, and `campaigns/ep_001.md` cross-link, so `_plugins/data_extractor.rb` populates `site.data.markdown_links` / `lastmod` and writes `.agents/context/catalog.json`.
- `directory/alpha.md` uses `{% include connected_to.html %}`, which the gem serves in-memory from its bundled `jekyll/_includes/` (no vault-local `_includes/` exists here).
- `_layouts/default.html` proves plain layout/template rendering.

The test copies this directory into a temporary folder, builds and installs the gem into a scratch `GEM_HOME`, and runs a headless `jekyll build` against that installed gem. The `bundle exec jekyll build` and clean-venv wheel scenarios for issue #34 are covered by the Python suites in PR #86 (`tests/test_e2e_jekyll.py`, `tests/test_e2e_wheel.py`).

Never run a Jekyll build directly inside this directory: it would write `_site/`, `.jekyll-cache/`, and `.agents/context/catalog.json` into the repository checkout.
