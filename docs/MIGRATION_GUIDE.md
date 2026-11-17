# Vault Migration Guide

Step-by-step cutover of an existing campaign vault (`hostile`, `charged`) off Google Drive onto the [ADR 003](adr/003_dual_workstation_topology_and_semantic_wiki_ingestion.md) dual-workstation model: git-ignored `_gm-materials/` synchronised peer-to-peer by Obsidian Sync between `ryu` (macOS tabletop) and `artemis` (Debian hub), with commercial PDFs kept on local Pillar 3 disk only.

> **Note**: the vaults currently exist on `ryu` and have not yet been cloned on `artemis`. Perform the cutover on `ryu` first, commit, then clone on `artemis` and enable Obsidian Sync.

## Prerequisites

- `oude` CLI installed and on `PATH` (`uv tool install .` from the engine checkout, or the published package).
- Obsidian Sync account with the `obsidian-sync.service` daemon running on both `ryu` and `artemis` (host-level contract; `oude doctor` cannot verify it).
- A local Pillar 3 directory for sourcebook PDFs, e.g. `~/Repos/rpg-sourcebooks/` on each machine (or `smb://artemis.local/rpg`). Never commit PDFs to the public vault.

## Step 1 — Snapshot the vault

```bash
cd ~/Repos/<campaign>
git status            # commit or stash any pending work
cp -R . /tmp/<campaign>-pre-migration-backup
```

## Step 2 — Move legacy folders into `_gm-materials/`

```bash
mkdir -p _gm-materials/session-summaries _gm-materials/session-preps _gm-materials/digests
# Legacy top-level folders (ADR 003 Phase 1 replaced these):
[ -d _sessions ] && mv _sessions/* _gm-materials/session-summaries/ && rmdir _sessions
[ -d _prep ]    && mv _prep/*    _gm-materials/session-preps/    && rmdir _prep
[ -d _digests ] && mv _digests/* _gm-materials/digests/          && rmdir _digests
```

## Step 3 — Anchor `drive_dir` to the repository root

Edit `.agents/context/tier1_sources.yml`:

```yaml
drive_dir: .
```

External sourcebook PDFs may live outside the repository via an absolute or relative path; the portable default `.` keeps `_gm-materials/` inside the vault.

## Step 4 — Re-anchor the Tier 3 index

```bash
oude digest                 # recompiles .agents/context/references.json
```

Confirm every entry in `.agents/context/references.json` has a portable `source_pdf` (relative path or basename — never a host-specific absolute path) and a relative `digest_path`. If legacy digests carry absolute `source_pdf` values, re-record them with `oude digest --scaffold <PDF_PATH> --source-pdf <rel>` or edit the frontmatter by hand.

## Step 5 — Validate exclusions and hygiene

```bash
oude doctor --fix           # repairs .gitignore / _config.yml exclude: / deletes legacy .agents/scripts/ runners
oude audit                  # coverage & gap report
bundle exec jekyll build    # Tier 1 catalogue compiles with zero errors
```

Verify the four-layer `_gm-materials/` exclusion holds: `.gitignore`, `_config.yml` `exclude:`, the gem's `data_extractor.rb` filter, and `oude doctor`.

## Step 6 — Commit and clone on `artemis`

```bash
git add -A && git commit -m "chore: migrate to _gm-materials/ + drive_dir: . (ADR 003)"
# on artemis:
git clone <vault-url> ~/Repos/<campaign>
```

Enable Obsidian Sync on both machines pointing at the vault; `_gm-materials/` syncs encrypted peer-to-peer and stays out of Git.

## Step 7 — LAN preview smoke check

On `artemis` (with `avahi-daemon` active):

```bash
cd ~/Repos/<campaign>
oude doctor
bundle exec jekyll serve --host 0.0.0.0 --port 4000 --livereload --baseurl ""
```

Open `http://artemis.local:4000` from `ryu` or a phone (or `http://<artemis-ip>:4000` on non-mDNS clients). Confirm pages, `relative_url` links, and gallery images render. One vault at a time on port `4000`.

## Troubleshooting

| Symptom | Fix |
| :--- | :--- |
| `oude digest` reports a configured `drive_dir` that does not exist | Re-check `.agents/context/tier1_sources.yml`; read errors now fail loudly instead of silently falling back to the repo root. |
| `references.json` still shows absolute paths | Re-record `source_pdf` as a relative path or basename (Step 4). |
| `_gm-materials/` appears in the built site or git | Run `oude doctor --fix`; verify all four exclusion layers (Step 5). |
| `python3 .agents/scripts/...` no longer exists | Legacy runners are deleted by `oude doctor --fix`; use the `oude` CLI (`oude digest`, `oude audit`, `oude transcribe`, …) instead. |
| `bin/init_vault.sh` vs `oude init` confusion | `bin/init_vault.sh` is deprecated; bootstrap new vaults with `oude init <target>`. |
| Jekyll build fails after gem update | `bundle update oude-mechanismen`, then `bundle exec jekyll build`; see [DYNAMIC_GEM.md](DYNAMIC_GEM.md). |
