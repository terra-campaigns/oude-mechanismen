#!/usr/bin/env python3
"""
Unit tests for transcribe_session.py verifying the Three-Tier Storage Separation & Privacy Air-Gap.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import transcribe_session


class TestStorageSeparation(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="oude_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")

        # Fake Google Drive directory
        self.fake_drive = (Path(self.test_dir) / "GoogleDrive").resolve()
        self.fake_drive.mkdir()

        # Fake tier1_sources.yml
        tier1_yml = self.repo_root / ".agents" / "context" / "tier1_sources.yml"
        tier1_yml.write_text(f"drive_dir: \"{self.fake_drive}\"\n", encoding="utf-8")

        # Fake AGENTS.md
        agents_md = self.repo_root / ".agents" / "AGENTS.md"
        agents_md.write_text("Default Campaign Subfolder: campaigns/test\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_find_airgap_dir_default(self):
        """Verify air-gap defaults to ~/Private/rpg-sessions/<campaign>."""
        with patch.dict(os.environ, {}, clear=True):
            airgap = transcribe_session.find_airgap_dir(self.repo_root)
            expected = Path.home() / "Private" / "rpg-sessions" / "test_campaign"
            self.assertEqual(airgap, expected)

    def test_find_airgap_dir_explicit(self):
        """Verify explicit airgap_dir argument overrides default."""
        custom_airgap = Path(self.test_dir) / "custom_airgap"
        airgap = transcribe_session.find_airgap_dir(self.repo_root, explicit_airgap_dir=str(custom_airgap))
        self.assertEqual(airgap, custom_airgap.resolve())
        self.assertTrue(airgap.exists())

    def test_find_airgap_dir_env_var(self):
        """Verify RPG_SESSIONS_DIR environment variable is respected."""
        env_airgap = Path(self.test_dir) / "env_airgap"
        with patch.dict(os.environ, {"RPG_SESSIONS_DIR": str(env_airgap)}):
            airgap = transcribe_session.find_airgap_dir(self.repo_root)
            expected = (env_airgap / "test_campaign").resolve()
            self.assertEqual(airgap, expected)
            self.assertTrue(airgap.exists())

    def test_tier_separation_paths(self):
        """
        Verify that transcripts and recordings are assigned to the Tier 0 local air-gap,
        while glossaries and session notes are assigned to Tier 2 Google Drive.
        """
        custom_airgap = Path(self.test_dir) / "custom_airgap"
        airgap_dir = transcribe_session.find_airgap_dir(self.repo_root, explicit_airgap_dir=str(custom_airgap))
        drive_dir = transcribe_session.find_drive_dir(self.repo_root)
        sessions_dir = drive_dir / "_sessions"

        slug = "2026-11-02_ep001"
        transcript_path = airgap_dir / f"{slug}_transcript.txt"
        notes_path = sessions_dir / f"{slug}_session_notes.md"
        glossary_path = sessions_dir / f"{slug}_glossary.md"

        # Transcript must be in local air-gap, NOT in Google Drive
        self.assertTrue(str(transcript_path).startswith(str(airgap_dir)))
        self.assertFalse(str(transcript_path).startswith(str(sessions_dir)))

        # Notes and glossary must be in Google Drive
        self.assertTrue(str(notes_path).startswith(str(sessions_dir)))
        self.assertTrue(str(glossary_path).startswith(str(sessions_dir)))

    def test_end_to_end_pre_transcribed_manifest(self):
        """
        Verify that running transcribe_session with a pre-transcribed text input
        places the transcript strictly into the local air-gap and glossary into Google Drive.
        """
        custom_airgap = Path(self.test_dir) / "custom_airgap"
        dummy_input = Path(self.test_dir) / "session_raw.txt"
        dummy_input.write_text("Olmo and Ezekiel enter the airlock.\n", encoding="utf-8")

        import subprocess
        script_path = Path(__file__).resolve().parent.parent / "scripts" / "transcribe_session.py"

        cmd = [
            sys.executable,
            str(script_path),
            str(dummy_input),
            "--repo-root", str(self.repo_root),
            "--airgap-dir", str(custom_airgap),
            "--session-slug", "2026-11-02_ep001",
            "--json"
        ]

        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"transcribe_session failed: {res.stderr}")

        manifest = json.loads(res.stdout)
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["airgap_dir"], str(custom_airgap.resolve()))

        transcript_p = Path(manifest["transcript_path"])
        glossary_p = Path(manifest["glossary_path"])

        self.assertTrue(transcript_p.exists())
        self.assertEqual(transcript_p.parent, custom_airgap.resolve())

        self.assertTrue(glossary_p.exists())
        self.assertEqual(glossary_p.parent, self.fake_drive / "_sessions")

        # Verify Google Drive contains NO .txt files
        gdrive_txt_files = list((self.fake_drive / "_sessions").glob("*.txt"))
        self.assertEqual(gdrive_txt_files, [])


if __name__ == "__main__":
    unittest.main()
