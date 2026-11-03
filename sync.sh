#!/usr/bin/env bash
#
# sync.sh — Synchronise the oude-mechanismen engine with downstream campaign repositories.
#
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CHECK_MODE=false
DIFF_MODE=false
FORCE_MODE=false
INIT_MODE=false
TARGET_REPOS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --check|--dry-run)
      CHECK_MODE=true
      shift
      ;;
    --diff)
      DIFF_MODE=true
      shift
      ;;
    --force)
      FORCE_MODE=true
      shift
      ;;
    --init)
      INIT_MODE=true
      shift
      ;;
    -h|--help)
      echo "Usage: ./sync.sh [OPTIONS] <path_to_campaign_repo_1> [path_to_campaign_repo_2 ...]"
      echo ""
      echo "Options:"
      echo "  --init              Initialise a new or existing vault with starter templates, badges, and folders"
      echo "  --check, --dry-run  Inspect status without making changes"
      echo "  --diff              Display unified diffs for outdated or modified files"
      echo "  --force             Overwrite files even if destination has uncommitted changes"
      echo "  -h, --help          Show this help message"
      exit 0
      ;;
    -*)
      echo "Error: Unknown option $1"
      exit 1
      ;;
    *)
      TARGET_REPOS+=("$1")
      shift
      ;;
  esac
done

if [ ${#TARGET_REPOS[@]} -eq 0 ]; then
  if [ "$PWD" != "$SCRIPT_DIR" ]; then
    TARGET_REPOS=(".")
  else
    echo "Usage: ./sync.sh [--init] [--check] [--diff] [--force] <path_to_campaign_repo_1> [path_to_campaign_repo_2 ...]"
    exit 1
  fi
fi

# Manifest of engine-managed files:
# Format: "source_in_engine:destination_in_vault:is_executable"
MANAGED_FILES=(
  "jekyll/_plugins/data_extractor.rb:_plugins/data_extractor.rb:false"
  "jekyll/_plugins/llm_content.rb:_plugins/llm_content.rb:false"
  "jekyll/_includes/connected_to.html:_includes/connected_to.html:false"
  "jekyll/_includes/header_chapter.md:_includes/header_chapter.md:false"
  "jekyll/_includes/header_directories.md:_includes/header_directories.md:false"
  "jekyll/_includes/image_gallery.html:_includes/image_gallery.html:false"
  "jekyll/all-content.md:all-content.md:false"
  "githooks/pre-commit:.githooks/pre-commit:true"
  "requirements.txt:.agents/requirements.txt:false"
  "templates/runners/generate_digests.py.template:.agents/scripts/generate_digests.py:true"
  "templates/runners/audit_coverage.py.template:.agents/scripts/audit_coverage.py:true"
  "templates/runners/transcribe_session.py.template:.agents/scripts/transcribe_session.py:true"
  "templates/runners/art_filter.py.template:.agents/scripts/art_filter.py:true"
  "templates/bin/setup.template:bin/setup:true"
)

TOTAL_OUTDATED=0

for REPO in "${TARGET_REPOS[@]}"; do
  if [ "$INIT_MODE" = true ] && [ ! -d "$REPO" ]; then
    mkdir -p "$REPO"
  elif [ ! -d "$REPO" ]; then
    echo "Warning: Directory $REPO does not exist. Skipping (use --init to create)."
    continue
  fi

  ABS_REPO="$(cd "$REPO" && pwd)"

  # Handle vault initialisation
  if [ "$INIT_MODE" = true ]; then
    echo "==> Initialising campaign vault at $ABS_REPO..."
    mkdir -p "$ABS_REPO/campaigns" \
             "$ABS_REPO/directory" \
             "$ABS_REPO/systems" \
             "$ABS_REPO/imgs/gallery" \
             "$ABS_REPO/imgs/badges" \
             "$ABS_REPO/_sass/custom" \
             "$ABS_REPO/.agents/context"

    scaffold_if_missing() {
      local src="$1"
      local dest="$2"
      if [ ! -f "$dest" ] && [ -f "$src" ]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        local rel_dest="${dest#"$ABS_REPO"/}"
        echo "  + Scaffolded $rel_dest"
      fi
    }

    scaffold_if_missing "$SCRIPT_DIR/templates/AGENTS.md.template" "$ABS_REPO/.agents/AGENTS.md"
    scaffold_if_missing "$SCRIPT_DIR/templates/tier1_sources.yml.template" "$ABS_REPO/.agents/context/tier1_sources.yml"
    scaffold_if_missing "$SCRIPT_DIR/templates/decisions.md.template" "$ABS_REPO/.agents/context/decisions.md"
    scaffold_if_missing "$SCRIPT_DIR/templates/aesthetics.yml.template" "$ABS_REPO/.agents/context/aesthetics.yml"
    scaffold_if_missing "$SCRIPT_DIR/templates/route_graph.json.template" "$ABS_REPO/.agents/context/route_graph.json"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/_config.yml.template" "$ABS_REPO/_config.yml"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/Gemfile.template" "$ABS_REPO/Gemfile"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/_sass/custom/custom.scss.template" "$ABS_REPO/_sass/custom/custom.scss"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/index.md.template" "$ABS_REPO/index.md"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/directory_index.md.template" "$ABS_REPO/directory/index.md"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/campaigns_index.md.template" "$ABS_REPO/campaigns/index.md"
    scaffold_if_missing "$SCRIPT_DIR/templates/jekyll/systems_index.md.template" "$ABS_REPO/systems/index.md"

    # Configure skills discovery pointing to engine path
    if [ ! -f "$ABS_REPO/.agents/skills.json" ]; then
      cat << EOF > "$ABS_REPO/.agents/skills.json"
{
  "entries": [
    {
      "path": "$SCRIPT_DIR/skills"
    },
    {
      "path": "../oude-mechanismen/skills"
    },
    {
      "path": "~/Repos/oude-mechanismen/skills"
    }
  ]
}
EOF
      echo "  + Scaffolded .agents/skills.json (pointing to $SCRIPT_DIR/skills)"
    fi

    # Copy fallback badges if missing
    if [ -d "$SCRIPT_DIR/templates/badges" ]; then
      for badge in "$SCRIPT_DIR/templates/badges"/*.png; do
        if [ -f "$badge" ]; then
          bname="$(basename "$badge")"
          if [ ! -f "$ABS_REPO/imgs/badges/$bname" ]; then
            cp "$badge" "$ABS_REPO/imgs/badges/$bname"
            echo "  + Scaffolded fallback badge: imgs/badges/$bname"
          fi
        fi
      done
    fi

    # Create default starter .gitignore if missing
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
EOF
      echo "  + Scaffolded .gitignore"
    fi
  fi

  echo "==> Auditing oude-mechanismen engine against $ABS_REPO..."

  # Remove obsolete legacy files if present
  if [ -f "$ABS_REPO/all-agent.md" ] && [ "$CHECK_MODE" = false ]; then
    rm -f "$ABS_REPO/all-agent.md" "$ABS_REPO/_site/all-agent.html"
    echo "  - Removed obsolete all-agent.md"
  fi

  DIRTY_COUNT=0
  OUTDATED_COUNT=0
  NEW_COUNT=0
  SYNCED_COUNT=0

  for ITEM in "${MANAGED_FILES[@]}"; do
    SRC_REL="${ITEM%%:*}"
    REST="${ITEM#*:}"
    DEST_REL="${REST%%:*}"
    IS_EXEC="${REST#*:}"

    SRC="$SCRIPT_DIR/$SRC_REL"
    DEST="$ABS_REPO/$DEST_REL"

    if [ ! -f "$SRC" ]; then
      echo "  [ERROR] Source file missing in engine: $SRC_REL"
      continue
    fi

    if [ ! -f "$DEST" ]; then
      NEW_COUNT=$((NEW_COUNT + 1))
      STATUS="NEW"
    elif cmp -s "$SRC" "$DEST"; then
      SYNCED_COUNT=$((SYNCED_COUNT + 1))
      STATUS="IN_SYNC"
    else
      # File exists and differs
      # Check if destination has local unstaged or uncommitted changes in git
      IS_DIRTY=false
      if git -C "$ABS_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        if [ -n "$(git -C "$ABS_REPO" status --porcelain "$DEST_REL" 2>/dev/null)" ]; then
          IS_DIRTY=true
        fi
      fi

      if [ "$IS_DIRTY" = true ]; then
        DIRTY_COUNT=$((DIRTY_COUNT + 1))
        STATUS="DIRTY"
      else
        OUTDATED_COUNT=$((OUTDATED_COUNT + 1))
        STATUS="OUTDATED"
      fi
    fi

    # Handle --diff output
    if [ "$DIFF_MODE" = true ] && [ "$STATUS" != "IN_SYNC" ]; then
      echo "--- Diff for $DEST_REL ($STATUS) ---"
      if [ -f "$DEST" ]; then
        diff -u "$DEST" "$SRC" || true
      else
        echo "(Destination file does not exist yet)"
      fi
      echo "-----------------------------------"
    fi

    # Handle reporting or execution
    if [ "$CHECK_MODE" = true ]; then
      case "$STATUS" in
        IN_SYNC)
          echo "  [IN SYNC]  $DEST_REL"
          ;;
        NEW)
          echo "  [NEW]      $DEST_REL (missing in campaign vault)"
          ;;
        OUTDATED)
          echo "  [OUTDATED] $DEST_REL (engine has updates)"
          ;;
        DIRTY)
          echo "  [DIRTY]    $DEST_REL (target vault has local uncommitted modifications)"
          ;;
      esac
    else
      # Real sync mode
      case "$STATUS" in
        IN_SYNC)
          # Ensure executable bits are preserved even if content matches
          if [ "$IS_EXEC" = "true" ] && [ ! -x "$DEST" ]; then
            chmod +x "$DEST"
          fi
          ;;
        NEW|OUTDATED)
          mkdir -p "$(dirname "$DEST")"
          cp "$SRC" "$DEST"
          if [ "$IS_EXEC" = "true" ]; then
            chmod +x "$DEST"
          fi
          echo "  ✓ Updated $DEST_REL"
          ;;
        DIRTY)
          if [ "$FORCE_MODE" = true ]; then
            mkdir -p "$(dirname "$DEST")"
            cp "$SRC" "$DEST"
            if [ "$IS_EXEC" = "true" ]; then
              chmod +x "$DEST"
            fi
            echo "  ✓ [FORCED] Overwrote $DEST_REL (was dirty)"
          else
            echo "  ⚠ [SKIPPED] $DEST_REL has local modifications in $ABS_REPO. Pass --force to overwrite."
          fi
          ;;
      esac
    fi
  done

  TOTAL_OUTDATED=$((TOTAL_OUTDATED + OUTDATED_COUNT + NEW_COUNT + DIRTY_COUNT))

  if [ "$CHECK_MODE" = false ]; then
    # Stamp engine version
    ENGINE_VERSION="$(cat "$SCRIPT_DIR/VERSION" 2>/dev/null || echo "0.1.0")"
    ENGINE_COMMIT="$(git -C "$SCRIPT_DIR" rev-parse --short HEAD 2>/dev/null || echo "unknown")"
    mkdir -p "$ABS_REPO/.agents"
    echo "${ENGINE_VERSION} (${ENGINE_COMMIT})" > "$ABS_REPO/.agents/.engine-version"

    # Configure git hooks in target repository
    if git -C "$ABS_REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
      git -C "$ABS_REPO" config core.hooksPath .githooks 2>/dev/null || true
    fi
    echo "  ✓ Engine sync complete for $ABS_REPO ($((NEW_COUNT + OUTDATED_COUNT)) updated, $DIRTY_COUNT skipped)."

    # Automatically run bin/setup if initialising
    if [ "$INIT_MODE" = true ] && [ -x "$ABS_REPO/bin/setup" ]; then
      echo "==> Running bin/setup in $ABS_REPO..."
      (cd "$ABS_REPO" && ./bin/setup) || true
    fi
  else
    echo "  Summary: $SYNCED_COUNT in-sync, $OUTDATED_COUNT outdated, $NEW_COUNT new, $DIRTY_COUNT dirty."
  fi
done

if [ "$CHECK_MODE" = true ] && [ "$TOTAL_OUTDATED" -gt 0 ]; then
  exit 2
fi
