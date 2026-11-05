#!/usr/bin/env python3
"""
Unit tests for scripts/scribe_session.py and scripts/benchmark_models.py.
Verifies:
1. Campaign root location and discovery.
2. Fence-aware Markdown cleanliness enforcement (blank line after headings, untouched fenced blocks).
3. Air-gap prompt boundary stripping across all delimiters and empty-output rejection.
4. Session metadata resolution (ignoring location_key schema names and stale previous chapter dates).
5. Optional input_file auto-discovery forwarding and .agents/venv Python resolution in run_acoustic_pipeline.
6. Context ingestion, keep_alive/stop propagation, and setting-agnostic British English prompts.
7. Benchmark runner weighted throughput calculation, error surfacing, and Markdown report compilation.
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import benchmark_models  # noqa: E402
import scribe_session  # noqa: E402


class TestScribeSession(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="scribe_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")

        self.transcript_file = self.repo_root / "sample_transcript.txt"
        self.transcript_file.write_text("Olmo and Ezekiel enter the airlock.\n", encoding="utf-8")

        self.glossary_file = self.repo_root / "sample_glossary.md"
        self.glossary_file.write_text("- Olmo: Android\n- Ezekiel: Spacer\n", encoding="utf-8")

        self.decisions_file = self.repo_root / ".agents" / "context" / "decisions.md"
        self.decisions_file.write_text("- Decision: Androids leak synthetic hydraulic fluid.\n", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_find_campaign_root(self):
        """Verify find_campaign_root resolves repository root from subdir or explicitly."""
        sub = self.repo_root / "nested" / "folder"
        sub.mkdir(parents=True)
        found = scribe_session.find_campaign_root(str(sub))
        self.assertEqual(found, self.repo_root)

    def test_markdown_cleanliness_enforcement_and_fences(self):
        """Verify blank lines are added after headings outside fences while fenced code comments remain intact."""
        raw = (
            "# Heading 1\n"
            "Text directly below heading\n"
            "```bash\n"
            "# Shell comment inside fence\n"
            "echo hello\n"
            "```\n"
            "## Subheading\n"
            "Line 1\n"
        )
        cleaned = scribe_session.enforce_markdown_cleanliness(raw)
        expected = (
            "# Heading 1\n\n"
            "Text directly below heading\n"
            "```bash\n"
            "# Shell comment inside fence\n"
            "echo hello\n"
            "```\n"
            "## Subheading\n\n"
            "Line 1\n"
        )
        self.assertEqual(cleaned, expected)

    def test_strip_prompt_echo_blocks_all_delimiters_and_rejects_empty(self):
        """Verify all prompt boundary markers are stripped to protect the Tier 0 air-gap and empty outputs fail."""
        for marker in (
            "\n---\n### Session Glossary:\nSecret",
            "\n---\n### Active Decisions (Tier 2 Canon):\nRuling",
            "\n---\n### Verbatim Session Transcript:\nPRIVATE PLAYER AUDIO",
            "\n### Verbatim Session Transcript:\nPRIVATE PLAYER AUDIO",
        ):
            cleaned = scribe_session.strip_prompt_echo(f"# Valid Notes\n\n- Beat 1.{marker}")
            self.assertEqual(cleaned, "# Valid Notes\n\n- Beat 1.")
            self.assertNotIn("PRIVATE", cleaned)

        with self.assertRaises(RuntimeError):
            scribe_session.strip_prompt_echo("   \n")

        with self.assertRaises(RuntimeError):
            scribe_session.strip_prompt_echo("### Verbatim Session Transcript:\nLeaked only")

    def test_resolve_session_metadata_ignores_location_key_and_stale_date(self):
        """Verify location_key ('location') is never rendered as a place name and slug date takes precedence."""
        manifest = {
            "session_slug": "2026-11-05_004",
            "campaign_defaults": {"location_key": "location"},
            "next_chapter_info": {
                "previous_date": "2226-05-11 03:00",
                "previous_region": None,
            },
        }
        recorded_date, last_locus = scribe_session.resolve_session_metadata(manifest)
        self.assertEqual(recorded_date, "2026-11-05")
        self.assertEqual(last_locus, "Unspecified Locus")
        self.assertNotEqual(last_locus, "location")

    @patch("scribe_session.subprocess.run")
    def test_run_acoustic_pipeline_optional_input_and_venv_precedence(self, mock_run):
        """Verify input_file=None omits positional arg, prefers engine transcribe_session.py, and uses .agents/venv."""
        fake_venv_py = self.repo_root / ".agents" / "venv" / "bin" / "python3"
        fake_venv_py.parent.mkdir(parents=True, exist_ok=True)
        fake_venv_py.write_text("#!/bin/sh\n", encoding="utf-8")

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({"status": "success", "session_slug": "2026-11-05_001"})
        mock_run.return_value = mock_proc

        manifest = scribe_session.run_acoustic_pipeline(
            self.repo_root,
            input_file=None,
            skip_transcribe=True,
            session_slug="2026-11-05_001",
        )
        self.assertEqual(manifest["status"], "success")
        cmd = mock_run.call_args[0][0]
        self.assertEqual(cmd[0], str(fake_venv_py))
        self.assertTrue(cmd[1].endswith("scripts/transcribe_session.py"))
        self.assertNotIn("None", cmd)
        self.assertIn("--skip-transcribe", cmd)
        self.assertIn("2026-11-05_001", cmd)

    def test_read_context_files(self):
        """Verify read_context_files reads transcript, glossary, and decisions."""
        manifest = {
            "transcript_path": str(self.transcript_file),
            "glossary_path": str(self.glossary_file),
        }
        ctx = scribe_session.read_context_files(self.repo_root, manifest)
        self.assertIn("Olmo and Ezekiel", ctx["transcript"])
        self.assertIn("Android", ctx["glossary"])
        self.assertIn("hydraulic fluid", ctx["decisions"])

    @patch("scribe_session.query_ollama_stream")
    def test_extract_tactical_facts(self, mock_query):
        """Verify extract_tactical_facts threads keep_alive, stop sequences, and de-personalisation mandate."""
        mock_query.return_value = "# Tactical Facts\n- Scene 1: Entered airlock.\n---\n### Verbatim Session Transcript:\nRaw"

        manifest = {
            "session_slug": "2026-11-03_ep001",
            "campaign": "test_campaign",
            "campaign_defaults": {"location_key": "region", "genre": "Science fantasy caravan"},
        }
        context = {
            "transcript": "Olmo and Ezekiel advance.",
            "glossary": "- Olmo: Scrapper",
            "decisions": "- Decision 1",
        }

        output = scribe_session.extract_tactical_facts(
            "http://localhost:11434",
            "qwen2.5:14b",
            manifest,
            context,
            keep_alive="0",
        )

        self.assertEqual(output, "# Tactical Facts\n\n- Scene 1: Entered airlock.\n")
        self.assertNotIn("Raw", output)
        mock_query.assert_called_once()
        prompt_arg = mock_query.call_args[0][2]
        kwargs = mock_query.call_args[1]
        self.assertEqual(kwargs["keep_alive"], "0")
        self.assertEqual(kwargs["stop"], scribe_session.OLLAMA_STOP_SEQUENCES)
        self.assertIn("DE-PERSONALISATION MANDATE", prompt_arg)
        self.assertIn("Science fantasy caravan", prompt_arg)

    @patch("scribe_session.query_ollama_stream")
    def test_extract_sensory_textures_is_setting_agnostic_and_british_english(self, mock_query):
        """Verify extract_sensory_textures contains zero hardcoded Hostile tropes and strictly British English."""
        mock_query.return_value = "# Sensory Textures\n- Rancid copper odour."

        manifest = {
            "session_slug": "2026-11-03_ep001",
            "campaign": "charged",
            "campaign_defaults": {"location_key": "region"},
        }
        context = {
            "transcript": "Dust blows across the steppe.",
            "glossary": "- Caravaner: Trader",
            "decisions": "",
        }

        output = scribe_session.extract_sensory_textures(
            "http://localhost:11434",
            "qwen2.5:14b",
            manifest,
            context,
            keep_alive="5m",
        )

        self.assertIn("# Sensory Textures\n\n- Rancid copper odour.", output)
        prompt_arg = mock_query.call_args[0][2]
        kwargs = mock_query.call_args[1]
        self.assertEqual(kwargs["keep_alive"], "5m")
        self.assertIn("utilising", prompt_arg)
        self.assertNotIn("utilizing", prompt_arg)
        for forbidden_trope in ("iron bar", "zero-G", "CRT phosphor", "hull strain", "bulkheads groaning"):
            self.assertNotIn(forbidden_trope, prompt_arg)

    @patch("benchmark_models.query_ollama_timed")
    def test_benchmark_model_and_report(self, mock_timed):
        """Verify benchmark_model computes weighted tok/s, shares production prompts, and flags failures."""
        # Pass 2A: 100 tokens at 50 tok/s (2.0s eval); Pass 2B: 300 tokens at 100 tok/s (3.0s eval)
        # Weighted throughput = (100 + 300) / (2.0 + 3.0) = 80.0 tok/s (NOT unweighted 75.0)
        mock_timed.side_effect = [
            ("# Tactical output\n\n- Beat 1", 2.0, 100, 50.0),
            ("# Sensory output\n\n- Wind", 3.0, 300, 100.0),
        ]

        res = benchmark_models.benchmark_model(
            "http://localhost:11434",
            "qwen2.5:14b",
            "Sample transcript text",
            "- Olmo: Android",
        )

        self.assertEqual(res["status"], "ok")
        self.assertEqual(res["total_tokens"], 400)
        self.assertAlmostEqual(res["avg_tokens_per_sec"], 80.0)

        # Verify error surfacing when a model fails
        mock_timed.side_effect = [RuntimeError("Connection refused"), ("# Sensory\n\n- Ok", 1.0, 20, 20.0)]
        err_res = benchmark_models.benchmark_model(
            "http://localhost:11434",
            "broken-model:latest",
            "Sample transcript text",
            "",
        )
        self.assertEqual(err_res["status"], "error")
        self.assertEqual(len(err_res["errors"]), 1)

        report_out = Path(self.test_dir) / "report.md"
        benchmark_models.compile_benchmark_report([res, err_res], str(self.transcript_file), report_out)

        self.assertTrue(report_out.exists())
        content = report_out.read_text(encoding="utf-8")
        self.assertIn("Local Model Benchmark Report", content)
        self.assertIn("| `qwen2.5:14b` | OK |", content)
        self.assertIn("| `broken-model:latest` | ERROR |", content)


if __name__ == "__main__":
    unittest.main()
