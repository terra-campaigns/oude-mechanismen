"""
Unit tests for bin/init_vault.sh campaign vault bootstrapper and gem packaging.
"""

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
        result = subprocess.run(
            ["ruby", "-Ilib", "-roude_mechanismen/version", "-e", "puts OudeMechanismen::VERSION"],
            cwd=str(self.engine_root),
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, f"Ruby version require failed: {result.stderr}")
        self.assertEqual(result.stdout.strip(), "0.4.0")


if __name__ == "__main__":
    unittest.main()
