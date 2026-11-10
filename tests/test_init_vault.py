"""
Unit tests for bin/init_vault.sh campaign vault bootstrapper and gem packaging.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


class TestInitVault(unittest.TestCase):
    def setUp(self):
        self.engine_root = Path(__file__).resolve().parent.parent
        self.init_script = self.engine_root / "bin" / "init_vault.sh"

    def test_init_vault_bootstraps_directory_structure_and_templates(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test_campaign"
            target.mkdir()

            result = subprocess.run(
                ["bash", str(self.init_script), str(target)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")

            # Verify directory topology
            expected_dirs = [
                "campaigns",
                "directory",
                "systems",
                "imgs/gallery",
                "imgs/badges",
                "_sass/custom",
                ".agents/context",
            ]
            for rel_dir in expected_dirs:
                self.assertTrue((target / rel_dir).is_dir(), f"Missing directory: {rel_dir}")

            # Verify starter template files
            expected_files = [
                ".agents/AGENTS.md",
                ".agents/context/tier1_sources.yml",
                ".agents/context/decisions.md",
                ".agents/context/aesthetics.yml",
                ".agents/context/route_graph.json",
                "_config.yml",
                "Gemfile",
                "_sass/custom/custom.scss",
                "index.md",
                "directory/index.md",
                "campaigns/index.md",
                "systems/index.md",
                "all-content.md",
                ".gitignore",
            ]
            for rel_file in expected_files:
                self.assertTrue((target / rel_file).is_file(), f"Missing file: {rel_file}")

            # Verify fallback badges were copied
            badges = list((target / "imgs/badges").glob("*.png"))
            self.assertGreater(len(badges), 0, "Fallback badges should be copied")

    def test_init_vault_is_idempotent_and_does_not_clobber(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "test_campaign"
            target.mkdir()

            # First run
            res1 = subprocess.run(["bash", str(self.init_script), str(target)], capture_output=True)
            self.assertEqual(res1.returncode, 0)

            # Mutate a starter file
            custom_text = "# Custom Lore Note\n\nDo not overwrite me."
            agents_md = target / ".agents/AGENTS.md"
            agents_md.write_text(custom_text, encoding="utf-8")

            # Second run
            res2 = subprocess.run(["bash", str(self.init_script), str(target)], capture_output=True)
            self.assertEqual(res2.returncode, 0)

            # File must remain untouched
            self.assertEqual(agents_md.read_text(encoding="utf-8"), custom_text)

    def test_gem_version_consistency(self):
        if not shutil.which("ruby"):
            self.skipTest("ruby executable not found on host system")
        result = subprocess.run(
            ["ruby", "-Ilib", "-roude_mechanismen/version", "-e", "puts OudeMechanismen::VERSION"],
            cwd=str(self.engine_root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Ruby version require failed: {result.stderr}")
        self.assertEqual(result.stdout.strip(), "0.5.0")

    def test_init_vault_enables_delete_branch_on_merge_when_remote_present(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target = tmp_path / "test_campaign"
            target.mkdir()

            # Initialise git repository with remote origin
            subprocess.run(["git", "init", "-b", "main", str(target)], check=True, capture_output=True)
            subprocess.run(
                ["git", "-C", str(target), "remote", "add", "origin", "https://github.com/terra-campaigns/test.git"],
                check=True,
                capture_output=True,
            )

            # Create mock gh binary that records invocations
            mock_bin_dir = tmp_path / "bin"
            mock_bin_dir.mkdir()
            gh_log = tmp_path / "gh_calls.log"
            mock_gh = mock_bin_dir / "gh"
            mock_gh.write_text(
                f'#!/usr/bin/env bash\necho "$@" >> "{gh_log}"\nexit 0\n',
                encoding="utf-8",
            )
            mock_gh.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(self.init_script), str(target)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
            self.assertIn("Configuring GitHub repository settings", result.stdout)
            self.assertIn("Enabled --delete-branch-on-merge", result.stdout)

            # Verify gh was called with the expected arguments
            self.assertTrue(gh_log.is_file(), "Mock gh should have been called")
            calls = gh_log.read_text(encoding="utf-8").strip().splitlines()
            self.assertEqual(calls, ["repo edit --delete-branch-on-merge"])

    def test_init_vault_skips_governance_when_no_remote(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            target = tmp_path / "test_campaign"
            target.mkdir()

            # Initialise git repository WITHOUT remote
            subprocess.run(["git", "init", "-b", "main", str(target)], check=True, capture_output=True)

            # Create mock gh binary
            mock_bin_dir = tmp_path / "bin"
            mock_bin_dir.mkdir()
            gh_log = tmp_path / "gh_calls.log"
            mock_gh = mock_bin_dir / "gh"
            mock_gh.write_text(
                f'#!/usr/bin/env bash\necho "$@" >> "{gh_log}"\nexit 0\n',
                encoding="utf-8",
            )
            mock_gh.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin_dir}:{env['PATH']}"

            result = subprocess.run(
                ["bash", str(self.init_script), str(target)],
                capture_output=True,
                text=True,
                env=env,
            )
            self.assertEqual(result.returncode, 0, f"Script failed: {result.stderr}")
            self.assertNotIn("Configuring GitHub repository settings", result.stdout)
            self.assertFalse(gh_log.is_file(), "Mock gh should NOT have been called when no remote is set")


if __name__ == "__main__":
    unittest.main()
