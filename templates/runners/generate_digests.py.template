#!/usr/bin/env python3
"""Runner delegating to oude-mechanismen generate_digests.py."""
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]

core_script = repo_root.parent / "oude-mechanismen" / "scripts" / "generate_digests.py"
if not core_script.exists():
    core_script = Path("/Users/efsa/Repos/oude-mechanismen/scripts/generate_digests.py")

if not core_script.exists():
    print(f"Error: {core_script} not found.", file=sys.stderr)
    sys.exit(1)

args = list(sys.argv[1:])
if not any(arg in args for arg in ("--repo-root", "--repo-dir")):
    args = ["--repo-root", str(repo_root)] + args

sys.exit(subprocess.call([sys.executable, str(core_script)] + args, cwd=str(repo_root)))
