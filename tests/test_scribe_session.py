#!/usr/bin/env python3
"""
Unit tests for scripts/scribe_session.py and scripts/benchmark_models.py.
Verifies:
1. Stage 0 Pre-Flight Repository Reconnaissance (clean/dirty, collision detection, --force override).
2. Markdown cleanliness enforcement (blank line following every heading).
3. Surgical character dossier YAML front matter updates (conditions list, trackers, preserving markdown body).
4. Benchmark auditing metrics (sentence-per-line, 2-4 rule, glossary recall).
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import scribe_session
import benchmark_models


class TestScribeSession(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="scribe_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")
        (self.repo_root / "campaigns" / "test").mkdir(parents=True)
        (self.repo_root / "directory" / "PCs").mkdir(parents=True)

        # Initialize git repo in test directory
        subprocess.run(["git", "init", "-b", "main"], cwd=self.repo_root, capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "Test Agent"], cwd=self.repo_root, check=True)
        subprocess.run(["git", "config", "user.email", "agent@test.local"], cwd=self.repo_root, check=True)

        # Commit initial state
        (self.repo_root / ".agents" / "context" / "catalog.json").write_text(json.dumps([{"title": "Olmo"}]), encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo_root, check=True)
        subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=self.repo_root, check=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_markdown_cleanliness_enforcement(self):
        """Verify that enforce_markdown_cleanliness inserts an empty blank line after headings."""
        raw = "# Heading 1\nText directly below heading\n## Subheading\nLine 1\nLine 2\n"
        cleaned = scribe_session.enforce_markdown_cleanliness(raw)
        expected = "# Heading 1\n\nText directly below heading\n## Subheading\n\nLine 1\nLine 2\n"
        self.assertEqual(cleaned, expected)

    def test_stage_0_recon_clean(self):
        """Verify Stage 0 recon passes on clean working tree without collisions."""
        recon = scribe_session.stage_0_recon(self.repo_root, force=False)
        self.assertTrue(recon["is_clean"])
        self.assertFalse(recon["is_blocked"])
        self.assertEqual(recon["branch"], "main")
        self.assertIn("valid (1 entries)", recon["catalogue_status"])

    def test_stage_0_recon_dirty_blocks_without_force(self):
        """Verify Stage 0 recon blocks when working tree is dirty and force=False."""
        dirty_file = self.repo_root / "campaigns" / "test" / "uncommitted.md"
        dirty_file.write_text("Uncommitted changes\n", encoding="utf-8")

        with self.assertRaises(RuntimeError) as ctx:
            scribe_session.stage_0_recon(self.repo_root, force=False)
        self.assertIn("Uncommitted changes detected", str(ctx.exception))

    def test_stage_0_recon_dirty_allowed_with_force(self):
        """Verify Stage 0 recon permits dirty working tree when force=True."""
        dirty_file = self.repo_root / "campaigns" / "test" / "uncommitted.md"
        dirty_file.write_text("Uncommitted changes\n", encoding="utf-8")

        recon = scribe_session.stage_0_recon(self.repo_root, force=True)
        self.assertFalse(recon["is_clean"])
        self.assertFalse(recon["is_blocked"])

    def test_stage_0_recon_target_collision_detection(self):
        """Verify Stage 0 recon detects existing non-empty chapter file and blocks unless force=True."""
        target_chapter = self.repo_root / "campaigns" / "test" / "001.md"
        target_chapter.write_text("Existing chapter content\n", encoding="utf-8")

        next_info = {"next_chapter_file": "campaigns/test/001.md"}

        # Blocked without force
        with self.assertRaises(RuntimeError) as ctx:
            scribe_session.stage_0_recon(self.repo_root, force=False, next_chapter_info=next_info)
        self.assertIn("Target chapter file already exists", str(ctx.exception))

        # Allowed with force
        recon = scribe_session.stage_0_recon(self.repo_root, force=True, next_chapter_info=next_info)
        self.assertTrue(recon["collision_detected"])

    def test_update_character_front_matter_preserves_body(self):
        """Verify update_character_front_matter modifies YAML trackers while leaving body untouched."""
        char_file = self.repo_root / "directory" / "PCs" / "Olmo.md"
        original_body = "\n\n{% include header_directories.md %}\n\n## Bio\nOlmo is an android scrapper.\n"
        char_content = f"""---
layout: default
type: people
title: Olmo
role: Scrapper
bends: 10
stress: d8
conditions:
  - Leaking hydraulic joint
---{original_body}"""
        char_file.write_text(char_content, encoding="utf-8")

        modified, diff = scribe_session.update_character_front_matter(
            char_file,
            new_conditions=["Concussion from airlock pressure surge"],
            cleared_conditions=["Leaking hydraulic joint"],
            tracker_updates={"stress": "d10", "bends": 12},
            dry_run=False,
        )

        self.assertTrue(modified)
        self.assertIn("+ condition: Concussion from airlock pressure surge", diff)
        self.assertIn("- condition: Leaking hydraulic joint", diff)
        self.assertIn("~ stress: d8 -> d10", diff)

        updated_text = char_file.read_text(encoding="utf-8")
        # Ensure markdown body is byte-for-byte identical
        self.assertTrue(updated_text.endswith(original_body))
        # Ensure conditions updated
        self.assertIn("Concussion from airlock pressure surge", updated_text)
        self.assertNotIn("Leaking hydraulic joint", updated_text)
        self.assertIn("bends: 12", updated_text)

    def test_reconcile_character_conditions_parsing(self):
        """Verify reconcile_character_conditions parses bullet points and updates directory files."""
        char_file = self.repo_root / "directory" / "PCs" / "Ezekiel.md"
        char_content = """---
layout: default
type: people
title: Ezekiel
role: Spacer
conditions: []
---

## Notes
Spacer notes.
"""
        char_file.write_text(char_content, encoding="utf-8")

        notes_text = """## 5. Combat, Hazards & Encounters
- Ezekiel: Acute panic and tremors
"""
        reconciled = scribe_session.reconcile_character_conditions(self.repo_root, notes_text, dry_run=False)
        self.assertEqual(len(reconciled), 1)
        self.assertTrue(reconciled[0]["modified"])

        updated_text = char_file.read_text(encoding="utf-8")
        self.assertIn("Acute panic and tremors", updated_text)
        self.assertTrue(updated_text.endswith("\n\n## Notes\nSpacer notes.\n"))

    def test_benchmark_auditing_metrics(self):
        """Verify metric evaluation functions in benchmark_models.py."""
        clean_md = "# Title\n\n## Section 1\n\nSentence one.\nSentence two.\n"
        dirty_md = "# Title\nNo blank line.\n"

        self.assertEqual(benchmark_models.audit_heading_cleanliness(clean_md), 100.0)
        self.assertEqual(benchmark_models.audit_heading_cleanliness(dirty_md), 0.0)

        spl_text = "Sentence one.\nSentence two.\nSentence three.\n"
        self.assertEqual(benchmark_models.audit_sentence_per_line(spl_text), 100.0)

        glossary_sample = "- Olmo: Scrapper\n- Ezekiel: Spacer\n- Cloudbank: Station"
        text_with_glossary = "Olmo and Ezekiel arrived at Cloudbank."
        self.assertEqual(benchmark_models.audit_glossary_recall(text_with_glossary, glossary_sample), 100.0)


if __name__ == "__main__":
    unittest.main()
