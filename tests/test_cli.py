#!/usr/bin/env python3
"""Unit tests for the oude-mechanismen CLI (oude_mechanismen.cli).

Verifies:
1. Version consistency between root VERSION and oude_mechanismen.__version__.
2. Asset resolution across package and engine root directories.
3. CLI --version and help behaviour.
4. Repository initialisation (`oude init`), template mapping, and idempotence.
5. Global skills installation (`oude install-skills`) and JSON registration.
6. Diagnostic checks (`oude doctor`) across complete and incomplete vaults.
7. Pass-through script dispatch with extra arguments.
All test assertions and docstrings strictly adhere to British English.
"""

import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import oude_mechanismen
from oude_mechanismen import cli


class TestOudeCLI(unittest.TestCase):
    """Test suite for the unified oude console CLI entrypoint."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="oude_cli_test_")
        self.target_dir = Path(self.temp_dir) / "test_campaign"
        self.target_dir.mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_version_consistency(self):
        """Verify that __version__ matches root VERSION file."""
        version_file = REPO_ROOT / "VERSION"
        self.assertTrue(version_file.is_file(), "Root VERSION file missing")
        expected_version = version_file.read_text(encoding="utf-8").strip()
        self.assertEqual(
            oude_mechanismen.__version__,
            expected_version,
            "Package __version__ does not match root VERSION",
        )

    def test_resolve_asset_dir(self):
        """Verify asset resolution resolves existing directories."""
        scripts_dir = oude_mechanismen.resolve_asset_dir("scripts")
        self.assertTrue(scripts_dir.is_dir(), f"Scripts directory not found: {scripts_dir}")
        self.assertTrue((scripts_dir / "lint_chapter.py").is_file())

        skills_dir = oude_mechanismen.resolve_asset_dir("skills")
        self.assertTrue(skills_dir.is_dir(), f"Skills directory not found: {skills_dir}")
        self.assertTrue((skills_dir / "add-chapter" / "SKILL.md").is_file())

        templates_dir = oude_mechanismen.resolve_asset_dir("templates")
        self.assertTrue(templates_dir.is_dir(), f"Templates directory not found: {templates_dir}")

    def test_cli_version_flag(self):
        """Verify that oude --version displays the expected package version."""
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            with self.assertRaises(SystemExit) as cm:
                cli.main(["--version"])
            self.assertEqual(cm.exception.code, 0)
            self.assertIn(oude_mechanismen.__version__, fake_out.getvalue())

    def test_init_repository_scaffolding(self):
        """Verify that oude init bootstraps topology, templates, and badges."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            rc = cli._init_repository(self.target_dir)
            self.assertEqual(rc, 0)

        # Check directory topology
        for expected_dir in [
            "campaigns",
            "directory",
            "systems",
            "imgs/gallery",
            "imgs/badges",
            "_sass/custom",
            ".agents/context",
        ]:
            self.assertTrue(
                (self.target_dir / expected_dir).is_dir(),
                f"Directory {expected_dir} was not created",
            )

        # Check starter template files
        for expected_file in [
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
            ".gitignore",
        ]:
            self.assertTrue(
                (self.target_dir / expected_file).is_file(),
                f"File {expected_file} was not scaffolded",
            )

        # Check fallback badges
        badges = list((self.target_dir / "imgs" / "badges").glob("*.png"))
        self.assertGreaterEqual(len(badges), 1, "Fallback badges were not copied")

    def test_init_repository_no_clobber(self):
        """Verify that oude init does not overwrite existing files."""
        custom_agents = self.target_dir / ".agents" / "AGENTS.md"
        custom_agents.parent.mkdir(parents=True, exist_ok=True)
        custom_agents.write_text("CUSTOM CAMPAIGN SPECIFICATION", encoding="utf-8")

        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            rc = cli._init_repository(self.target_dir)
            self.assertEqual(rc, 0)

        self.assertEqual(
            custom_agents.read_text(encoding="utf-8"),
            "CUSTOM CAMPAIGN SPECIFICATION",
            "Existing file was clobbered by init",
        )

    def test_install_skills_and_registration(self):
        """Verify skills synchronisation and registration in skills.json."""
        fake_xdg = Path(self.temp_dir) / "xdg_data"
        fake_gemini_cfg = Path(self.temp_dir) / "gemini_config"
        fake_skills_file = fake_gemini_cfg / "skills.json"

        # Pre-populate skills.json with existing entries (e.g. artifice)
        fake_gemini_cfg.mkdir(parents=True, exist_ok=True)
        fake_skills_file.write_text(
            json.dumps({"entries": [{"path": "/existing/artifice/skills"}]}),
            encoding="utf-8",
        )

        with patch.object(cli, "SKILLS_TARGET_DIR", fake_xdg / "oude-mechanismen" / "skills"), \
             patch.object(cli, "GEMINI_CONFIG_DIR", fake_gemini_cfg), \
             patch.object(cli, "GEMINI_SKILLS_FILE", fake_skills_file):
            rc = cli._install_skills()
            self.assertEqual(rc, 0)

            # Check that skills were copied
            dest_skills = fake_xdg / "oude-mechanismen" / "skills"
            self.assertTrue((dest_skills / "add-chapter" / "SKILL.md").is_file())
            self.assertTrue((dest_skills / "scribe-session" / "SKILL.md").is_file())

            # Check JSON configuration
            updated_cfg = json.loads(fake_skills_file.read_text(encoding="utf-8"))
            entries = updated_cfg.get("entries", [])
            paths = [e.get("path") for e in entries if isinstance(e, dict)]
            self.assertIn("/existing/artifice/skills", paths, "Existing entry was erased")
            self.assertIn(str(dest_skills.resolve()), paths, "New skills path was not added")

            # Second run must be idempotent
            rc2 = cli._install_skills()
            self.assertEqual(rc2, 0)
            updated_cfg2 = json.loads(fake_skills_file.read_text(encoding="utf-8"))
            self.assertEqual(len(updated_cfg2.get("entries", [])), 2, "Duplicate entries created")

    def test_corrupt_skills_json_refuses_overwrite_and_creates_backup(self):
        """Verify that a corrupt skills.json is backed up and not overwritten."""
        fake_xdg = Path(self.temp_dir) / "xdg_data"
        fake_gemini_cfg = Path(self.temp_dir) / "gemini_config"
        fake_skills_file = fake_gemini_cfg / "skills.json"
        fake_gemini_cfg.mkdir(parents=True, exist_ok=True)
        fake_skills_file.write_text("{\"entries\": [INVALID JSON TRAILING COMMA,", encoding="utf-8")

        with patch.object(cli, "SKILLS_TARGET_DIR", fake_xdg / "oude-mechanismen" / "skills"), \
             patch.object(cli, "GEMINI_CONFIG_DIR", fake_gemini_cfg), \
             patch.object(cli, "GEMINI_SKILLS_FILE", fake_skills_file), \
             patch("sys.stderr", new=io.StringIO()):
            rc = cli._install_skills()
            self.assertEqual(rc, 1, "Should fail when skills.json is corrupt")

            # Verify backup was created
            backup_file = fake_skills_file.with_suffix(".json.corrupt.bak")
            self.assertTrue(backup_file.is_file(), "Corrupt backup file was not created")
            self.assertIn("INVALID JSON", backup_file.read_text(encoding="utf-8"))

            # Verify corrupt file was not overwritten with blank structure
            self.assertIn("INVALID JSON", fake_skills_file.read_text(encoding="utf-8"))

    def test_doctor_diagnostics(self):
        """Verify doctor detects missing and valid configurations."""
        # Incomplete vault
        with patch("sys.stdout", new=io.StringIO()):
            rc_fail = cli._doctor(self.target_dir)
            self.assertEqual(rc_fail, 1, "Doctor should report failure on empty directory")

        # Initialise vault and create mock catalog
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        with patch("sys.stdout", new=io.StringIO()):
            rc_pass = cli._doctor(self.target_dir)
            self.assertEqual(rc_pass, 0, "Doctor should pass on initialised directory with catalog")

    def test_doctor_detects_missing_oude_mechanismen_in_config_yml(self):
        """Verify doctor detects missing oude-mechanismen in _config.yml."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        config_yml_path = self.target_dir / "_config.yml"
        config_content = config_yml_path.read_text(encoding="utf-8")
        config_content = "# plugins:\n# - oude-mechanismen\n" + config_content.replace("  - oude-mechanismen\n", "")
        config_yml_path.write_text(config_content, encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when oude-mechanismen is missing in _config.yml")
            self.assertIn("Jekyll configuration (_config.yml) is missing oude-mechanismen under plugins", fake_out.getvalue())

    def test_doctor_detects_legacy_plugins(self):
        """Verify doctor detects legacy _plugins/data_extractor.rb."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        legacy_plugin_path = self.target_dir / "_plugins" / "data_extractor.rb"
        legacy_plugin_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_plugin_path.write_text("# Legacy plugin", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when legacy plugins are detected")
            self.assertIn("Legacy file detected: _plugins/data_extractor.rb", fake_out.getvalue())

    def test_doctor_fix_removes_legacy_plugins_and_patches_config_yml(self):
        """Verify doctor --fix removes legacy plugins and patches _config.yml."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        # Add valid catalog so catalog rebuild is not triggered
        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        # Add legacy plugin
        legacy_plugin_path = self.target_dir / "_plugins" / "data_extractor.rb"
        legacy_plugin_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_plugin_path.write_text("# Legacy plugin", encoding="utf-8")

        # Remove oude-mechanismen from _config.yml and prepend commented # plugins:
        config_yml_path = self.target_dir / "_config.yml"
        config_content = "# plugins:\n" + config_yml_path.read_text(encoding="utf-8").replace("  - oude-mechanismen\n", "")
        config_yml_path.write_text(config_content, encoding="utf-8")

        # Run doctor with --fix
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed legacy file: _plugins/data_extractor.rb", fake_out.getvalue())
            self.assertIn("Adding oude-mechanismen to plugins in _config.yml...", fake_out.getvalue())

        # Verify legacy plugin and empty _plugins dir are removed
        self.assertFalse(legacy_plugin_path.exists(), "Legacy plugin was not removed")
        self.assertFalse((self.target_dir / "_plugins").exists(), "Empty _plugins directory was not removed")

        # Verify oude-mechanismen is added under active plugins: and not under # plugins:
        updated_config_content = config_yml_path.read_text(encoding="utf-8")
        self.assertIn("\nplugins:\n  - oude-mechanismen\n", updated_config_content)

    def test_doctor_fix_rebuilds_catalogue_when_stale(self):
        """Verify doctor --fix triggers bundle exec jekyll build when catalogue is stale."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        # Write catalog without engine_version
        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(json.dumps({"total_entries": 5}), encoding="utf-8")

        with patch("shutil.which", return_value="/usr/bin/bundle"), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                rc = cli._doctor(self.target_dir, fix=True)
                self.assertEqual(rc, 0)
                self.assertIn("Regenerating catalogue with engine_version via 'bundle exec jekyll build'...", fake_out.getvalue())
                mock_sub.assert_called_with(
                    ["bundle", "exec", "jekyll", "build"],
                    cwd=str(self.target_dir),
                    capture_output=True,
                    text=True,
                )

    def test_doctor_detects_redundant_all_content_md(self):
        """Verify doctor detects redundant root all-content.md."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        bundled_content = oude_mechanismen.resolve_asset_dir("jekyll/all-content.md").read_text(encoding="utf-8")
        (self.target_dir / "all-content.md").write_text(bundled_content, encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when redundant all-content.md is detected")
            self.assertIn("Redundant root all-content.md detected", fake_out.getvalue())

    def test_doctor_fix_removes_redundant_all_content_md(self):
        """Verify doctor --fix removes redundant root all-content.md."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        bundled_content = oude_mechanismen.resolve_asset_dir("jekyll/all-content.md").read_text(encoding="utf-8")
        (self.target_dir / "all-content.md").write_text(bundled_content, encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed redundant root all-content.md", fake_out.getvalue())

        self.assertFalse((self.target_dir / "all-content.md").exists(), "Redundant all-content.md was not removed")

    def test_doctor_preserves_custom_all_content_md(self):
        """Verify doctor preserves custom root all-content.md."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        custom_content = "# Custom LLM Context\n\nThis is a custom version of all-content.md."
        (self.target_dir / "all-content.md").write_text(custom_content, encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0, "Doctor should pass when custom all-content.md is detected")
            self.assertIn("Custom root all-content.md override detected", fake_out.getvalue())

    def test_doctor_detects_shadowing_includes(self):
        """Verify doctor detects shadowing includes in _includes/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        includes_dir = self.target_dir / "_includes"
        includes_dir.mkdir(parents=True, exist_ok=True)
        (includes_dir / "connected_to.html").write_text("<!-- shadow -->", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when shadowing include is detected")
            self.assertIn("Shadowing include detected: _includes/connected_to.html", fake_out.getvalue())

    def test_doctor_fix_removes_shadowing_includes_and_preserves_custom(self):
        """Verify doctor --fix removes shadowing includes and preserves custom includes."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        includes_dir = self.target_dir / "_includes"
        includes_dir.mkdir(parents=True, exist_ok=True)
        (includes_dir / "connected_to.html").write_text("<!-- shadow -->", encoding="utf-8")
        (includes_dir / "footer_custom.html").write_text("<!-- custom footer -->", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed shadowing duplicate include: _includes/connected_to.html", fake_out.getvalue())

        self.assertFalse((includes_dir / "connected_to.html").exists(), "Shadowing include was not removed")
        self.assertTrue((includes_dir / "footer_custom.html").exists(), "Custom include was removed")
        self.assertTrue(includes_dir.exists(), "_includes directory should not be pruned when not empty")

    def test_doctor_fix_prunes_empty_includes_dir(self):
        """Verify doctor --fix prunes _includes directory if empty after removing shadows."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        includes_dir = self.target_dir / "_includes"
        includes_dir.mkdir(parents=True, exist_ok=True)
        (includes_dir / "connected_to.html").write_text("<!-- shadow -->", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")

        self.assertFalse((includes_dir / "connected_to.html").exists(), "Shadowing include was not removed")
        self.assertFalse(includes_dir.exists(), "Empty _includes directory was not pruned")

    def test_run_script_passthrough(self):
        """Verify pass-through execution runs bundled script and returns exit code."""
        with patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)
            rc = cli._run_script("lint_chapter.py", ["--help"])
            self.assertEqual(rc, 0)
            mock_sub.assert_called_once()
            called_cmd = mock_sub.call_args[0][0]
            self.assertIn("lint_chapter.py", called_cmd[1])
            self.assertIn("--help", called_cmd[2:])

    def test_doctor_detects_legacy_runner_scripts(self):
        """Verify doctor detects legacy runner scripts in .agents/scripts/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        scripts_dir = self.target_dir / ".agents" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "lint_chapter.py").write_text("# Legacy runner", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when legacy runner scripts are detected")
            self.assertIn("Legacy runner script detected: .agents/scripts/lint_chapter.py", fake_out.getvalue())

    def test_doctor_fix_removes_legacy_runner_scripts_and_prunes_empty_dir(self):
        """Verify doctor --fix removes legacy runner scripts and prunes empty .agents/scripts/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        scripts_dir = self.target_dir / ".agents" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "lint_chapter.py").write_text("# Legacy runner", encoding="utf-8")
        (scripts_dir / "harvest_archival.py").write_text("# Legacy runner", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed legacy runner script: .agents/scripts/lint_chapter.py", fake_out.getvalue())
            self.assertIn("Removed legacy runner script: .agents/scripts/harvest_archival.py", fake_out.getvalue())

        self.assertFalse((scripts_dir / "lint_chapter.py").exists(), "Legacy runner script was not removed")
        self.assertFalse((scripts_dir / "harvest_archival.py").exists(), "Legacy runner script was not removed")
        self.assertFalse(scripts_dir.exists(), "Empty .agents/scripts/ directory was not pruned")

    def test_doctor_preserves_custom_agent_scripts(self):
        """Verify doctor preserves custom agent scripts in .agents/scripts/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        scripts_dir = self.target_dir / ".agents" / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "lint_chapter.py").write_text("# Legacy runner", encoding="utf-8")
        (scripts_dir / "custom_tool.py").write_text("# Custom agent script", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed legacy runner script: .agents/scripts/lint_chapter.py", fake_out.getvalue())

        self.assertFalse((scripts_dir / "lint_chapter.py").exists(), "Legacy runner script was not removed")
        self.assertTrue((scripts_dir / "custom_tool.py").exists(), "Custom agent script was removed")
        self.assertTrue(scripts_dir.exists(), ".agents/scripts/ directory should not be pruned when not empty")

    def test_doctor_detects_deprecated_engine_version_stamp(self):
        """Verify doctor detects deprecated .agents/.engine-version stamp file."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        stamp_file = self.target_dir / ".agents" / ".engine-version"
        stamp_file.write_text("0.2.0 (abc1234)", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when .engine-version exists")
            self.assertIn("Deprecated version stamp detected: .agents/.engine-version", fake_out.getvalue())

    def test_doctor_fix_removes_deprecated_engine_version_stamp(self):
        """Verify doctor --fix removes deprecated .agents/.engine-version stamp file."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.0", "total_entries": 10}),
            encoding="utf-8",
        )

        stamp_file = self.target_dir / ".agents" / ".engine-version"
        stamp_file.write_text("0.2.0 (abc1234)", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            self.assertIn("Removed deprecated version stamp: .agents/.engine-version", fake_out.getvalue())

        self.assertFalse(stamp_file.exists(), "Deprecated version stamp was not removed")

    def test_doctor_warns_on_engine_version_mismatch(self):
        """Verify doctor warns when catalog.json engine_version differs from installed package version."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.1.0", "total_entries": 10}),
            encoding="utf-8",
        )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0, "Doctor should pass with warning on version mismatch")
            self.assertIn("Engine version mismatch: catalog.json (0.1.0) vs installed package", fake_out.getvalue())


if __name__ == "__main__":
    unittest.main()
