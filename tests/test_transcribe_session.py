#!/usr/bin/env python3
"""
Unit tests for transcribe_session.py verifying the Four-Tier Storage Separation & Privacy Air-Gap.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        sessions_dir = drive_dir / "_gm-materials" / "session-summaries"

        slug = "2026-11-02_ep001"
        transcript_path = airgap_dir / f"{slug}_transcript.txt"
        notes_path = sessions_dir / f"{slug}_session_notes.md"
        glossary_path = sessions_dir / f"{slug}_glossary.md"
        tactical_facts_path = sessions_dir / f"{slug}_tactical_facts.md"
        sensory_textures_path = sessions_dir / f"{slug}_sensory_textures.md"

        # Transcript must be in local air-gap, NOT in Google Drive
        self.assertTrue(str(transcript_path).startswith(str(airgap_dir)))
        self.assertFalse(str(transcript_path).startswith(str(sessions_dir)))

        # Notes, glossary, tactical facts, and sensory textures must be in Google Drive
        self.assertTrue(str(notes_path).startswith(str(sessions_dir)))
        self.assertTrue(str(glossary_path).startswith(str(sessions_dir)))
        self.assertTrue(str(tactical_facts_path).startswith(str(sessions_dir)))
        self.assertTrue(str(sensory_textures_path).startswith(str(sessions_dir)))

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
        expected_sessions_dir = self.fake_drive / "_gm-materials" / "session-summaries"

        self.assertTrue(transcript_p.exists())
        self.assertEqual(transcript_p.parent, custom_airgap.resolve())

        self.assertTrue(glossary_p.exists())
        self.assertEqual(glossary_p.parent, expected_sessions_dir)

        self.assertIn("tactical_facts_path", manifest)
        self.assertIn("sensory_textures_path", manifest)
        self.assertEqual(Path(manifest["tactical_facts_path"]).parent, expected_sessions_dir)
        self.assertEqual(Path(manifest["sensory_textures_path"]).parent, expected_sessions_dir)

        # Verify Google Drive contains NO .txt files
        gdrive_txt_files = list(expected_sessions_dir.glob("*.txt"))
        self.assertEqual(gdrive_txt_files, [])

    def test_find_drive_dir_relative_and_fallback(self):
        """Verify relative drive_dir resolves against repo_root and missing/empty falls back to repo_root."""
        tier1_yml = self.repo_root / ".agents" / "context" / "tier1_sources.yml"
        tier1_yml.write_text('drive_dir: "."\n', encoding="utf-8")
        other_cwd = Path(self.test_dir) / "elsewhere"
        other_cwd.mkdir()
        prev_cwd = Path.cwd()
        try:
            os.chdir(other_cwd)
            self.assertEqual(transcribe_session.find_drive_dir(self.repo_root), self.repo_root.resolve())
        finally:
            os.chdir(prev_cwd)

        tier1_yml.write_text('drive_dir: ""\n', encoding="utf-8")
        self.assertEqual(transcribe_session.find_drive_dir(self.repo_root), self.repo_root.resolve())
        tier1_yml.unlink()
        self.assertEqual(transcribe_session.find_drive_dir(self.repo_root), self.repo_root.resolve())

    def test_find_drive_dir_nonexistent_or_file_raises(self):
        """Verify find_drive_dir raises FileNotFoundError when path is missing or is a regular file."""
        with self.assertRaises(FileNotFoundError):
            transcribe_session.find_drive_dir(self.repo_root, explicit_drive_dir="missing_dir")

        regular_file = self.repo_root / "not_a_dir.txt"
        regular_file.write_text("file\n", encoding="utf-8")
        with self.assertRaises(FileNotFoundError):
            transcribe_session.find_drive_dir(self.repo_root, explicit_drive_dir="not_a_dir.txt")


class TestFindDriveDirErrorPropagation(unittest.TestCase):
    """Verify find_drive_dir propagates configuration errors loudly instead of silently falling back."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="oude_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")
        self.tier1_yml = self.repo_root / ".agents" / "context" / "tier1_sources.yml"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_find_drive_dir_propagates_yaml_error(self):
        """Verify malformed YAML in tier1_sources.yml raises yaml.YAMLError rather than falling back."""
        import yaml
        self.tier1_yml.write_text("drive_dir: [unclosed\n", encoding="utf-8")
        with self.assertRaises(yaml.YAMLError):
            transcribe_session.find_drive_dir(self.repo_root)

    def test_find_drive_dir_propagates_oserror_when_config_is_directory(self):
        """Verify an OSError (tier1_sources.yml is a directory) propagates instead of falling back."""
        self.tier1_yml.mkdir()
        with self.assertRaises(OSError):
            transcribe_session.find_drive_dir(self.repo_root)

    def test_find_drive_dir_propagates_unicode_decode_error(self):
        """Verify invalid UTF-8 bytes in tier1_sources.yml raise UnicodeDecodeError instead of falling back."""
        self.tier1_yml.write_bytes(b"drive_dir: \"\xff\xfe\x00invalid\"\n")
        with self.assertRaises(UnicodeDecodeError):
            transcribe_session.find_drive_dir(self.repo_root)




class TestActiveRulingsInGlossary(unittest.TestCase):
    """Design 006: build_dynamic_glossary ingests active Tier 2 rulings via tier2.load_active_rulings_text."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="oude_tier2_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")
        self.out_glossary = self.repo_root / "glossary.md"

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def _write_ruling(self, rel: str, text: str) -> None:
        path = self.repo_root / "_gm-materials" / "rulings" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def test_active_rulings_included_when_rulings_dir_exists(self):
        self._write_ruling(
            "R-001_tribute.md",
            "---\nid: R-001\ntitle: Tribute\ndate: 2026-11-01\nkind: faction-turn\nstatus: active\n"
            "fact: The Piot Chants pay tribute.\nentities: []\nactors: [piot_chant]\n"
            "opinions:\n  - actor: piot_chant\n    vote: 1\n    shifted: false\n    stance: Go.\n"
            "---\n\nNarrative.\n",
        )
        content, _nouns = transcribe_session.build_dynamic_glossary(
            self.repo_root, self.out_glossary, "2026-11-02_ep001"
        )
        self.assertIn("## 5. Active Tier 2 Table Rulings & Decisions", content)
        self.assertIn("- **R-001 — Tribute:** The Piot Chants pay tribute.", content)

    def test_non_active_rulings_excluded_and_stale_cache_ignored(self):
        self._write_ruling(
            "R-001_old.md",
            "---\nid: R-001\ntitle: Old\ndate: 2026-11-01\nkind: ruling\nstatus: superseded\n"
            "fact: Old fact.\nentities: []\n---\n\nB.\n",
        )
        self._write_ruling(
            "R-002_new.md",
            "---\nid: R-002\ntitle: New\ndate: 2026-11-02\nkind: ruling\nstatus: active\n"
            "supersedes: [R-001]\nfact: New fact.\nentities: []\n---\n\nB.\n",
        )
        # A stale derived cache claiming a bogus active ruling must be ignored.
        cache = self.repo_root / "_gm-materials" / ".cache" / "tier2.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"schema_version": 1, "entries": [
            {"id": "R-999", "title": "Stale", "status": "active", "fact": "Stale fact."}
        ]}), encoding="utf-8")
        content, _ = transcribe_session.build_dynamic_glossary(
            self.repo_root, self.out_glossary, "2026-11-02_ep001"
        )
        self.assertIn("New fact.", content)
        self.assertNotIn("Old fact.", content)
        self.assertNotIn("Stale fact.", content)

    def test_read_only_legacy_decisions_fallback_when_rulings_absent(self):
        decisions = self.repo_root / ".agents" / "context" / "decisions.md"
        decisions.write_text("- Decision: Legacy ruling stays.\n", encoding="utf-8")
        content, _ = transcribe_session.build_dynamic_glossary(
            self.repo_root, self.out_glossary, "2026-11-02_ep001"
        )
        self.assertIn("Legacy ruling stays.", content)


class TestAudioSubprocessDecoding(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="oude_audio_test_")
        self.root = Path(self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_normalise_audio_uses_utf8_replace_and_raises_on_failure(self):
        src = self.root / "input.mkv"
        dst = self.root / "output.wav"
        src.write_bytes(b"")

        with patch("transcribe_session.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("transcribe_session.subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            transcribe_session.normalise_audio(src, dst)
            self.assertEqual(mock_run.call_args.kwargs.get("encoding"), "utf-8")
            self.assertEqual(mock_run.call_args.kwargs.get("errors"), "replace")
            self.assertNotIn("text", mock_run.call_args.kwargs)

        with patch("transcribe_session.shutil.which", return_value="/usr/bin/ffmpeg"), \
             patch("transcribe_session.subprocess.run", return_value=MagicMock(returncode=1, stdout="", stderr="bad\ufffdbyte")):
            with self.assertRaisesRegex(RuntimeError, "ffmpeg conversion failed: bad\ufffdbyte"):
                transcribe_session.normalise_audio(src, dst)

    def test_transcribe_audio_uses_utf8_replace_and_raises_on_failure(self):
        model = self.root / "model.bin"
        wav = self.root / "audio.wav"
        out_base = self.root / "session_transcript"
        out_txt = out_base.with_suffix(".txt")
        model.write_bytes(b"")
        wav.write_bytes(b"")
        out_txt.write_text("Transcript.", encoding="utf-8")

        with patch("transcribe_session.shutil.which", return_value="/usr/bin/whisper-cli"), \
             patch("transcribe_session.subprocess.run", return_value=MagicMock(returncode=0, stdout="", stderr="")) as mock_run:
            res = transcribe_session.transcribe_audio(model, wav, out_base, ["Olmo"])
            self.assertEqual(res, out_txt)
            self.assertEqual(mock_run.call_args.kwargs.get("encoding"), "utf-8")
            self.assertEqual(mock_run.call_args.kwargs.get("errors"), "replace")
            self.assertNotIn("text", mock_run.call_args.kwargs)

        with patch("transcribe_session.shutil.which", return_value="/usr/bin/whisper-cli"), \
             patch("transcribe_session.subprocess.run", return_value=MagicMock(returncode=1, stdout="whisper\ufffderr", stderr="")):
            with self.assertRaisesRegex(RuntimeError, "whisper-cli failed: whisper\ufffderr"):
                transcribe_session.transcribe_audio(model, wav, out_base, [])


if __name__ == "__main__":
    unittest.main()
