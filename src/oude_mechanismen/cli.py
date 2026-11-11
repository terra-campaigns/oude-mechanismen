#!/usr/bin/env python3
"""Command-line interface for the oude-mechanismen procedural engine.

Provides CLI subcommands for campaign vault initialisation, global skill
management, health diagnostics, and pass-through execution of bundled scripts.
All messages and documentation strictly adhere to British English.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple

try:
    from oude_mechanismen import ENGINE_ROOT, PACKAGE_DIR, __version__, resolve_asset_dir
except ImportError:
    # Allow running src/oude_mechanismen/cli.py directly in development
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from oude_mechanismen import ENGINE_ROOT, PACKAGE_DIR, __version__, resolve_asset_dir

# XDG data directory specification
XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
SKILLS_TARGET_DIR = XDG_DATA_HOME / "oude-mechanismen" / "skills"
GEMINI_CONFIG_DIR = Path.home() / ".gemini" / "config"
GEMINI_SKILLS_FILE = GEMINI_CONFIG_DIR / "skills.json"

# Directory topology for init subcommand
REPO_DIRECTORIES = [
    "campaigns",
    "directory",
    "systems",
    "imgs/gallery",
    "imgs/badges",
    "_sass/custom",
    ".agents/context",
]

# Standard template mappings (source relative to engine : target relative to vault)
TEMPLATE_MAPPINGS = [
    ("templates/AGENTS.md.template", ".agents/AGENTS.md"),
    ("templates/tier1_sources.yml.template", ".agents/context/tier1_sources.yml"),
    ("templates/decisions.md.template", ".agents/context/decisions.md"),
    ("templates/aesthetics.yml.template", ".agents/context/aesthetics.yml"),
    ("templates/route_graph.json.template", ".agents/context/route_graph.json"),
    ("templates/jekyll/_config.yml.template", "_config.yml"),
    ("templates/jekyll/Gemfile.template", "Gemfile"),
    ("templates/jekyll/_sass/custom/custom.scss.template", "_sass/custom/custom.scss"),
    ("templates/jekyll/index.md.template", "index.md"),
    ("templates/jekyll/directory_index.md.template", "directory/index.md"),
    ("templates/jekyll/campaigns_index.md.template", "campaigns/index.md"),
    ("templates/jekyll/systems_index.md.template", "systems/index.md"),
    ("jekyll/all-content.md", "all-content.md"),
]

# Pass-through script mappings (command name : filename in scripts/)
PASS_THROUGH_SCRIPTS = {
    "lint": "lint_chapter.py",
    "audit": "audit_coverage.py",
    "digest": "generate_digests.py",
    "harvest": "harvest_archival.py",
    "filter": "art_filter.py",
    "transcribe": "transcribe_session.py",
    "scribe": "scribe_session.py",
    "benchmark": "benchmark_models.py",
}

# Standard .gitignore content
DEFAULT_GITIGNORE = """_site/
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
"""


def _copy_if_missing(src: Path, dst: Path) -> bool:
    """Copy a file if the destination does not already exist (no-clobber)."""
    if dst.is_file():
        return False
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return True


def _ensure_gitignore(target: Path) -> None:
    """Scaffold a standard .gitignore file if missing."""
    gitignore_path = target / ".gitignore"
    if not gitignore_path.exists():
        gitignore_path.write_text(DEFAULT_GITIGNORE, encoding="utf-8")


def _enable_auto_branch_deletion(target: Path) -> bool:
    """Opportunistically enable automatic branch deletion on merge via gh CLI."""
    if not shutil.which("gh"):
        return False

    try:
        remote_check = subprocess.run(
            ["git", "-C", str(target), "config", "--get", "remote.origin.url"],
            capture_output=True,
            text=True,
        )
        if remote_check.returncode != 0 or not remote_check.stdout.strip():
            return False

        res = subprocess.run(
            ["gh", "repo", "edit", "--delete-branch-on-merge"],
            cwd=str(target),
            capture_output=True,
            text=True,
        )
        return res.returncode == 0
    except Exception:
        return False


def _init_repository(target_path: Path) -> int:
    """Initialise a campaign repository with directory topology and starter templates."""
    abs_repo = target_path.resolve()
    abs_repo.mkdir(parents=True, exist_ok=True)
    print(f"==> Initialising campaign vault at {abs_repo}...")

    # 1. Directory topology
    for dir_rel in REPO_DIRECTORIES:
        (abs_repo / dir_rel).mkdir(parents=True, exist_ok=True)

    # 2. Starter template scaffolding (no-clobber)
    for src_rel, dst_rel in TEMPLATE_MAPPINGS:
        src = resolve_asset_dir(src_rel)
        if not src.exists():
            # Fallback relative to package templates if structured differently
            src = resolve_asset_dir("templates") / Path(src_rel).name
        dst = abs_repo / dst_rel
        if src.is_file() and _copy_if_missing(src, dst):
            print(f"  + Scaffolded {dst_rel}")

    # 3. Fallback badges
    badge_source = resolve_asset_dir("templates/badges")
    if not badge_source.is_dir():
        badge_source = resolve_asset_dir("templates") / "badges"

    badge_dest = abs_repo / "imgs" / "badges"
    badge_dest.mkdir(parents=True, exist_ok=True)
    if badge_source.is_dir():
        for badge_file in badge_source.glob("*.png"):
            dst = badge_dest / badge_file.name
            if not dst.exists():
                shutil.copy2(badge_file, dst)

    # 4. Standard .gitignore
    _ensure_gitignore(abs_repo)

    # 5. Remote branch deletion on merge
    if _enable_auto_branch_deletion(abs_repo):
        print("  ✓ Enabled --delete-branch-on-merge for remote repository")

    # 6. Global skills synchronisation
    _install_skills()

    print(f"==> Campaign vault initialisation complete: {abs_repo}")
    return 0


def _load_gemini_skills_config() -> Optional[dict]:
    """Load or initialise the global Gemini skills.json configuration.

    Returns:
        The parsed configuration dictionary, an empty template dictionary if
        the file does not exist, or None if the configuration file is corrupted.
    """
    if not GEMINI_SKILLS_FILE.is_file():
        return {"entries": []}
    try:
        return json.loads(GEMINI_SKILLS_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        backup_path = GEMINI_SKILLS_FILE.with_suffix(".json.corrupt.bak")
        try:
            shutil.copy2(GEMINI_SKILLS_FILE, backup_path)
            backup_msg = f" Created backup at {backup_path}."
        except Exception:
            backup_msg = ""
        print(
            f"Error: Corrupted skills configuration at {GEMINI_SKILLS_FILE}: {e}.{backup_msg} "
            "Refusing to overwrite.",
            file=sys.stderr,
        )
        return None


def _save_gemini_skills_config(config: dict) -> None:
    """Persist the global Gemini skills.json configuration."""
    GEMINI_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    GEMINI_SKILLS_FILE.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")


def _sync_skills() -> int:
    """Synchronise bundled skills into XDG data directory."""
    source_skills = resolve_asset_dir("skills")
    if not source_skills.is_dir():
        print(f"Error: Source skills directory not found at {source_skills}", file=sys.stderr)
        return 1

    SKILLS_TARGET_DIR.parent.mkdir(parents=True, exist_ok=True)
    for skill_dir in source_skills.iterdir():
        if skill_dir.is_dir() and not skill_dir.name.startswith("."):
            dest_dir = SKILLS_TARGET_DIR / skill_dir.name
            if dest_dir.exists():
                shutil.rmtree(dest_dir)
            shutil.copytree(skill_dir, dest_dir, dirs_exist_ok=True)

    return 0


def _register_skills_path() -> int:
    """Register XDG skills directory into ~/.gemini/config/skills.json idempotently."""
    target_str = str(SKILLS_TARGET_DIR.resolve())
    config = _load_gemini_skills_config()
    if config is None:
        return 1

    entries = config.get("entries", [])
    if not isinstance(entries, list):
        print(
            f"Error: Expected 'entries' array in {GEMINI_SKILLS_FILE}, found {type(entries).__name__}.",
            file=sys.stderr,
        )
        return 1

    # Check if already present
    for entry in entries:
        if isinstance(entry, dict) and entry.get("path") == target_str:
            return 0

    entries.append({"path": target_str})
    config["entries"] = entries
    _save_gemini_skills_config(config)
    return 0


def _install_skills() -> int:
    """Synchronise bundled skills to XDG data directory and register in Gemini config."""
    if _sync_skills() != 0:
        return 1
    if _register_skills_path() != 0:
        return 1
    print(f"  ✓ Synchronised skills to {SKILLS_TARGET_DIR}")
    print(f"  ✓ Registered skills in {GEMINI_SKILLS_FILE}")
    return 0


def _doctor(target_path: Optional[Path] = None, fix: bool = False) -> int:
    """Audit campaign vault health, tool dependencies, and skills registration."""
    vault = (target_path or Path.cwd()).resolve()
    print(f"Oude Mechanismen v{__version__} — Campaign Diagnostics")
    print(f"  Target vault: {vault}\n")

    all_passed = True

    # 1. Check essential vault configuration files
    print("Checking campaign configuration:")
    config_yml_path = vault / "_config.yml"
    if config_yml_path.is_file():
        config_content = config_yml_path.read_text(encoding="utf-8")
        if re.search(r"(?m)^[ \t]*-[ \t]*oude-mechanismen\b", config_content):
            print("  ✓ Jekyll configuration (_config.yml)")
        elif fix:
            print("  ✓ Adding oude-mechanismen to plugins in _config.yml...")
            if re.search(r"(?m)^plugins:[ \t]*\n", config_content):
                new_content = re.sub(
                    r"(?m)^(plugins:[ \t]*\n)",
                    r"\1  - oude-mechanismen\n",
                    config_content,
                    count=1,
                )
            else:
                new_content = config_content.rstrip() + "\n\nplugins:\n  - oude-mechanismen\n"
            config_yml_path.write_text(new_content, encoding="utf-8")
        else:
            print("  ⚠ Jekyll configuration (_config.yml) is missing oude-mechanismen under plugins")
            all_passed = False
    else:
        print("  ✗ Missing: Jekyll configuration (_config.yml)")
        all_passed = False

    for path, desc in [
        (vault / "Gemfile", "Bundler configuration (Gemfile)"),
        (vault / ".agents" / "AGENTS.md", "Agent instructions (.agents/AGENTS.md)"),
        (vault / ".agents" / "context" / "tier1_sources.yml", "Tier 1 sources (tier1_sources.yml)"),
    ]:
        if path.is_file():
            print(f"  ✓ {desc}")
        else:
            print(f"  ✗ Missing: {desc}")
            all_passed = False

    # 2. Check for legacy files (collisions/shadowing)
    for rel_str in ("_plugins/data_extractor.rb", "_plugins/llm_content.rb", ".agents/venv"):
        legacy_path = vault / rel_str
        if legacy_path.exists():
            if fix:
                shutil.rmtree(legacy_path) if legacy_path.is_dir() else legacy_path.unlink()
                print(f"  ✓ Removed legacy file: {rel_str}")
            else:
                print(f"  ⚠ Legacy file detected: {rel_str}")
                all_passed = False

    plugins_dir = vault / "_plugins"
    if fix and plugins_dir.is_dir() and not any(plugins_dir.iterdir()):
        plugins_dir.rmdir()

    # 3. Check catalog.json and engine version
    catalog_path = vault / ".agents" / "context" / "catalog.json"
    engine_ver = None
    if catalog_path.is_file():
        try:
            data = json.loads(catalog_path.read_text(encoding="utf-8"))
            engine_ver = data.get("engine_version") or data.get("metadata", {}).get("engine_version")
        except Exception as e:
            print(f"  ✗ Corrupted catalog.json: {e}")

    if engine_ver:
        print(f"  ✓ Tier 1 catalogue compiled (engine_version: {engine_ver})")
    elif fix and shutil.which("bundle"):
        print("  -> Regenerating catalogue with engine_version via 'bundle exec jekyll build'...")
        res = subprocess.run(["bundle", "exec", "jekyll", "build"], cwd=str(vault), capture_output=True, text=True)
        if res.returncode == 0:
            print("  ✓ Recompiled Jekyll site and refreshed catalogue")
        else:
            print(f"  ✗ Rebuild failed: {res.stderr.strip() or res.stdout.strip()}")
            all_passed = False
    else:
        status = "compiled but lacks engine_version metadata" if catalog_path.is_file() else "not yet generated"
        print(f"  ⚠ Tier 1 catalogue {status}")
        all_passed = False

    # 4. Check CLI tool dependencies
    print("\nChecking external tool dependencies:")
    tools = [
        ("whisper-cli", "Whisper speech-to-text (whisper.cpp)"),
        ("ffmpeg", "Audio normalisation utility"),
        ("ollama", "Local LLM sovereign runtime"),
    ]
    for tool_cmd, tool_desc in tools:
        found_path = shutil.which(tool_cmd)
        if found_path:
            print(f"  ✓ {tool_desc}: {found_path}")
        else:
            print(f"  ⚠ Not found in PATH: {tool_cmd} ({tool_desc})")

    # 5. Check global skills registration
    print("\nChecking agent skills registration:")
    skills_registered = False
    target_str = str(SKILLS_TARGET_DIR.resolve())
    if GEMINI_SKILLS_FILE.is_file():
        config = _load_gemini_skills_config()
        if config is None:
            print(f"  ✗ Corrupted skills configuration at {GEMINI_SKILLS_FILE}")
            all_passed = False
        else:
            for entry in config.get("entries", []):
                if isinstance(entry, dict) and entry.get("path") == target_str:
                    skills_registered = True
                    break

    if skills_registered:
        print(f"  ✓ Global skills path registered: {target_str}")
    elif GEMINI_SKILLS_FILE.is_file() and config is not None:
        print(f"  ⚠ Skills path not registered in {GEMINI_SKILLS_FILE}. Run `oude install-skills` to register.")
    elif not GEMINI_SKILLS_FILE.is_file():
        print(f"  ⚠ Skills configuration not yet created at {GEMINI_SKILLS_FILE}. Run `oude install-skills` to initialise.")

    print("")
    return 0 if all_passed else 1


def _run_script(script_name: str, extra_args: List[str]) -> int:
    """Execute a pass-through procedural script with PYTHONPATH set to scripts/."""
    scripts_dir = resolve_asset_dir("scripts")
    script_path = scripts_dir / script_name

    if not script_path.is_file():
        print(f"Error: Script '{script_name}' not found at {script_path}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PYTHONPATH"] = f"{scripts_dir}:{env.get('PYTHONPATH', '')}"

    cmd = [sys.executable, str(script_path)] + extra_args
    result = subprocess.run(cmd, env=env)
    return result.returncode


def main(argv: Optional[List[str]] = None) -> int:
    """Main CLI entrypoint for oude."""
    parser = argparse.ArgumentParser(
        prog="oude",
        description="Oude Mechanismen — procedural engine and CLI tooling for tabletop RPG campaign vaults.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"oude-mechanismen {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # 1. init
    p_init = subparsers.add_parser("init", help="Initialise a new campaign vault repository")
    p_init.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Destination directory for the campaign vault (default: current directory)",
    )

    # 2. install-skills
    subparsers.add_parser(
        "install-skills",
        help="Synchronise bundled skills into user XDG directory and register in ~/.gemini/config/skills.json",
    )

    # 3. doctor
    p_doc = subparsers.add_parser(
        "doctor",
        help="Audit campaign vault configuration, tools, and skills health",
    )
    p_doc.add_argument(
        "--vault",
        help="Path to target campaign vault directory (default: current directory)",
    )
    p_doc.add_argument(
        "--fix",
        action="store_true",
        help="Automatically remediate legacy plugins, missing config, and rebuild catalogue",
    )

    # 4. Pass-through scripts
    for cmd_name, script_file in PASS_THROUGH_SCRIPTS.items():
        subparsers.add_parser(
            cmd_name,
            help=f"Execute {script_file}",
            add_help=False,
        )

    args, extra_args = parser.parse_known_args(argv)

    if args.command == "init":
        return _init_repository(Path(args.path))
    if args.command == "install-skills":
        return _install_skills()
    if args.command == "doctor":
        target = Path(args.vault) if getattr(args, "vault", None) else None
        return _doctor(target, args.fix)
    if args.command in PASS_THROUGH_SCRIPTS:
        return _run_script(PASS_THROUGH_SCRIPTS[args.command], extra_args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
