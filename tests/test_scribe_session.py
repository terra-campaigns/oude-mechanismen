#!/usr/bin/env python3
"""
Unit tests for scripts/scribe_session.py and scripts/benchmark_models.py.
Verifies:
1. Campaign root location and discovery.
2. Markdown cleanliness enforcement (blank line following every heading).
3. Context ingestion (transcripts, glossaries, active decisions).
4. Prompt structure and de-personalisation directives for Pass 2A and Pass 2B.
5. Benchmark runner execution and Markdown report compilation.
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

import scribe_session
import benchmark_models


class TestScribeSession(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="scribe_test_")
        self.repo_root = (Path(self.test_dir) / "test_campaign").resolve()
        self.repo_root.mkdir()
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test Campaign\n", encoding="utf-8")

        # Fake files
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

    def test_markdown_cleanliness_enforcement(self):
        """Verify that enforce_markdown_cleanliness inserts an empty blank line after headings."""
        raw = "# Heading 1\nText directly below heading\n## Subheading\nLine 1\nLine 2\n"
        cleaned = scribe_session.enforce_markdown_cleanliness(raw)
        expected = "# Heading 1\n\nText directly below heading\n## Subheading\n\nLine 1\nLine 2\n"
        self.assertEqual(cleaned, expected)

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
        """Verify extract_tactical_facts sends appropriate prompt and de-personalisation instructions."""
        mock_query.return_value = "# Tactical Facts\n\n- Scene 1: Entered airlock."

        manifest = {
            "session_slug": "2026-11-03_ep001",
            "campaign": "test_campaign",
            "campaign_defaults": {"location_key": "region"},
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
        )

        self.assertIn("# Tactical Facts", output)
        mock_query.assert_called_once()
        prompt_arg = mock_query.call_args[0][2]
        self.assertIn("DE-PERSONALISATION MANDATE", prompt_arg)
        self.assertIn("Chronological sequence", prompt_arg)

    @patch("scribe_session.query_ollama_stream")
    def test_extract_sensory_textures(self, mock_query):
        """Verify extract_sensory_textures requests environmental and acoustic textures."""
        mock_query.return_value = "# Sensory Textures\n\n- Rancid copper odour."

        manifest = {
            "session_slug": "2026-11-03_ep001",
            "campaign": "test_campaign",
            "campaign_defaults": {"location_key": "region"},
        }
        context = {
            "transcript": "Flickering lights in corridor.",
            "glossary": "- Olmo: Scrapper",
            "decisions": "",
        }

        output = scribe_session.extract_sensory_textures(
            "http://localhost:11434",
            "mistral-nemo:12b",
            manifest,
            context,
        )

        self.assertIn("# Sensory Textures", output)
        mock_query.assert_called_once()
        prompt_arg = mock_query.call_args[0][2]
        self.assertIn("DE-PERSONALISATION MANDATE", prompt_arg)
        self.assertIn("Lighting & visual palette", prompt_arg)

    @patch("benchmark_models.query_ollama_timed")
    def test_benchmark_model_and_report(self, mock_timed):
        """Verify benchmark_model executes 2A & 2B and compile_benchmark_report writes markdown."""
        mock_timed.side_effect = [
            ("# Tactical output", 2.0, 100, 50.0),
            ("# Sensory output", 3.0, 150, 50.0),
        ]

        res = benchmark_models.benchmark_model(
            "http://localhost:11434",
            "qwen2.5:14b",
            "Sample transcript text",
            "- Olmo: Android",
        )

        self.assertEqual(res["model"], "qwen2.5:14b")
        self.assertEqual(res["total_time_sec"], 5.0)
        self.assertEqual(res["avg_tokens_per_sec"], 50.0)

        report_out = Path(self.test_dir) / "report.md"
        benchmark_models.compile_benchmark_report([res], str(self.transcript_file), report_out)

        self.assertTrue(report_out.exists())
        content = report_out.read_text(encoding="utf-8")
        self.assertIn("Local Model Benchmark Report", content)
        self.assertIn("`qwen2.5:14b`", content)


if __name__ == "__main__":
    unittest.main()
