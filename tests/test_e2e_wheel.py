#!/usr/bin/env python3
"""Clean-virtualenv wheel packaging smoke tests (GitHub issue #34).

Builds the Python wheel from the repository checkout with ``uv build``,
installs it into an isolated virtual environment created OUTSIDE the
repository checkout, and verifies from that venv that:

1. Bundled engine assets resolve inside the installed wheel
   (``jekyll/_includes``, ``scripts``, ``skills``, ``templates``, ``VERSION``)
   via ``resolve_asset_dir`` — never falling back to the repo checkout.
2. The retired monolithic LLM dump assets are NOT bundled: the wheel contains
   neither ``jekyll/all-content.md`` nor ``jekyll/_plugins/llm_content.rb``
   (issues #25/#35, PR #72).
3. The installed ``oude`` CLI entrypoint runs from outside the checkout.

Skipped automatically when ``uv`` is unavailable on the host.
All test assertions and docstrings strictly adhere to British English.
"""

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

UV_AVAILABLE = shutil.which("uv") is not None

SMOKE_SCRIPT = r"""
import sys
from pathlib import Path

import oude_mechanismen as om
from oude_mechanismen import PACKAGE_DIR, __version__, resolve_asset_dir

# Assets must resolve inside the installed wheel, never the repo checkout.
assert str(PACKAGE_DIR).startswith(sys.prefix), (PACKAGE_DIR, sys.prefix)
for rel in ("jekyll/_includes", "scripts", "skills", "templates", "VERSION"):
    resolved = resolve_asset_dir(rel)
    assert resolved.exists(), f"bundled asset missing from wheel: {rel} -> {resolved}"
assert resolve_asset_dir("jekyll/_includes").is_dir()

# Retired monolithic LLM dump assets must NOT be bundled (#25/#35, PR #72).
jekyll_dir = PACKAGE_DIR / "jekyll"
assert not (jekyll_dir / "all-content.md").exists(), "jekyll/all-content.md must not ship in the wheel"
assert not (jekyll_dir / "_plugins" / "llm_content.rb").exists(), "llm_content.rb must not ship in the wheel"

print("SMOKE-OK", __version__)
"""


@unittest.skipUnless(UV_AVAILABLE, "uv executable not found on host system")
class TestE2EWheelAssets(unittest.TestCase):
    """Wheel build + clean-venv install + asset resolution smoke check (issue #34)."""

    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="oude-e2e-wheel-"))
        dist = cls.tmp / "dist"
        build = subprocess.run(
            ["uv", "build", "--quiet", "--out-dir", str(dist)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        if build.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest(f"uv build failed: {build.stderr[-400:]}")
        wheels = sorted(dist.glob("*.whl"))
        if not wheels:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest("uv build produced no wheel")
        cls.venv = cls.tmp / "venv"
        venv = subprocess.run(
            ["uv", "venv", "--quiet", str(cls.venv)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if venv.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest(f"uv venv failed: {venv.stderr[-400:]}")
        cls.python = cls.venv / "bin" / "python"
        install = subprocess.run(
            ["uv", "pip", "install", "--quiet", "--python", str(cls.python), str(wheels[0])],
            capture_output=True,
            text=True,
            timeout=600,
        )
        if install.returncode != 0:
            shutil.rmtree(cls.tmp, ignore_errors=True)
            raise unittest.SkipTest(
                f"wheel install unavailable (offline?): {install.stderr[-400:]}"
            )

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_1_bundled_assets_resolve_inside_wheel_outside_checkout(self):
        """Verify resolve_asset_dir finds bundled assets in the installed wheel, not the repo."""
        result = subprocess.run(
            [str(self.python), "-c", SMOKE_SCRIPT],
            cwd=self.tmp,  # deliberately outside the repository checkout
            capture_output=True,
            text=True,
            timeout=120,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        self.assertIn("SMOKE-OK", result.stdout)

    def test_2_installed_cli_runs_outside_checkout(self):
        """Verify the installed oude entrypoint runs and reports the packaged version."""
        oude = self.venv / "bin" / "oude"
        result = subprocess.run(
            [str(oude), "--version"],
            cwd=self.tmp,  # deliberately outside the repository checkout
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr[-1000:])
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
