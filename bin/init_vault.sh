#!/usr/bin/env bash
#
# init_vault.sh — Idempotent one-time campaign vault bootstrapper.
#
# DEPRECATED: use `oude init <target>` (src/oude_mechanismen/cli.py) instead.
# Retained temporarily while legacy references and tests (tests/test_init_vault.py) remain.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_REPO="${1:-.}"
ABS_REPO="$(mkdir -p "$TARGET_REPO" && cd "$TARGET_REPO" && pwd)"

echo "==> Initialising campaign vault at $ABS_REPO..."

# 1. Directory topology
mkdir -p "$ABS_REPO/campaigns" "$ABS_REPO/directory" "$ABS_REPO/systems" \
         "$ABS_REPO/imgs/gallery" "$ABS_REPO/imgs/badges" \
         "$ABS_REPO/_sass/custom" "$ABS_REPO/.agents/context" \
         "$ABS_REPO/_gm-materials"

# 2. Starter template scaffolding (no-clobber)
MAPPINGS=(
  "templates/AGENTS.md.template:.agents/AGENTS.md"
  "templates/tier1_sources.yml.template:.agents/context/tier1_sources.yml"
  "templates/decisions.md.template:.agents/context/decisions.md"
  "templates/aesthetics.yml.template:.agents/context/aesthetics.yml"
  "templates/route_graph.json.template:.agents/context/route_graph.json"
  "templates/jekyll/_config.yml.template:_config.yml"
  "templates/jekyll/Gemfile.template:Gemfile"
  "templates/jekyll/_sass/custom/custom.scss.template:_sass/custom/custom.scss"
  "templates/jekyll/index.md.template:index.md"
  "templates/jekyll/directory_index.md.template:directory/index.md"
  "templates/jekyll/campaigns_index.md.template:campaigns/index.md"
  "templates/jekyll/systems_index.md.template:systems/index.md"
)

for item in "${MAPPINGS[@]}"; do
  src="$SCRIPT_DIR/${item%%:*}"
  dest="$ABS_REPO/${item##*:}"
  [ -f "$dest" ] || { cp "$src" "$dest" && echo "  + Scaffolded ${item##*:}"; }
done

# 3. Fallback badges & default gitignore
cp -n "$SCRIPT_DIR/templates/badges"/*.png "$ABS_REPO/imgs/badges/" 2>/dev/null || true

if [ ! -f "$ABS_REPO/.gitignore" ]; then
  cat << 'EOF' > "$ABS_REPO/.gitignore"
_site/
.jekyll-cache/
.sass-cache/
.DS_Store
.agents/venv/
__pycache__/
*.pyc
.env
.bundle/
vendor/
*_studio.html
*_preview_*.png
*_raw.*
# Private GM materials (session summaries, session preps, digests)
_gm-materials/
EOF
  echo "  + Scaffolded .gitignore"
fi

# 4. GitHub remote branch hygiene (if repo has a remote and gh is available)
if command -v gh >/dev/null 2>&1 && git -C "$ABS_REPO" config --get remote.origin.url >/dev/null 2>&1; then
  echo "  ==> Configuring GitHub repository settings for $ABS_REPO..."
  if (cd "$ABS_REPO" && gh repo edit --delete-branch-on-merge >/dev/null 2>&1); then
    echo "  ✓ Enabled --delete-branch-on-merge for remote repository"
  fi
fi

# 5. Smoke-validate the deterministic wiki linter (Gate 3) if the oude CLI is installed
if command -v oude >/dev/null 2>&1; then
  if (cd "$ABS_REPO" && oude lint-wiki --format json >/dev/null 2>&1); then
    echo "  ✓ Wiki lint clean (oude lint-wiki)"
  else
    echo "  ℹ 'oude lint-wiki' reports findings (e.g. missing catalog.json); run it before publishing (Gate 3)."
  fi
else
  echo "  ℹ oude CLI not found; install it to run 'oude lint-wiki' (Gate 3) before publishing."
fi

echo "==> Campaign vault initialisation complete: $ABS_REPO"
