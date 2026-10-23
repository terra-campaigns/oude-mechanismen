#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_REPOS=("$@")

if [ ${#TARGET_REPOS[@]} -eq 0 ]; then
  echo "Usage: ./sync.sh <path_to_campaign_repo_1> [path_to_campaign_repo_2 ...]"
  exit 1
fi

for REPO in "${TARGET_REPOS[@]}"; do
  if [ ! -d "$REPO" ]; then
    echo "Warning: Directory $REPO does not exist. Skipping."
    continue
  fi

  ABS_REPO="$(cd "$REPO" && pwd)"
  echo "==> Syncing oude-mechanismen engine to $ABS_REPO..."

  # 1. Jekyll Plugins
  mkdir -p "$ABS_REPO/_plugins"
  cp "$SCRIPT_DIR/jekyll/_plugins/data_extractor.rb" "$ABS_REPO/_plugins/"
  cp "$SCRIPT_DIR/jekyll/_plugins/llm_content.rb" "$ABS_REPO/_plugins/"

  # 2. Shared Jekyll Includes (preserves repo-specific footers and calendars)
  mkdir -p "$ABS_REPO/_includes"
  cp "$SCRIPT_DIR/jekyll/_includes/connected_to.html" "$ABS_REPO/_includes/"
  cp "$SCRIPT_DIR/jekyll/_includes/header_chapter.md" "$ABS_REPO/_includes/"
  cp "$SCRIPT_DIR/jekyll/_includes/header_directories.md" "$ABS_REPO/_includes/"
  cp "$SCRIPT_DIR/jekyll/_includes/image_gallery.html" "$ABS_REPO/_includes/"

  # 3. Dynamic content dump
  rm -f "$ABS_REPO/all-agent.md" "$ABS_REPO/_site/all-agent.html"
  cp "$SCRIPT_DIR/jekyll/all-content.md" "$ABS_REPO/all-content.md"

  # 4. Git hook
  mkdir -p "$ABS_REPO/.githooks"
  cp "$SCRIPT_DIR/githooks/pre-commit" "$ABS_REPO/.githooks/pre-commit"
  chmod +x "$ABS_REPO/.githooks/pre-commit"
  git -C "$ABS_REPO" config core.hooksPath .githooks 2>/dev/null || true

  echo "  ✓ Engine files and pre-commit hook synced to $ABS_REPO."
done

echo "==> All target repositories synced successfully."
