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

import importlib.metadata
import io
import json
import os
import re
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

    def test_version_synchronisation_across_package_gem_and_templates(self):
        """Verify VERSION stays synchronised with Python/Ruby fallbacks and Gemfile.template (#105, #106)."""
        expected = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()

        # 1. Python fallback when VERSION and importlib metadata are unavailable
        empty_dir = Path(self.temp_dir) / "empty_pkg"
        empty_dir.mkdir(exist_ok=True)
        with patch.object(oude_mechanismen, "PACKAGE_DIR", empty_dir), \
             patch.object(oude_mechanismen, "ENGINE_ROOT", empty_dir), \
             patch(
                 "importlib.metadata.version",
                 side_effect=importlib.metadata.PackageNotFoundError("oude-mechanismen"),
             ):
            self.assertEqual(
                oude_mechanismen._get_version(),
                expected,
                "src/oude_mechanismen/__init__.py fallback version is out of sync with VERSION",
            )

        # 2. Ruby gem fallback version in lib/oude_mechanismen/version.rb
        rb_text = (REPO_ROOT / "lib" / "oude_mechanismen" / "version.rb").read_text(encoding="utf-8")
        rb_match = re.search(r'\belse\s*\n\s*["\']([^"\']+)["\']', rb_text)
        self.assertIsNotNone(rb_match, "Expected else fallback literal in lib/oude_mechanismen/version.rb")
        self.assertEqual(
            rb_match.group(1),
            expected,
            "lib/oude_mechanismen/version.rb fallback version is out of sync with VERSION",
        )

        # 3. Downstream Gemfile template tag pin
        gemfile_text = (REPO_ROOT / "templates" / "jekyll" / "Gemfile.template").read_text(encoding="utf-8")
        tag_match = re.search(
            r'gem\s+["\']oude-mechanismen["\'][^\n]*\btag:\s*["\']v([^"\']+)["\']',
            gemfile_text,
        )
        self.assertIsNotNone(tag_match, "Expected tagged oude-mechanismen pin in Gemfile.template")
        self.assertEqual(
            tag_match.group(1),
            expected,
            "templates/jekyll/Gemfile.template tag pin is out of sync with VERSION",
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


    def test_enable_auto_branch_deletion_invokes_gh_when_remote_present(self):
        """gh repo edit --delete-branch-on-merge runs when gh exists and origin is set."""
        subprocess.run(["git", "init"], cwd=self.target_dir, capture_output=True, check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "remote", "add", "origin", "https://example.com/x.git"], check=True)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            out = "https://example.com/x.git" if len(cmd) > 3 and cmd[3] == "config" else ""
            return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

        with patch.object(cli.shutil, "which", return_value="/usr/bin/gh"), \
             patch.object(cli.subprocess, "run", side_effect=fake_run):
            self.assertTrue(cli._enable_auto_branch_deletion(self.target_dir))
        self.assertIn(["gh", "repo", "edit", "--delete-branch-on-merge"], calls)

    def test_enable_auto_branch_deletion_skips_without_remote(self):
        """No gh call when the repo has no origin remote."""
        subprocess.run(["git", "init"], cwd=self.target_dir, capture_output=True, check=True)
        calls = []

        def fake_run(cmd, **kwargs):
            calls.append(cmd)
            return subprocess.CompletedProcess(cmd, 1 if len(cmd) > 3 and cmd[3] == "config" else 0, stdout="", stderr="")

        with patch.object(cli.shutil, "which", return_value="/usr/bin/gh"), \
             patch.object(cli.subprocess, "run", side_effect=fake_run):
            self.assertFalse(cli._enable_auto_branch_deletion(self.target_dir))
        self.assertNotIn(["gh", "repo", "edit", "--delete-branch-on-merge"], calls)

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
            ".github",
        ]:
            self.assertTrue(
                (self.target_dir / expected_dir).is_dir(),
                f"Directory {expected_dir} was not created",
            )

        # Check starter template files
        for expected_file in [
            ".agents/AGENTS.md",
            ".agents/context/tier1_sources.yml",
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
            ".github/dependabot.yml",
        ]:
            self.assertTrue(
                (self.target_dir / expected_file).is_file(),
                f"File {expected_file} was not scaffolded",
            )

        self.assertFalse(
            (self.target_dir / ".agents" / "context" / "decisions.md").exists(),
            "legacy decisions.md must no longer be scaffolded (Design 006)",
        )
        gitignore_lines = (self.target_dir / ".gitignore").read_text(encoding="utf-8").splitlines()
        self.assertIn(
            "_gm-materials/.cache/tier2.json",
            gitignore_lines,
            "fresh vault .gitignore must carry an uncommented _gm-materials/.cache/tier2.json line",
        )

        self.assertFalse((self.target_dir / "all-content.md").exists())
        self.assertFalse((self.target_dir / "_plugins" / "llm_content.rb").exists())

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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
                    encoding="utf-8",
                    errors="replace",
                )

    def test_doctor_detects_deprecated_all_content_md_and_llm_content_plugin(self):
        """Verify doctor detects deprecated root all-content.md and _plugins/llm_content.rb."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        (self.target_dir / "all-content.md").write_text("# Legacy LLM dump", encoding="utf-8")
        legacy_llm = self.target_dir / "_plugins" / "llm_content.rb"
        legacy_llm.parent.mkdir(parents=True, exist_ok=True)
        legacy_llm.write_text("# Legacy llm_content plugin", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1, "Doctor should report failure when deprecated LLM dump artefacts exist")
            out = fake_out.getvalue()
            self.assertIn("Deprecated root all-content.md detected", out)
            self.assertIn("Legacy file detected: _plugins/llm_content.rb", out)

    def test_doctor_fix_removes_deprecated_all_content_md_and_llm_content_plugin(self):
        """Verify doctor --fix removes deprecated root all-content.md and _plugins/llm_content.rb."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        all_content_path = self.target_dir / "all-content.md"
        all_content_path.write_text("# Legacy LLM dump", encoding="utf-8")
        legacy_llm = self.target_dir / "_plugins" / "llm_content.rb"
        legacy_llm.parent.mkdir(parents=True, exist_ok=True)
        legacy_llm.write_text("# Legacy llm_content plugin", encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0, "Doctor --fix should succeed")
            out = fake_out.getvalue()
            self.assertIn("Removed deprecated root all-content.md", out)
            self.assertIn("Removed legacy file: _plugins/llm_content.rb", out)

        self.assertFalse(all_content_path.exists(), "Deprecated all-content.md was not removed")
        self.assertFalse(legacy_llm.exists(), "Legacy _plugins/llm_content.rb was not removed")
        self.assertFalse((self.target_dir / "_plugins").exists(), "Empty _plugins directory was not pruned")
        self.assertTrue(catalog_path.is_file(), "catalog.json should remain intact")

    def test_doctor_ignores_nonfile_all_content_md(self):
        """Verify doctor ignores a directory named all-content.md without crashing."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        all_content_dir = self.target_dir / "all-content.md"
        all_content_dir.mkdir()

        with patch("sys.stdout", new=io.StringIO()):
            rc = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc, 0)

        self.assertTrue(all_content_dir.is_dir(), "Directory named all-content.md must remain untouched")

    def test_doctor_detects_shadowing_includes(self):
        """Verify doctor detects shadowing includes in _includes/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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

    def test_lint_wiki_passthrough_registered(self):
        """Verify lint-wiki is a pass-through command and a prunable legacy runner."""
        self.assertEqual(cli.PASS_THROUGH_SCRIPTS.get("lint-wiki"), "lint_wiki.py")
        self.assertIn("lint_wiki.py", cli.LEGACY_RUNNER_SCRIPTS)

    def test_doctor_detects_legacy_runner_scripts(self):
        """Verify doctor detects legacy runner scripts in .agents/scripts/."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
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

    def test_doctor_fix_handles_inline_plugins_in_config_yml(self):
        """Verify doctor --fix appends oude-mechanismen to inline plugins lists without duplicating keys."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        config_path = self.target_dir / "_config.yml"
        for initial, expected in [
            (
                "title: Test\nplugins: [jekyll-feed]\nexclude: [_gm-materials]\n",
                "title: Test\nplugins: [jekyll-feed, oude-mechanismen]\nexclude: [_gm-materials]\n",
            ),
            (
                "title: Test\nplugins: []\nexclude: [_gm-materials]\n",
                "title: Test\nplugins: [oude-mechanismen]\nexclude: [_gm-materials]\n",
            ),
        ]:
            config_path.write_text(initial, encoding="utf-8")
            with patch("sys.stdout", new=io.StringIO()):
                rc_fix = cli._doctor(self.target_dir, fix=True)
                self.assertEqual(rc_fix, 0)
            updated = config_path.read_text(encoding="utf-8")
            self.assertEqual(updated, expected)
            self.assertEqual(updated.count("plugins:"), 1)

            with patch("sys.stdout", new=io.StringIO()):
                rc_check = cli._doctor(self.target_dir)
                self.assertEqual(rc_check, 0, "Doctor should recognise inline oude-mechanismen plugin")

    def test_resolve_asset_dir_includes_and_removed_llm_assets(self):
        """Verify bundled Jekyll includes directory resolves cleanly and legacy LLM dump files are removed."""
        includes_dir = oude_mechanismen.resolve_asset_dir("jekyll/_includes")
        self.assertTrue(includes_dir.is_dir())
        self.assertFalse((REPO_ROOT / "jekyll" / "all-content.md").exists())
        self.assertFalse((REPO_ROOT / "jekyll" / "_plugins" / "llm_content.rb").exists())
        self.assertNotIn("llm_content", (REPO_ROOT / "lib" / "oude_mechanismen.rb").read_text(encoding="utf-8"))

    def test_doctor_fix_preserves_plugin_quotes_comments_and_boundaries(self):
        """Verify doctor handles quoted plugins, trailing comments, empty configs, and substring collisions."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        config_path = self.target_dir / "_config.yml"
        cases = [
            (
                'title: Test\nplugins: ["jekyll-feed"]\nexclude: ["_gm-materials"]\n',
                'title: Test\nplugins: ["jekyll-feed", "oude-mechanismen"]\nexclude: ["_gm-materials"]\n',
            ),
            (
                "title: Test\nplugins: ['jekyll-feed']\nexclude: ['_gm-materials']\n",
                "title: Test\nplugins: ['jekyll-feed', 'oude-mechanismen']\nexclude: ['_gm-materials']\n",
            ),
            (
                "title: Test\nplugins: [jekyll-feed, ]\nexclude: [_gm-materials]\n",
                "title: Test\nplugins: [jekyll-feed, oude-mechanismen]\nexclude: [_gm-materials]\n",
            ),
            (
                "title: Test\nplugins: [jekyll-feed] # core plugins\nexclude: [_gm-materials]\n",
                "title: Test\nplugins: [jekyll-feed, oude-mechanismen] # core plugins\nexclude: [_gm-materials]\n",
            ),
            (
                "title: Test\nplugins: [my-oude-mechanismen]\nexclude: [_gm-materials]\n",
                "title: Test\nplugins: [my-oude-mechanismen, oude-mechanismen]\nexclude: [_gm-materials]\n",
            ),
            (
                'title: Test\nplugins: # gems\n  - "jekyll-feed"\nexclude:\n  - "_gm-materials"\n',
                'title: Test\nplugins: # gems\n  - "oude-mechanismen"\n  - "jekyll-feed"\nexclude:\n  - "_gm-materials"\n',
            ),
            (
                "",
                "plugins:\n  - oude-mechanismen\n\nexclude:\n  - \"_gm-materials\"\n",
            ),
        ]
        for initial, expected in cases:
            config_path.write_text(initial, encoding="utf-8")
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 1)
                self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
            self.assertEqual(config_path.read_text(encoding="utf-8"), expected)
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_doctor_recognises_quoted_block_plugin_and_ignores_nonfile_engine_version(self):
        """Verify doctor accepts quoted block plugins and does not crash if .engine-version is a directory."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        config_path = self.target_dir / "_config.yml"
        config_path.write_text(
            'title: Test\nplugins:\n  - "oude-mechanismen"\nexclude:\n  - "_gm-materials"\n',
            encoding="utf-8",
        )

        engine_version_dir = self.target_dir / ".agents" / ".engine-version"
        engine_version_dir.mkdir(parents=True, exist_ok=True)

        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        self.assertTrue(engine_version_dir.is_dir())

    def test_init_scaffolds_gm_materials_and_excludes(self):
        """Verify oude init scaffolds top-level _gm-materials/, .gitignore rule, and _config.yml exclude."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        self.assertTrue(
            (self.target_dir / "_gm-materials").is_dir(),
            "Expected top-level _gm-materials/ directory to be created",
        )
        for subdir in ["session-summaries", "session-preps", "digests"]:
            self.assertFalse(
                (self.target_dir / "_gm-materials" / subdir).exists(),
                f"Expected _gm-materials/{subdir} not to be pre-created during init",
            )

        gitignore_text = (self.target_dir / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("_gm-materials/", gitignore_text)
        self.assertIn(".agents/context/catalog.json", gitignore_text)
        self.assertIn(".agents/context/rolling_glossary.md", gitignore_text)
        self.assertIn(".agents/context/references.json", gitignore_text)
        self.assertIn("_gm-materials/.cache/tier2.json", gitignore_text)

        tier1_text = (self.target_dir / ".agents" / "context" / "tier1_sources.yml").read_text(encoding="utf-8")
        self.assertIn("drive_dir: .", tier1_text)

        config_text = (self.target_dir / "_config.yml").read_text(encoding="utf-8")
        self.assertTrue(cli._has_jekyll_exclude(config_text, "_gm-materials"))

    def test_doctor_checks_and_fixes_gitignore_and_config_exclude_for_gm_materials(self):
        """Verify doctor checks and --fix repairs missing _gm-materials in .gitignore and _config.yml."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        gitignore_path = self.target_dir / ".gitignore"
        config_path = self.target_dir / "_config.yml"

        # Case 1: .gitignore missing _gm-materials/, derived .agents/context caches, and the tier2 index (and no trailing newline)
        gitignore_path.write_text("_site/", encoding="utf-8")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        self.assertEqual(
            gitignore_path.read_text(encoding="utf-8"),
            "_site/\n_gm-materials/\n.agents/context/catalog.json\n.agents/context/rolling_glossary.md\n.agents/context/references.json\n_gm-materials/.cache/tier2.json\n",
        )
        self.assertTrue(cli._has_gitignore_entry("_site/\r\n_gm-materials/\r\n", "_gm-materials"))
        self.assertTrue(
            cli._has_gitignore_entry(
                "_site/\r\n.agents/context/catalog.json\r\n",
                ".agents/context/catalog.json",
            )
        )
        self.assertTrue(
            cli._has_gitignore_entry(
                "_site/\r\n.agents/context/rolling_glossary.md\r\n",
                ".agents/context/rolling_glossary.md",
            )
        )
        self.assertTrue(
            cli._has_gitignore_entry(
                "_site/\r\n.agents/context/references.json\r\n",
                ".agents/context/references.json",
            )
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "_site/\r\n_agents/context/catalogXjson\r\n",
                ".agents/context/catalog.json",
            ),
            "dotted entries must be regex-escaped (no wildcard false positive)",
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "_site/\r\n_agents/context/rolling_glossaryXmd\r\n",
                ".agents/context/rolling_glossary.md",
            ),
            "dotted entries must be regex-escaped (no wildcard false positive)",
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "_site/\r\n_agents/context/referencesXjson\r\n",
                ".agents/context/references.json",
            ),
            "dotted entries must be regex-escaped (no wildcard false positive)",
        )
        self.assertTrue(
            cli._has_gitignore_entry(
                "/.agents/context/references.json\n",
                ".agents/context/references.json",
            ),
            "leading slash anchored gitignore entry must match",
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "# .agents/context/references.json\n",
                ".agents/context/references.json",
            ),
            "full-line comment must not satisfy gitignore entry",
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "_site/\n.agents/context/references.json # derived cache\n",
                ".agents/context/references.json",
            ),
            "trailing '#' is literal text in gitignore(5) and must not satisfy entry",
        )
        self.assertFalse(
            cli._has_gitignore_entry(
                "_site/\n_gm-materials/ # private\n",
                "_gm-materials/",
            ),
            "trailing '#' is literal text in gitignore(5) and must not satisfy directory entry",
        )
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

        # Case 1b: pre-Design-006 .gitignore missing rolling_glossary.md, references.json, and the tier2 index
        gitignore_path.write_text(
            "_gm-materials/\n.agents/context/catalog.json\n", encoding="utf-8"
        )
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertIn(".gitignore is missing .agents/context/rolling_glossary.md", fake_out.getvalue())
            self.assertIn(".gitignore is missing .agents/context/references.json", fake_out.getvalue())
            self.assertIn(".gitignore is missing _gm-materials/.cache/tier2.json", fake_out.getvalue())
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
            self.assertEqual(cli._doctor(self.target_dir), 0)
        self.assertEqual(
            gitignore_path.read_text(encoding="utf-8"),
            "_gm-materials/\n.agents/context/catalog.json\n.agents/context/rolling_glossary.md\n.agents/context/references.json\n_gm-materials/.cache/tier2.json\n",
        )

        # Case 1c: completely missing .gitignore is flagged and recreated with all required exclusions
        gitignore_path.unlink()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertIn("Missing .gitignore", fake_out.getvalue())
            self.assertIn(".agents/context/references.json", fake_out.getvalue())
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
            self.assertIn("Created .gitignore", fake_out.getvalue())
            self.assertIn(".agents/context/references.json", fake_out.getvalue())
        self.assertIn(".agents/context/references.json", gitignore_path.read_text(encoding="utf-8"))

        # Case 2: _config.yml inline and block exclude variants
        exclude_cases = [
            (
                'title: Test # header\nplugins: ["oude-mechanismen"]\nexclude: ["Gemfile"]\n',
                'title: Test # header\nplugins: ["oude-mechanismen"]\nexclude: ["Gemfile", "_gm-materials"]\n',
            ),
            (
                "title: Test\nplugins: [oude-mechanismen]\nexclude:\n  - Gemfile\n",
                'title: Test\nplugins: [oude-mechanismen]\nexclude:\n  - "_gm-materials"\n  - Gemfile\n',
            ),
            (
                "title: Test\nplugins: [oude-mechanismen]\n",
                'title: Test\nplugins: [oude-mechanismen]\n\nexclude:\n  - "_gm-materials"\n',
            ),
        ]
        for initial_cfg, expected_cfg in exclude_cases:
            config_path.write_text(initial_cfg, encoding="utf-8")
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 1)
                self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
            self.assertEqual(config_path.read_text(encoding="utf-8"), expected_cfg)
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_data_extractor_rb_excludes_gm_materials(self):
        """Verify jekyll/_plugins/data_extractor.rb unconditionally filters _gm-materials/ from catalog.json."""
        extractor_path = cli.resolve_asset_dir("jekyll/_plugins/data_extractor.rb")
        if not extractor_path.is_file():
            extractor_path = cli.resolve_asset_dir("jekyll") / "_plugins" / "data_extractor.rb"
        content = extractor_path.read_text(encoding="utf-8")
        self.assertIn('f.start_with?("_gm-materials/")', content)

    def test_has_jekyll_exclude_with_crlf_and_blank_comment_lines(self):
        """Verify _has_jekyll_exclude recognises _gm-materials with CRLF endings and blank/comment lines in block lists."""
        cases = [
            # CRLF inline list
            "title: Test\r\nplugins: [oude-mechanismen]\r\nexclude: [_gm-materials]\r\n",
            # CRLF block list
            "title: Test\r\nplugins: [oude-mechanismen]\r\nexclude:\r\n  - _gm-materials\r\n",
            # CRLF block list with trailing slash and quotes
            'title: Test\r\nexclude:\r\n  - "_gm-materials/"\r\n',
            # LF block list with blank and comment lines before the item
            "title: Test\nexclude:\n\n  # private GM materials\n  - _gm-materials\n",
            # LF block list with blank and comment lines between items
            "title: Test\nexclude:\n  - Gemfile\n\n  # comment between items\n  - _gm-materials\n",
            # CRLF block list with blank and comment lines before and between items
            "title: Test\r\nexclude:\r\n\r\n  # private GM materials\r\n  - Gemfile\r\n\r\n  - _gm-materials\r\n",
        ]
        for content in cases:
            self.assertTrue(
                cli._has_jekyll_exclude(content, "_gm-materials"),
                f"_has_jekyll_exclude failed to detect _gm-materials in: {content!r}",
            )

        # Negative cases: entry absent or only as a substring
        negative_cases = [
            "title: Test\nexclude:\n  - Gemfile\n",
            "title: Test\nexclude: [Gemfile]\n",
            "title: Test\nexclude:\n  - _gm-materials-backup\n",
        ]
        for content in negative_cases:
            self.assertFalse(
                cli._has_jekyll_exclude(content, "_gm-materials"),
                f"_has_jekyll_exclude falsely detected _gm-materials in: {content!r}",
            )

    def test_append_jekyll_exclude_and_doctor_fix_with_crlf_and_blank_comment_lines(self):
        """Verify _append_jekyll_exclude and doctor --fix handle CRLF configs and block lists with blank/comment lines."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        config_path = self.target_dir / "_config.yml"

        # Case 1: CRLF inline exclude list
        config_path.write_bytes(b"title: Test\r\nplugins: [oude-mechanismen]\r\nexclude: [Gemfile]\r\n")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        updated = config_path.read_text(encoding="utf-8")
        self.assertIn('exclude: [Gemfile, "_gm-materials"]', updated)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

        # Case 2: CRLF block exclude with comment and blank line before the first item
        config_path.write_bytes(
            b"title: Test\r\nplugins: [oude-mechanismen]\r\nexclude:\r\n  # private materials\r\n\r\n  - Gemfile\r\n"
        )
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        updated = config_path.read_text(encoding="utf-8")
        self.assertIn('  - "_gm-materials"\n', updated)
        self.assertIn("  - Gemfile\n", updated)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

        # Case 3: CRLF config with no exclude section at all
        config_path.write_bytes(b"title: Test\r\nplugins: [oude-mechanismen]\r\n")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 1)
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        updated = config_path.read_text(encoding="utf-8")
        self.assertIn('exclude:\n  - "_gm-materials"\n', updated)
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

        # Direct unit checks on _append_jekyll_exclude
        appended = cli._append_jekyll_exclude("title: Test\r\nexclude: [Gemfile]\r\n")
        self.assertIn('exclude: [Gemfile, "_gm-materials"]', appended)
        appended = cli._append_jekyll_exclude("title: Test\r\nexclude:\r\n  # note\r\n\r\n  - Gemfile\r\n")
        self.assertIn('  - "_gm-materials"\r\n', appended)
        appended = cli._append_jekyll_exclude("title: Test\r\n")
        self.assertIn('exclude:\r\n  - "_gm-materials"\r\n', appended)

    def test_append_and_doctor_fix_with_bare_key_at_eof_without_trailing_newline(self):
        """Verify bare 'exclude:'/'plugins:' at EOF (LF and CRLF) are extended in place without duplicate keys."""
        # Direct unit checks on _append_jekyll_exclude / _append_jekyll_plugin
        unit_cases = [
            (cli._append_jekyll_exclude, "title: Test\nexclude:", 'title: Test\nexclude:\n  - "_gm-materials"\n'),
            (cli._append_jekyll_exclude, "title: Test\r\nexclude:", 'title: Test\r\nexclude:\r\n  - "_gm-materials"\r\n'),
            (cli._append_jekyll_plugin, "title: Test\nplugins:", "title: Test\nplugins:\n  - oude-mechanismen\n"),
            (cli._append_jekyll_plugin, "title: Test\r\nplugins:", "title: Test\r\nplugins:\r\n  - oude-mechanismen\r\n"),
        ]
        for func, initial, expected in unit_cases:
            updated = func(initial)
            self.assertEqual(updated, expected)
            key = "exclude" if "exclude" in initial else "plugins"
            self.assertEqual(updated.count(f"{key}:"), 1, f"Duplicate '{key}:' key emitted for {initial!r}")

        # End-to-end doctor --fix checks on a real vault
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )

        config_path = self.target_dir / "_config.yml"
        e2e_cases = [
            (
                "title: Test\nplugins: [oude-mechanismen]\nexclude:",
                'title: Test\nplugins: [oude-mechanismen]\nexclude:\n  - "_gm-materials"\n',
                "exclude",
            ),
            (
                # _doctor reads via read_text (universal newlines), so CRLF is normalised to LF on write
                "title: Test\r\nplugins: [oude-mechanismen]\r\nexclude:",
                'title: Test\nplugins: [oude-mechanismen]\nexclude:\n  - "_gm-materials"\n',
                "exclude",
            ),
            (
                "title: Test\nexclude: [_gm-materials]\nplugins:",
                "title: Test\nexclude: [_gm-materials]\nplugins:\n  - oude-mechanismen\n",
                "plugins",
            ),
            (
                "title: Test\r\nexclude: [_gm-materials]\r\nplugins:",
                "title: Test\nexclude: [_gm-materials]\nplugins:\n  - oude-mechanismen\n",
                "plugins",
            ),
        ]
        for initial, expected, key in e2e_cases:
            config_path.write_bytes(initial.encode("utf-8"))
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 1)
                self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
            updated = config_path.read_bytes().decode("utf-8")
            self.assertEqual(updated, expected)
            self.assertEqual(updated.count(f"{key}:"), 1, f"Duplicate '{key}:' key emitted for {initial!r}")
            with patch("sys.stdout", new=io.StringIO()):
                self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_agents_md_template_uses_jekyll_build_and_doctor_fix(self):
        """Verify templates/AGENTS.md.template references bundle exec jekyll build and oude doctor --fix, not the legacy ruby plugin."""
        template_path = REPO_ROOT / "templates" / "AGENTS.md.template"
        content = template_path.read_text(encoding="utf-8")
        self.assertNotIn("_plugins/data_extractor.rb", content)
        self.assertIn("bundle exec jekyll build", content)
        self.assertIn("oude doctor --fix", content)

        # Every Markdown heading must be followed by an immediately blank line
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            if line.startswith("#"):
                self.assertTrue(
                    idx + 1 < len(lines) and lines[idx + 1].strip() == "",
                    f"Heading at line {idx + 1} is not followed by a blank line: {line!r}",
                )

    def test_doctor_fix_rebuilds_catalogue_when_engine_version_stale(self):
        """Verify doctor --fix triggers bundle exec jekyll build when engine_version is outdated."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": "0.5.3", "total_entries": 5}),
            encoding="utf-8",
        )

        with patch("shutil.which", side_effect=lambda cmd: "/usr/bin/bundle" if cmd == "bundle" else None), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                rc = cli._doctor(self.target_dir, fix=True)
                self.assertEqual(rc, 0)
                self.assertIn("Stale catalogue engine_version (0.5.3", fake_out.getvalue())
                mock_sub.assert_called_with(
                    ["bundle", "exec", "jekyll", "build"],
                    cwd=str(self.target_dir),
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                )

    def test_doctor_fix_falls_back_to_bundle33(self):
        """Verify doctor --fix resolves bundle3.3 on Debian 13 when bundle is absent."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(json.dumps({"engine_version": "0.5.3", "total_entries": 5}), encoding="utf-8")

        def which_side_effect(cmd):
            return "/usr/bin/bundle3.3" if cmd == "bundle3.3" else None

        with patch("shutil.which", side_effect=which_side_effect), \
             patch("subprocess.run") as mock_sub:
            mock_sub.return_value = MagicMock(returncode=0)
            with patch("sys.stdout", new=io.StringIO()) as fake_out:
                rc = cli._doctor(self.target_dir, fix=True)
                self.assertEqual(rc, 0)
                self.assertIn("bundle3.3 exec jekyll build", fake_out.getvalue())
                mock_sub.assert_called_with(
                    ["bundle3.3", "exec", "jekyll", "build"],
                    cwd=str(self.target_dir),
                    capture_output=True,
                    encoding="utf-8",
                    errors="replace",
                )

    def test_doctor_warns_when_vendor_dir_exists(self):
        """Verify doctor emits an advisory warning when vendor/ exists inside the vault."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 10}),
            encoding="utf-8",
        )
        (self.target_dir / "vendor" / "bundle").mkdir(parents=True, exist_ok=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertIn("Local vendor/ directory detected", fake_out.getvalue())

    def test_data_extractor_skips_rewriting_unchanged_catalog(self):
        """Verify DataExtractor.extract does not churn catalog.json timestamp when content is unchanged."""
        if not shutil.which("ruby"):
            self.skipTest("ruby executable not found on host system")

        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            (vault / "campaigns" / "arc").mkdir(parents=True)
            # Include an unquoted YAML Date title (parsed as Date by Ruby YAML.safe_load)
            # and two misc notes sharing (type, title) to verify deterministic sorting.
            (vault / "campaigns" / "arc" / "ep001.md").write_text(
                "---\ntitle: 2026-11-12\ntype: chapter\n---\n\nFirst session prose.\n",
                encoding="utf-8",
            )
            (vault / "directory").mkdir(parents=True)
            (vault / "directory" / "a.md").write_text("---\ntitle: Shared\n---\n\nAlpha note.\n", encoding="utf-8")
            (vault / "directory" / "b.md").write_text("---\ntitle: Shared\n---\n\nBeta note.\n", encoding="utf-8")

            ruby_script = (
                "require 'fileutils'\n"
                "load File.join(ARGV[0], 'jekyll/_plugins/data_extractor.rb')\n"
                "r1 = OudeMechanismen::DataExtractor.extract(ARGV[1], write_catalog: true)\n"
                "sleep 1.1\n"
                "r2 = OudeMechanismen::DataExtractor.extract(ARGV[1], write_catalog: true)\n"
                "puts r1[:catalog]['generated']\n"
                "puts r2[:catalog]['generated']\n"
                "puts r1[:catalog]['entries'].any? { |e| e.key?('lastmod') }\n"
                "puts r1[:lastmod].key?('campaigns/arc/ep001.md')\n"
            )
            res = subprocess.run(
                ["ruby", "-I", str(REPO_ROOT / "lib"), "-e", ruby_script, str(REPO_ROOT), str(vault)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            ts1, ts2, has_entry_lastmod, has_site_lastmod = res.stdout.strip().splitlines()
            self.assertEqual(ts1, ts2, "catalog.json 'generated' timestamp should not change on identical rebuild")
            self.assertEqual(has_entry_lastmod, "false", "catalog.json entries should not carry 'lastmod'")
            self.assertEqual(has_site_lastmod, "true", "in-memory site.data.lastmod must remain populated")

    def test_data_extractor_strips_whitespace_trimmed_comments_from_summary(self):
        """Verify DataExtractor.extract strips {%- comment -%} blocks so stub summaries stay nil."""
        if not shutil.which("ruby"):
            self.skipTest("ruby executable not found on host system")

        with tempfile.TemporaryDirectory() as tmpdir:
            vault = Path(tmpdir)
            (vault / "directory").mkdir(parents=True)
            (vault / "directory" / "stub.md").write_text(
                "---\ntitle: Stub\n---\n\n"
                "{% include header_directories.md %}\n"
                "{%- comment -%}\nHidden GM crosslink text.\n{%- endcomment -%}\n",
                encoding="utf-8",
            )
            ruby_script = (
                "require 'json'\n"
                "load File.join(ARGV[0], 'jekyll/_plugins/data_extractor.rb')\n"
                "res = OudeMechanismen::DataExtractor.extract(ARGV[1], write_catalog: false)\n"
                "puts JSON.generate(res[:catalog]['entries'].first['summary'])\n"
            )
            res = subprocess.run(
                ["ruby", "-I", str(REPO_ROOT / "lib"), "-e", ruby_script, str(REPO_ROOT), str(vault)],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stderr)
            self.assertEqual(json.loads(res.stdout.strip()), None)

    def test_doctor_passes_with_advisory_when_catalog_missing_and_fails_when_corrupt(self):
        """Verify doctor treats missing catalog.json as an advisory local cache but fails on corrupt JSON."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        self.assertFalse(catalog_path.exists())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertIn("Tier 1 catalogue local cache not yet generated", fake_out.getvalue())

        catalog_path.write_text("{corrupt", encoding="utf-8")
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_corrupt = cli._doctor(self.target_dir)
            self.assertEqual(rc_corrupt, 1)
            self.assertIn("Corrupted catalog.json", fake_out.getvalue())

    def test_doctor_detects_and_untracks_git_tracked_catalog_json(self):
        """Verify doctor detects git-tracked catalog.json and --fix untracks it cleanly."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 1}),
            encoding="utf-8",
        )
        subprocess.run(["git", "-C", str(self.target_dir), "add", "-f", ".agents/context/catalog.json"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "commit", "-m", "track catalog"], check=True, capture_output=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn(".agents/context/catalog.json is tracked in Git", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("Untracked derived .agents/context/catalog.json", fake_out.getvalue())

        self.assertTrue(catalog_path.is_file(), "catalog.json should remain on disk after untracking")
        ls_res = subprocess.run(
            ["git", "-C", str(self.target_dir), "ls-files", "--error-unmatch", ".agents/context/catalog.json"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ls_res.returncode, 0, "catalog.json should no longer be tracked in Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_doctor_detects_and_untracks_git_tracked_rolling_glossary(self):
        """Verify doctor detects git-tracked rolling_glossary.md and --fix untracks it cleanly."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 1}),
            encoding="utf-8",
        )

        rg_path = self.target_dir / ".agents" / "context" / "rolling_glossary.md"
        rg_path.write_text("# Rolling Campaign Glossary\n", encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.target_dir), "add", "-f", ".agents/context/rolling_glossary.md"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.target_dir), "commit", "-m", "track rolling glossary"],
            check=True,
            capture_output=True,
        )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn(".agents/context/rolling_glossary.md is tracked in Git", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("Untracked derived .agents/context/rolling_glossary.md", fake_out.getvalue())

        self.assertTrue(rg_path.is_file(), "rolling_glossary.md should remain on disk after untracking")
        ls_res = subprocess.run(
            ["git", "-C", str(self.target_dir), "ls-files", "--error-unmatch", ".agents/context/rolling_glossary.md"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ls_res.returncode, 0, "rolling_glossary.md should no longer be tracked in Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_doctor_detects_and_untracks_git_tracked_references_json(self):
        """Verify doctor detects git-tracked references.json and --fix untracks it cleanly."""
        self.assertIn(".agents/context/references.json", cli.DERIVED_CACHE_FILES)
        self.assertIn(".agents/context/references.json", cli.REQUIRED_GITIGNORE_ENTRIES)
        self.assertTrue(
            any(line == ".agents/context/references.json" for line in cli.DEFAULT_GITIGNORE.splitlines()),
            "DEFAULT_GITIGNORE must carry an uncommented .agents/context/references.json line",
        )

        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)

        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)

        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 1}),
            encoding="utf-8",
        )

        ref_path = self.target_dir / ".agents" / "context" / "references.json"
        ref_path.write_text(json.dumps({"generated": "2026-01-01", "digests": []}), encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.target_dir), "add", "-f", ".agents/context/references.json"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.target_dir), "commit", "-m", "track references.json"],
            check=True,
            capture_output=True,
        )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn(".agents/context/references.json is tracked in Git", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("Untracked derived .agents/context/references.json", fake_out.getvalue())

        self.assertTrue(ref_path.is_file(), "references.json should remain on disk after untracking")
        ls_res = subprocess.run(
            ["git", "-C", str(self.target_dir), "ls-files", "--error-unmatch", ".agents/context/references.json"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ls_res.returncode, 0, "references.json should no longer be tracked in Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_default_gitignore_includes_all_required_entries(self):
        """Verify every REQUIRED_GITIGNORE_ENTRIES item appears uncommented in DEFAULT_GITIGNORE."""
        default_lines = cli.DEFAULT_GITIGNORE.splitlines()
        for entry in cli.REQUIRED_GITIGNORE_ENTRIES:
            self.assertIn(
                entry,
                default_lines,
                f"DEFAULT_GITIGNORE must carry an uncommented line for {entry}",
            )
            self.assertTrue(
                cli._has_gitignore_entry(cli.DEFAULT_GITIGNORE, entry),
                f"_has_gitignore_entry must recognise {entry} in DEFAULT_GITIGNORE",
            )




    def test_tier2_pass_through_and_derived_cache_guard_registered(self):
        """Design 006: oude tier2 pass-through, DERIVED_CACHE_FILES guard, retired decisions template."""
        self.assertEqual(cli.PASS_THROUGH_SCRIPTS.get("tier2"), "tier2.py")
        self.assertIn("_gm-materials/.cache/tier2.json", cli.DERIVED_CACHE_FILES)
        self.assertIn("_gm-materials/.cache/tier2.json", cli.REQUIRED_GITIGNORE_ENTRIES)
        self.assertTrue(
            any(line == "_gm-materials/.cache/tier2.json" for line in cli.DEFAULT_GITIGNORE.splitlines()),
            "DEFAULT_GITIGNORE must carry an uncommented _gm-materials/.cache/tier2.json line",
        )
        self.assertFalse(
            any("decisions.md.template" in src for src, _ in cli.TEMPLATE_MAPPINGS),
            "decisions.md.template must be retired from TEMPLATE_MAPPINGS",
        )
        self.assertFalse((REPO_ROOT / "templates" / "decisions.md.template").exists())

    def _write_healthy_vault(self):
        """Initialise a vault with a fresh catalog.json so doctor starts healthy."""
        with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
             patch.object(cli, "_install_skills", return_value=0):
            cli._init_repository(self.target_dir)
        catalog_path = self.target_dir / ".agents" / "context" / "catalog.json"
        catalog_path.write_text(
            json.dumps({"engine_version": cli.__version__, "total_entries": 1}),
            encoding="utf-8",
        )

    def _write_valid_ruling(self, ruling_id="R-001"):
        rulings_dir = self.target_dir / "_gm-materials" / "rulings"
        rulings_dir.mkdir(parents=True, exist_ok=True)
        (rulings_dir / f"{ruling_id}_slug.md").write_text(
            "---\n"
            f"id: {ruling_id}\n"
            "title: Test Ruling\n"
            "date: 2026-11-01\n"
            "kind: ruling\n"
            "status: active\n"
            "fact: The sky is red.\n"
            "entities: []\n"
            "---\n\n"
            "Narrative body.\n",
            encoding="utf-8",
        )

    def test_doctor_legacy_decisions_advisory_preserved_never_deleted(self):
        """Legacy decisions.md yields a warning advisory only; --fix never deletes it."""
        self._write_healthy_vault()
        decisions = self.target_dir / ".agents" / "context" / "decisions.md"
        decisions.write_text("- Decision: legacy ruling\n", encoding="utf-8")
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0, "legacy decisions.md advisory must not fail doctor")
            self.assertIn("decisions.md", fake_out.getvalue())
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("decisions.md", fake_out.getvalue())
        self.assertTrue(decisions.is_file(), "--fix must never auto-delete legacy decisions.md")

    def test_doctor_detects_and_untracks_git_tracked_tier2_cache(self):
        """Force-added _gm-materials/.cache/tier2.json is detected and --fix untracks it."""
        self._write_healthy_vault()
        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)

        cache_path = self.target_dir / "_gm-materials" / ".cache" / "tier2.json"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
        subprocess.run(
            ["git", "-C", str(self.target_dir), "add", "-f", "_gm-materials/.cache/tier2.json"],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(self.target_dir), "commit", "-m", "track tier2 cache"],
            check=True,
            capture_output=True,
        )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn("_gm-materials/.cache/tier2.json is tracked in Git", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("Untracked derived _gm-materials/.cache/tier2.json", fake_out.getvalue())

        self.assertTrue(cache_path.is_file(), "tier2.json should remain on disk after untracking")
        ls_res = subprocess.run(
            ["git", "-C", str(self.target_dir), "ls-files", "--error-unmatch", "_gm-materials/.cache/tier2.json"],
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(ls_res.returncode, 0, "tier2.json should no longer be tracked in the Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)


    def test_doctor_detects_and_untracks_any_tracked_gm_materials_path(self):
        """M3: tree-wide guard — force-added _gm-materials/rulings/*.md (private opinions)
        and any other tracked path under _gm-materials/ is detected and --fix untracks it."""
        self._write_healthy_vault()
        self._write_valid_ruling()
        notes_rel = "_gm-materials/session-summaries/ep_001_notes.md"
        notes_path = self.target_dir / notes_rel
        notes_path.parent.mkdir(parents=True, exist_ok=True)
        notes_path.write_text("# Session notes\n", encoding="utf-8")
        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)
        rulings_rel = "_gm-materials/rulings/R-001_slug.md"
        subprocess.run(["git", "-C", str(self.target_dir), "add", "-f", rulings_rel, notes_rel], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "commit", "-m", "leak gm materials"], check=True, capture_output=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            out = fake_out.getvalue()
            self.assertIn(f"{rulings_rel} is tracked in Git", out)
            self.assertIn(f"{notes_rel} is tracked in Git", out)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            out = fake_out.getvalue()
            self.assertIn(f"Untracked {rulings_rel} from Git index", out)
            self.assertIn(f"Untracked {notes_rel} from Git index", out)

        for rel in (rulings_rel, notes_rel):
            self.assertTrue((self.target_dir / rel).is_file(), f"{rel} must remain on disk after untracking")
            ls_res = subprocess.run(
                ["git", "-C", str(self.target_dir), "ls-files", "--error-unmatch", rel],
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(ls_res.returncode, 0, f"{rel} should no longer be tracked in the Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_doctor_gm_materials_guard_handles_non_ascii_filenames(self):
        """Non-ASCII ruling filenames are detected with the real path and --fix untracks them
        (ls-files -z NUL split, no C-quoting)."""
        self._write_healthy_vault()
        rulings_rel = "_gm-materials/rulings/R-001_são-paulo.md"
        rulings_path = self.target_dir / rulings_rel
        rulings_path.parent.mkdir(parents=True, exist_ok=True)
        rulings_path.write_text(
            "---\n"
            "id: R-001\n"
            "title: São Paulo ruling\n"
            "date: 2026-11-01\n"
            "kind: ruling\n"
            "status: active\n"
            "fact: The sky is red.\n"
            "entities: []\n"
            "---\n\n"
            "Narrative body.\n",
            encoding="utf-8",
        )
        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "add", "-f", rulings_rel], check=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn(f"{rulings_rel} is tracked in Git", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn(f"Untracked {rulings_rel} from Git index", fake_out.getvalue())

        self.assertTrue(rulings_path.is_file(), "ruling must remain on disk after untracking")
        ls_res = subprocess.run(
            ["git", "-C", str(self.target_dir), "ls-files", "-z", "--", "_gm-materials/"],
            capture_output=True,
            text=True,
        )
        self.assertNotIn(rulings_rel, ls_res.stdout.split("\0"), "ruling should no longer be tracked in the Git index")
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir), 0)

    def test_doctor_gm_materials_guard_prints_surrogate_paths_safely(self):
        """Surrogate-escaped paths and stderr print safely under strict UTF-8 stdout while keeping raw paths for git rm."""
        self._write_healthy_vault()
        (self.target_dir / ".git").mkdir()
        surrogate_rel = "_gm-materials/rulings/bad\udcffname.md"
        rm_calls = []

        def make_fake_run(rm_returncode=0, rm_stderr=""):
            def fake_run(cmd, **kwargs):
                if len(cmd) >= 2 and str(cmd[1]).endswith("generate_digests.py"):
                    return MagicMock(returncode=0, stdout="", stderr="")
                if "ls-files" in cmd and "--error-unmatch" in cmd:
                    return MagicMock(returncode=1, stdout="", stderr="")
                if "ls-files" in cmd and "-z" in cmd:
                    return MagicMock(returncode=0, stdout=f"{surrogate_rel}\0", stderr="")
                if "rm" in cmd:
                    rm_calls.append((cmd, kwargs))
                    return MagicMock(returncode=rm_returncode, stdout="", stderr=rm_stderr)
                raise AssertionError(f"Unexpected subprocess.run call: {cmd}")
            return fake_run

        with patch("shutil.which", side_effect=lambda name: "/usr/bin/git" if name == "git" else None):
            buf_detect = io.BytesIO()
            strict_detect = io.TextIOWrapper(buf_detect, encoding="utf-8", errors="strict")
            with patch("subprocess.run", side_effect=make_fake_run()), \
                 patch("sys.stdout", new=strict_detect):
                rc_detect = cli._doctor(self.target_dir)
                strict_detect.flush()
                out_detect = buf_detect.getvalue().decode("utf-8")
                strict_detect.detach()
            self.assertEqual(rc_detect, 1)
            self.assertIn("_gm-materials/rulings/bad\ufffdname.md is tracked in Git", out_detect)

            buf_fix_ok = io.BytesIO()
            strict_fix_ok = io.TextIOWrapper(buf_fix_ok, encoding="utf-8", errors="strict")
            with patch("subprocess.run", side_effect=make_fake_run(rm_returncode=0)), \
                 patch("sys.stdout", new=strict_fix_ok):
                rc_fix_ok = cli._doctor(self.target_dir, fix=True)
                strict_fix_ok.flush()
                out_fix_ok = buf_fix_ok.getvalue().decode("utf-8")
                strict_fix_ok.detach()
            self.assertEqual(rc_fix_ok, 0)
            self.assertIn("Untracked _gm-materials/rulings/bad\ufffdname.md from Git index", out_fix_ok)
            self.assertEqual(rm_calls[-1][0][-1], surrogate_rel)

            buf_fix_err = io.BytesIO()
            strict_fix_err = io.TextIOWrapper(buf_fix_err, encoding="utf-8", errors="strict")
            with patch("subprocess.run", side_effect=make_fake_run(rm_returncode=1, rm_stderr="fatal: bad\udcfferr\n")), \
                 patch("sys.stdout", new=strict_fix_err):
                rc_fix_err = cli._doctor(self.target_dir, fix=True)
                strict_fix_err.flush()
                out_fix_err = buf_fix_err.getvalue().decode("utf-8")
                strict_fix_err.detach()
            self.assertEqual(rc_fix_err, 1)
            self.assertIn("Failed to untrack _gm-materials/rulings/bad\ufffdname.md: fatal: bad\ufffderr", out_fix_err)

    def test_doctor_gm_materials_guard_ignores_derived_cache_double_report(self):
        """A force-added _gm-materials/.cache/tier2.json is reported once via DERIVED_CACHE_FILES."""
        self._write_healthy_vault()
        subprocess.run(["git", "init", "-b", "main", str(self.target_dir)], check=True, capture_output=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.email", "test@example.com"], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "config", "user.name", "Test"], check=True)
        cache_rel = "_gm-materials/.cache/tier2.json"
        cache_path = self.target_dir / cache_rel
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8")
        subprocess.run(["git", "-C", str(self.target_dir), "add", "-f", cache_rel], check=True)
        subprocess.run(["git", "-C", str(self.target_dir), "commit", "-m", "track cache"], check=True, capture_output=True)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            out = fake_out.getvalue()
            self.assertEqual(out.count(f"{cache_rel} is tracked in Git"), 1, "derived cache must be reported exactly once")

    def test_doctor_empty_rulings_dir_produces_no_missing_index_warning(self):
        """An empty _gm-materials/rulings/ must stay silent (no unfixable WARN)."""
        self._write_healthy_vault()
        (self.target_dir / "_gm-materials" / "rulings").mkdir(parents=True, exist_ok=True)
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertNotIn("tier2.json absent", fake_out.getvalue())
            self.assertFalse((self.target_dir / "_gm-materials" / ".cache" / "tier2.json").exists())

    def test_doctor_stale_tier2_cache_advisory_and_fix_refresh(self):
        """Rulings present: absent cache warns; stale cache warns; --fix recompiles via tier2.py."""
        self._write_healthy_vault()
        self._write_valid_ruling()

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0, "missing tier2.json is an advisory, not a failure")
            self.assertIn("tier2.json absent", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("tier2.py", fake_out.getvalue())
        cache_path = self.target_dir / "_gm-materials" / ".cache" / "tier2.json"
        self.assertTrue(cache_path.is_file(), "--fix must compile _gm-materials/.cache/tier2.json")
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
        self.assertEqual(cache["schema_version"], 1)
        self.assertEqual([e["id"] for e in cache["entries"]], ["R-001"])

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertIn("fresh", fake_out.getvalue())

        # Make the cache stale by editing the ruling, then confirm the advisory and --fix refresh.
        ruling_path = self.target_dir / "_gm-materials" / "rulings" / "R-001_slug.md"
        ruling_path.write_text(
            ruling_path.read_text(encoding="utf-8") + "\nExtra line.\n",
            encoding="utf-8",
        )
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertIn("stale", fake_out.getvalue())
        with patch("sys.stdout", new=io.StringIO()):
            self.assertEqual(cli._doctor(self.target_dir, fix=True), 0)
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            self.assertEqual(cli._doctor(self.target_dir), 0)
            self.assertIn("fresh", fake_out.getvalue())

    def test_doctor_invalid_rulings_fail_compilation_under_fix(self):
        """A FAIL-severity ruling makes tier2.py fail and doctor --fix report the failure."""
        self._write_healthy_vault()
        rulings_dir = self.target_dir / "_gm-materials" / "rulings"
        rulings_dir.mkdir(parents=True, exist_ok=True)
        (rulings_dir / "R-001_slug.md").write_text(
            "---\nid: R-1\ntitle: Bad\n---\n\nBody.\n",
            encoding="utf-8",
        )
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 1, "invalid rulings must fail doctor --fix")
            self.assertIn("tier2.py", fake_out.getvalue())
        self.assertFalse((self.target_dir / "_gm-materials" / ".cache" / "tier2.json").exists())

    def test_doctor_warns_and_fixes_legacy_digest_type_keys(self):
        """Legacy digest entity_type warns and exits 1 in doctor; --fix migrates to canonical type."""
        self._write_healthy_vault()
        digest_path = self.target_dir / "_gm-materials" / "digests" / "book" / "npc.md"
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        digest_path.write_text(
            "---\nsource: book\ntier: 3\nentity_type: person\ntitle: NPC\n---\n\n# NPC\n\nBody.\n",
            encoding="utf-8",
        )

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 1)
            self.assertIn("Legacy digest type keys (run oude doctor --fix)", fake_out.getvalue())

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 0)
            self.assertIn("Digest type keys migrated to canonical 'type'", fake_out.getvalue())

        migrated = digest_path.read_text(encoding="utf-8")
        self.assertIn("type: people", migrated)
        self.assertNotIn("entity_type", migrated)

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            self.assertEqual(cli._doctor(self.target_dir), 0)
            self.assertIn("Digest type keys", fake_out.getvalue())

    def test_doctor_reports_digest_type_conflicts(self):
        """Conflicting type/entity_type keys make doctor --fix fail loudly without altering the note."""
        self._write_healthy_vault()
        digest_path = self.target_dir / "_gm-materials" / "digests" / "book" / "conflict.md"
        digest_path.parent.mkdir(parents=True, exist_ok=True)
        raw = "---\nsource: book\ntier: 3\ntype: faction\nentity_type: location\ntitle: C\n---\n\n# C\n\nBody.\n"
        digest_path.write_text(raw, encoding="utf-8")

        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_fix = cli._doctor(self.target_dir, fix=True)
            self.assertEqual(rc_fix, 1)
            self.assertIn("Digest type conflicts need manual edits", fake_out.getvalue())
        self.assertEqual(digest_path.read_text(encoding="utf-8"), raw)

    def test_doctor_skips_digest_type_check_when_digests_dir_absent(self):
        """Absent _gm-materials/digests/ passes cleanly without warning or failing."""
        self._write_healthy_vault()
        with patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc = cli._doctor(self.target_dir)
            self.assertEqual(rc, 0)
            self.assertIn("Digest type keys", fake_out.getvalue())

    def test_doctor_vault_flag_migrates_target_vault_not_cwd(self):
        """oude doctor --vault <other> --fix migrates <other>, leaving CWD untouched."""
        with tempfile.TemporaryDirectory() as tmp:
            cwd_vault = Path(tmp) / "cwd_vault"
            other_vault = Path(tmp) / "other_vault"
            legacy_note = "---\nsource: book\ntier: 3\nentity_type: person\ntitle: NPC\n---\n\n# NPC\n\nBody.\n"

            for vault in (cwd_vault, other_vault):
                with patch.object(cli, "_enable_auto_branch_deletion", return_value=True), \
                     patch.object(cli, "_install_skills", return_value=0):
                    cli._init_repository(vault)
                (vault / ".agents" / "context" / "catalog.json").write_text(
                    json.dumps({"engine_version": cli.__version__, "total_entries": 1}),
                    encoding="utf-8",
                )
                note = vault / "_gm-materials" / "digests" / "book" / "npc.md"
                note.parent.mkdir(parents=True, exist_ok=True)
                note.write_text(legacy_note, encoding="utf-8")

            prev_cwd = Path.cwd()
            try:
                os.chdir(cwd_vault)
                with patch("sys.stdout", new=io.StringIO()):
                    rc = cli.main(["doctor", "--vault", str(other_vault), "--fix"])
            finally:
                os.chdir(prev_cwd)

            self.assertEqual(rc, 0)
            other_text = (other_vault / "_gm-materials" / "digests" / "book" / "npc.md").read_text(encoding="utf-8")
            cwd_text = (cwd_vault / "_gm-materials" / "digests" / "book" / "npc.md").read_text(encoding="utf-8")
            self.assertIn("type: people", other_text)
            self.assertNotIn("entity_type", other_text)
            self.assertEqual(cwd_text, legacy_note)

    def test_doctor_digest_type_dry_run_is_quiet_and_reports_missing_script(self):
        """Dry-run probe runs quietly (DEVNULL), and missing generate_digests.py returns 127 and fails clearly."""
        with patch("subprocess.run", return_value=MagicMock(returncode=0)) as mock_sub:
            rc = cli._run_script("generate_digests.py", ["--help"], quiet=True)
        self.assertEqual(rc, 0)
        self.assertEqual(mock_sub.call_args.kwargs.get("stdout"), subprocess.DEVNULL)
        self.assertEqual(mock_sub.call_args.kwargs.get("stderr"), subprocess.DEVNULL)

        with patch("sys.stderr", new=io.StringIO()) as fake_err:
            rc_missing = cli._run_script("definitely_missing_script_xyz.py", [])
        self.assertEqual(rc_missing, 127)
        self.assertIn("not found", fake_err.getvalue())

        self._write_healthy_vault()
        with patch.object(cli, "_run_script", return_value=127) as mock_run_script, \
             patch("sys.stdout", new=io.StringIO()) as fake_out:
            rc_doc = cli._doctor(self.target_dir)
        self.assertEqual(rc_doc, 1)
        out = fake_out.getvalue()
        self.assertIn("Bundled scripts/generate_digests.py not found", out)
        self.assertNotIn("Legacy digest type keys", out)
        self.assertEqual(mock_run_script.call_args.kwargs.get("quiet"), True)


class TestDependabotGuard(unittest.TestCase):
    """Regression tests for the vault Dependabot ignore guard (issue #76)."""

    def test_gemfile_matcher_single_line_git_tag(self):
        gemfile = 'gem "oude-mechanismen", git: "https://example.com/x.git", tag: "v0.7.2"\n'
        self.assertTrue(cli._gemfile_pins_engine_via_git(gemfile))

    def test_gemfile_matcher_multiline_and_shorthands(self):
        multiline = 'gem "oude-mechanismen",\n  github: "terra-campaigns/oude-mechanismen",\n  tag: "v0.7.2"\n'
        self.assertTrue(cli._gemfile_pins_engine_via_git(multiline))
        gitlab = 'gem "oude-mechanismen", gitlab: "group/oude-mechanismen", ref: "main"\n'
        self.assertTrue(cli._gemfile_pins_engine_via_git(gitlab))
        bitbucket = 'gem "oude-mechanismen", bitbucket: "team/oude-mechanismen", branch: "develop"\n'
        self.assertTrue(cli._gemfile_pins_engine_via_git(bitbucket))

    def test_gemfile_matcher_registry_pinned_is_not_git(self):
        self.assertFalse(cli._gemfile_pins_engine_via_git('gem "oude-mechanismen", "~> 0.7"\n'))
        self.assertFalse(cli._gemfile_pins_engine_via_git('gem "jekyll", "~> 4.3"\n'))
        # A registry-pinned engine must not match a later, unrelated git-sourced gem.
        mixed = 'gem "oude-mechanismen", "~> 0.7"\ngem "jekyll-theme", git: "https://x.git", tag: "v1.0"\n'
        self.assertFalse(cli._gemfile_pins_engine_via_git(mixed))
        # Commented-out pins and bare git sources (no tag/ref/branch).
        commented = '# gem "oude-mechanismen", git: "https://x.git", tag: "v1"\n'
        self.assertFalse(cli._gemfile_pins_engine_via_git(commented))
        bare_git = 'gem "oude-mechanismen", git: "https://x.git"\n'
        self.assertTrue(cli._gemfile_pins_engine_via_git(bare_git))

    def test_ignores_engine_scoped_to_bundler_update(self):
        bundler_ignore = (
            "version: 2\nupdates:\n  - package-ecosystem: \"bundler\"\n"
            "    directory: \"/\"\n    ignore:\n      - dependency-name: \"oude-mechanismen\"\n"
        )
        self.assertTrue(cli._dependabot_ignores_engine(bundler_ignore))
        flow_style = "version: 2\nupdates: [{package-ecosystem: bundler, ignore: [{dependency-name: oude-mechanismen}]}]\n"
        self.assertTrue(cli._dependabot_ignores_engine(flow_style))
        # Same-named ignore under a different ecosystem must NOT count.
        other_ecosystem = (
            "version: 2\nupdates:\n  - package-ecosystem: \"github-actions\"\n"
            "    directory: \"/\"\n    ignore:\n      - dependency-name: \"oude-mechanismen\"\n"
        )
        self.assertFalse(cli._dependabot_ignores_engine(other_ecosystem))
        self.assertFalse(cli._dependabot_ignores_engine("version: 2\nupdates: []\n"))
        self.assertFalse(cli._dependabot_ignores_engine("not: [valid, yaml: {"))

    def test_append_managed_block_when_no_updates_key(self):
        import yaml as _yaml
        result = cli._append_managed_updates_block("version: 2\n")
        self.assertIsNotNone(result)
        _yaml.safe_load(result)  # must stay valid YAML
        self.assertTrue(cli._dependabot_ignores_engine(result))

    def test_append_managed_block_refuses_existing_updates_key(self):
        # Block or flow style: caller must instruct a manual edit instead.
        self.assertIsNone(cli._append_managed_updates_block("version: 2\nupdates: []\n"))
        self.assertIsNone(cli._append_managed_updates_block('version: 2\n"updates": []\n'))
        block = "version: 2\nupdates:\n  - package-ecosystem: \"github-actions\"\n    directory: \"/\"\n"
        self.assertIsNone(cli._append_managed_updates_block(block))

    def test_template_itself_carries_the_ignore_rule(self):
        template = cli.resolve_asset_dir("templates/github/dependabot.yml.template").read_text(encoding="utf-8")
        self.assertTrue(cli._dependabot_ignores_engine(template))
        self.assertNotIn("versions:", template)

if __name__ == "__main__":
    unittest.main()
