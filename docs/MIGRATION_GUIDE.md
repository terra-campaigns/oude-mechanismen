# Vault Migration Guide

Step-by-step cutover of an existing campaign vault (such as `hostile` or `charged`) off Google Drive onto the [ADR 003](adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md) dual-workstation model: git-ignored `_gm-materials/` synchronised peer-to-peer by Obsidian Sync between `ryu` (macOS tabletop) and `artemis` (Debian hub), with commercial PDFs kept on local disk only (ADR 003 "Pillar 3": local storage outside Git and Obsidian Sync).

> **Multi-machine rollout note**: perform the cutover on the workstation that currently holds the vault first, commit, then clone on the secondary machine and enable Obsidian Sync.

## Prerequisites

- `oude` CLI installed and on `PATH` (`uv tool install git+https://github.com/terra-campaigns/oude-mechanismen.git`).
- Obsidian Sync account with the `obsidian-sync.service` daemon running on both machines (host-level contract; `oude doctor` cannot verify it).
- A local Pillar 3 directory for sourcebook PDFs (local-only disk outside Git and Obsidian Sync), e.g. `~/Repos/rpg-sourcebooks/` on each machine (or `smb://artemis.local/rpg`). Never commit PDFs to the public vault.

## Step 1 — Snapshot the vault

```bash
cd ~/Repos/<campaign>
git status            # commit or stash any pending work
cp -R . /tmp/<campaign>-pre-migration-backup
```

## Step 2 — Move legacy folders into `_gm-materials/`

Legacy `_sessions`, `_prep`, and `_digests` lived under the old `drive_dir` (for example Google Drive). Copy or move any existing files into `_gm-materials/` inside the vault (leaving empty directories untouched):

```bash
OLD_DRIVE="/path/to/old/drive_dir"   # e.g. your legacy Google Drive campaign folder
mkdir -p _gm-materials/session-summaries _gm-materials/session-preps _gm-materials/digests
shopt -s nullglob
for f in "$OLD_DRIVE"/_sessions/*; do mv "$f" _gm-materials/session-summaries/; done
for f in "$OLD_DRIVE"/_prep/*;     do mv "$f" _gm-materials/session-preps/; done
for f in "$OLD_DRIVE"/_digests/*;  do mv "$f" _gm-materials/digests/; done
shopt -u nullglob
```

## Step 3 — Anchor `drive_dir` to the repository root

Edit `.agents/context/tier1_sources.yml`:

```yaml
drive_dir: .
```

External sourcebook PDFs live outside the repository in Pillar 3; the portable default `.` keeps `_gm-materials/` inside the vault.

## Step 4 — Re-anchor the Tier 3 index

```bash
oude digest                 # recompiles .agents/context/references.json
```

`oude digest` (`compile_references()`) normalises any leading `/` `source_pdf` paths into `drive_dir`-relative paths or basenames when writing `.agents/context/references.json`, and derives relative `digest_path` values. Inspect `.agents/context/references.json` to confirm no machine-specific paths remain; if any legacy digest `.md` file under `_gm-materials/digests/` has an old absolute path in its frontmatter `source_pdf:` or `Source:` line, update it to a relative path or basename in that `.md` file and re-run `oude digest`.

## Step 5 — Ensure gem consumption, then validate exclusions and hygiene

First ensure the vault consumes the `oude-mechanismen` RubyGem: `Gemfile` pins `oude-mechanismen` (see [DYNAMIC_GEM.md](DYNAMIC_GEM.md#installation)), `_config.yml` includes `plugins: [oude-mechanismen]`, and `bundle install` has succeeded.

> **Linux / Debian 13 (`trixie`) note:** Debian 13 packages Bundler as `/usr/bin/bundle3.3` with no `/usr/bin/bundle` symlink; `oude doctor` resolves `bundle3.3` automatically, or you can invoke `bundle3.3` directly (or symlink `~/.local/bin/bundle -> /usr/bin/bundle3.3`). Always configure Bundler's local install path **outside** an Obsidian Sync vault (`bundle config set --local path ~/.local/share/bundle/<campaign>`) rather than `./vendor/bundle` so Ruby gems are never uploaded into Obsidian Sync.

Then run:

```bash
oude doctor --fix           # repairs .gitignore / _config.yml exclude:, deletes legacy .agents/scripts/ runners and shadowing _plugins/, _includes/, unmodified all-content.md, and refreshes stale catalog.json
oude audit                  # coverage & gap report
bundle exec jekyll build    # Tier 1 catalogue compiles with zero errors (use bundle3.3 on Debian 13 if unlinked)
```

Verify all four `_gm-materials/` exclusion layers from ADR 003 hold: `.gitignore`, `_config.yml` `exclude:`, the gem's `data_extractor.rb` filter, and updated script/skill/template paths (audited by `oude doctor --fix`).

## Step 6 — Commit and clone on the secondary workstation

```bash
git add -A && git commit -m "chore: migrate to _gm-materials/ + drive_dir: . (ADR 003)"
# on the secondary workstation (e.g. artemis):
git clone <vault-url> ~/Repos/<campaign>
```

Before running the first `ob sync` after `ob sync-setup`, configure exclusions and allowed file types so Obsidian Sync does **not** pull stale deleted files from remote history (`_includes/*.html`, `_data/*.json`, legacy `*.py` scripts that would shadow the RubyGem) or upload `vendor/` / build caches:

```bash
cd ~/Repos/<campaign>
ob sync-setup --vault "<obsidian-vault-name>"
ob sync-config --configs "" --file-types image,audio,video,pdf --excluded-folders "_site,vendor,.jekyll-cache,.sass-cache,.bundle,.githooks,.agents,bin,_data"
ob sync
```

> **Why `--file-types` and `--excluded-folders` matter:** Leaving `unsupported` enabled lets Obsidian Sync restore old `.html`, `.json`, `.py`, and `.rb` ghost files from remote vault history, while omitting `vendor` causes `./vendor/bundle` (if ever created) to synchronise thousands of gem files across machines.

Enable Obsidian Sync on both machines pointing at the vault; `_gm-materials/` syncs encrypted peer-to-peer and stays out of Git.

## Step 7 — LAN preview smoke check

On the preview host (e.g. `artemis` with `avahi-daemon` active):

```bash
cd ~/Repos/<campaign>
oude doctor
bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""
```

Open `http://<hostname>.local:4000` (e.g. `http://artemis.local:4000`) from a secondary device — `.local` resolves via mDNS (`avahi-daemon` on Linux; Bonjour on macOS). On non-mDNS clients use `http://<host-ip>:4000`, where `<host-ip>` is the host's LAN address (`ip addr` on Linux, or your router's client list). Confirm pages, `relative_url` links, and gallery images render. One vault at a time on port `4000`.

## Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `oude digest` reports a configured `drive_dir` that does not exist | Re-check `.agents/context/tier1_sources.yml`; read errors now fail loudly instead of silently falling back to the repo root. |
| `references.json` still shows old paths | Edit `source_pdf:` in the digest `.md` note to a relative path or basename, then run `oude digest` (Step 4). |
| `_gm-materials/` appears in the built site or Git | Ensure `Gemfile` + `_config.yml` use the gem, run `oude doctor --fix`, and verify all four exclusion layers (Step 5). |
| `python3 .agents/scripts/...` no longer exists | Legacy runners are deleted by `oude doctor --fix`; use the `oude` CLI (`oude digest`, `oude audit`, `oude transcribe`, …) instead. |
| Jekyll build fails after gem update | `bundle update oude-mechanismen`, then `bundle exec jekyll build`; see [DYNAMIC_GEM.md](DYNAMIC_GEM.md). |
| `bundle: command not found` on Debian 13 (`trixie`) | Use `bundle3.3` or symlink `~/.local/bin/bundle -> /usr/bin/bundle3.3`; `oude doctor` detects `bundle3.3` automatically. |
| Obsidian Sync restores deleted `_includes/`, `_data/`, or uploads `vendor/` | Apply `ob sync-config --configs "" --file-types image,audio,video,pdf --excluded-folders "_site,vendor,.jekyll-cache,.sass-cache,.bundle,.githooks,.agents,bin,_data"` (Step 6), run `bundle config set --local path ~/.local/share/bundle/<campaign>`, and clean up with `oude doctor --fix`. |
