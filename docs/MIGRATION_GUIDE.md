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
oude doctor --fix           # repairs .gitignore (_gm-materials/, .agents/context/catalog.json, .agents/context/rolling_glossary.md, .agents/context/references.json, _gm-materials/.cache/tier2.json) / _config.yml exclude:, untracks derived caches if committed, deletes legacy .agents/scripts/ runners and shadowing _plugins/, _includes/, deprecated all-content.md, and refreshes local catalog.json
oude audit                  # coverage & gap report
bundle exec jekyll build    # Tier 1 local catalogue cache compiles with zero errors (use bundle3.3 on Debian 13 if unlinked)
```

Verify all four `_gm-materials/` exclusion layers from ADR 003 hold: `.gitignore`, `_config.yml` `exclude:`, the gem's `data_extractor.rb` filter, and updated script/skill/template paths (audited by `oude doctor --fix`). Also confirm `.agents/context/catalog.json`, `.agents/context/rolling_glossary.md`, and `.agents/context/references.json` are gitignored and untracked (if upgrading manually from an older vault where any of them was committed, run `git rm --cached --ignore-unmatch .agents/context/catalog.json .agents/context/rolling_glossary.md .agents/context/references.json`, and ensure any local `.git/hooks/pre-commit` script does **not** stage any derived cache).

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

## Migrating Legacy `.agents/context/decisions.md`

Older vaults keep confirmed table rulings as unstructured prose in the Git-tracked `.agents/context/decisions.md`. [Design 006](designs/006_tier2_canon_and_faction_turns.md) retires that file in favour of structured rulings inside the git-ignored `_gm-materials/rulings/` (compiled by `oude tier2` into `_gm-materials/.cache/tier2.json`). Migrate manually:

1. Split the file: static style/procedure conventions move into `.agents/AGENTS.md`; mutable world-state rulings become one structured ruling file per decision under `_gm-materials/rulings/<id>_<slug>.md`, with YAML front matter per the [Design 006 ruling schema](designs/006_tier2_canon_and_faction_turns.md#component-2-canonical-ruling-schema-_gm-materialsrulingsmd):

   ```yaml
   ---
   id: R-001                 # ^R-[0-9]{3,}$, unique across _gm-materials/rulings/
   title: Covert tribute route
   date: 2026-11-01          # real-world ISO date YYYY-MM-DD
   in_world_date: "1025-12"  # optional freeform in-world campaign calendar label; omit or null when unused
   kind: faction-turn        # or `ruling`
   status: active            # active | superseded | retracted | promoted
   fact: The Iron Pots secretly tax the Sigisfarne road.
   entities: [sigisfarne]    # Tier 1 slugs, joined against catalog.json ids
   actors: [piot_chant, iron_pot_6_body]   # required non-empty for faction-turn
   supersedes: []            # authored list of ruling IDs; superseded_by is derived
   promoted_to: null         # required when status: promoted, null otherwise
   retraction_reason: null   # required when status: retracted, null otherwise
   turn:                     # optional freeform faction-turn metadata
     active_actor: piot_chant
     roll: 17
   opinions:                 # required non-empty for faction-turn; each item is:
     - actor: piot_chant     #   a slug listed in `actors`
       vote: 1               #   integer -1, 0, or +1
       shifted: true         #   boolean
       stance: Push the tribute.   #   non-empty string
   ---
   ```

   Status semantics: `active` and `superseded` rulings must not set `promoted_to` or `retraction_reason`; `promoted` requires a valid Tier 1 `promoted_to` path (existing `.md` inside `include_paths`, outside `_gm-materials/` and `.agents/`, not matching `exclude_paths`) and forbids `retraction_reason`; `retracted` requires a non-empty `retraction_reason`, forbids `promoted_to`, and must keep `supersedes: []`. Supersession edges must form a DAG (directed acyclic graph) with at most one active successor per target.
2. Remove `.agents/context/decisions.md` once everything is moved (`oude lint-wiki` and `oude doctor` warn while both coexist; `oude doctor` never auto-deletes it).
3. Validate and compile:

```bash
oude doctor --fix        # refreshes .gitignore/_config.yml exclusions and untracks derived caches
oude tier2               # validates _gm-materials/rulings/ and compiles _gm-materials/.cache/tier2.json
oude lint-wiki           # Gate 3: schema, supersession DAG (directed acyclic graph), duplicate Tier 1 ids, tier2.json freshness
```

Already-pushed public Git history containing `.agents/context/decisions.md` in `charged`/`hostile` is accepted as-is; no history rewrite is performed. The read-only fallback in `scripts/tier2.py:load_active_rulings_text()` keeps un-migrated vaults working until the split completes.

## Migrating Legacy Digest `entity_type` Keys

[Design 007](designs/007_unified_type_key_for_digests.md) unifies digest front matter classification on `type` (values `index | people | faction | location | creature | artefact | mechanic | table | reference | other`, aligning `person` to `people` and adding `reference`).

1. **Single-writer Obsidian Sync precondition:** run the migration on **one** workstation only (`ryu` or `artemis`, after Step 1's backup snapshot) and let Obsidian Sync propagate the updated `_gm-materials/digests/` notes before running on the second machine. If concurrent edits create a `*conflicted copy*.md` file, delete the duplicate conflict copy once reconciled and re-run `oude digest`.
2. **Migrate, re-index, and validate:**

```bash
oude doctor --fix                      # rewrites legacy entity_type keys to canonical type (reports conflicts)
oude digest                            # recompiles .agents/context/references.json with canonical "type"
oude digest --validate _gm-materials/digests
```

3. **Local / self-hosted `oude doctor` exit-1 note:** standard public vault Continuous Integration (CI) skips the check when `_gm-materials/digests/` is absent, whereas local hooks or self-hosted runners mounting `_gm-materials/` will exit `1` until `oude doctor --fix` finishes. Unmigrated `entity_type` notes still pass `oude digest --validate` with a non-fatal `[WARN]`.
4. **Immediate `.agents/context/references.json` field rename:** `compile_references()` immediately emits `"type"` instead of `"entity_type"` (and omits `"type"` with a stderr `[WARN]` when absent or invalid). Update any vault-local script reading `entry["entity_type"]` to read `entry["type"]`.
5. **Rollback:** downgrading the engine restores `entity_type` validation and rejects migrated `type:` notes; roll back from your Step 1 snapshot if reverting.

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
