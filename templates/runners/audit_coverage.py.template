#!/usr/bin/env python3
"""Runner delegating to oude-mechanismen audit_coverage.py."""
import subprocess
import sys
from pathlib import Path

repo_root = Path(__file__).resolve().parents[2]

core_script = repo_root.parent / "oude-mechanismen" / "scripts" / "audit_coverage.py"
if not core_script.exists():
    core_script = Path("/Users/efsa/Repos/oude-mechanismen/scripts/audit_coverage.py")

if not core_script.exists():
    print(f"Error: {core_script} not found.", file=sys.stderr)
    sys.exit(1)

venv_python = repo_root / ".agents" / "venv" / "bin" / "python3"
python_bin = str(venv_python) if venv_python.exists() else sys.executable

args = list(sys.argv[1:])
if not any(arg in args for arg in ("--repo-root", "--repo-dir")):
    args = ["--repo-dir", str(repo_root)] + args

sys.exit(subprocess.call([python_bin, str(core_script)] + args, cwd=str(repo_root)))
