import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import audit_coverage


class TestAuditCoverage(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "repo"
        self.repo_root.mkdir(parents=True)
        self.context_dir = self.repo_root / ".agents" / "context"
        self.context_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_resolve_drive_dir_relative_dot_independent_of_cwd(self):
        (self.context_dir / "tier1_sources.yml").write_text('drive_dir: "."\n')
        other_cwd = Path(self.temp_dir.name) / "other_cwd"
        other_cwd.mkdir()
        prev_cwd = Path.cwd()
        try:
            os.chdir(other_cwd)
            resolved = audit_coverage.resolve_drive_dir(self.repo_root)
        finally:
            os.chdir(prev_cwd)
        self.assertEqual(resolved, self.repo_root.resolve())

    def test_resolve_drive_dir_strips_inline_yaml_comments(self):
        for yml_line in (
            "drive_dir: . # inline comment\n",
            'drive_dir: "." # quoted inline comment\n',
            "drive_dir: './' # single-quoted comment\n",
        ):
            with self.subTest(yml_line=yml_line):
                (self.context_dir / "tier1_sources.yml").write_text(yml_line)
                self.assertEqual(audit_coverage.resolve_drive_dir(self.repo_root), self.repo_root.resolve())

    def test_resolve_drive_dir_falls_back_to_repo_root_when_missing_or_empty(self):
        self.assertEqual(
            audit_coverage.resolve_drive_dir(self.repo_root),
            self.repo_root.resolve(),
        )
        for yml_content in (
            'drive_dir: ""\n',
            "drive_dir:\ninclude_paths:\n  - campaigns\n",
            "drive_dir: # unset\ninclude_paths:\n  - campaigns\n",
        ):
            with self.subTest(yml_content=yml_content):
                (self.context_dir / "tier1_sources.yml").write_text(yml_content)
                self.assertEqual(
                    audit_coverage.resolve_drive_dir(self.repo_root),
                    self.repo_root.resolve(),
                )

    def test_resolve_drive_dir_raises_file_not_found_on_missing_or_file(self):
        with self.assertRaises(FileNotFoundError):
            audit_coverage.resolve_drive_dir(self.repo_root, "missing_dir")

        regular_file = self.repo_root / "file.txt"
        regular_file.write_text("hello\n")
        (self.context_dir / "tier1_sources.yml").write_text("drive_dir: file.txt\n")
        with self.assertRaises(FileNotFoundError):
            audit_coverage.resolve_drive_dir(self.repo_root)

    def test_audit_drive_sync_uses_gm_materials_digests_and_ignores_vault_dirs(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests" / "sector_module" / "factions"
        digests_dir.mkdir(parents=True)
        nested_digest = digests_dir / "harbour_guild.md"
        nested_digest.write_text("# Harbour Guild\n")

        # Ignored directories when drive_dir == repo_root
        for ignored in [
            "_gm-materials/session-summaries",
            "_site",
            ".jekyll-cache",
            "campaigns",
            "directory",
            "systems",
            "imgs",
            "node_modules",
            "bin",
            ".git",
        ]:
            d = self.repo_root / ignored
            d.mkdir(parents=True, exist_ok=True)
            (d / "ignored_doc.pdf").write_bytes(b"%PDF-1.4")

        # Unindexed PDF in sourcebooks/ and indexed PDF at root
        sourcebooks = self.repo_root / "sourcebooks"
        sourcebooks.mkdir()
        (sourcebooks / "Unindexed_Source.pdf").write_bytes(b"%PDF-1.4")
        (self.repo_root / "Sector_Module.pdf").write_bytes(b"%PDF-1.4")

        references_data = {
            "generated": "2026-01-01T00:00:00+00:00",
            "sources": [
                {
                    "slug": "sector_module/factions/harbour_guild",
                    "title": "Harbour Guild",
                    "category": "factions",
                    "tier": 3,
                    "source_pdf": "Sector_Module.pdf",
                    "digest_path": "_gm-materials/digests/sector_module/factions/harbour_guild.md",
                    "digest_exists": True,
                    "sections": [],
                }
            ],
        }
        (self.context_dir / "references.json").write_text(json.dumps(references_data))

        findings = audit_coverage.audit_drive_sync(self.repo_root, self.repo_root)
        unindexed_names = [item["name"] for item in findings["unindexed_files"]]
        self.assertIn("Unindexed_Source.pdf", unindexed_names)
        self.assertNotIn("ignored_doc.pdf", unindexed_names)
        self.assertEqual(findings["missing_digests"], [])

    def test_resolve_unindexed_file_action_pdf_suggests_oude_digest_scaffold(self):
        action = audit_coverage.resolve_unindexed_file_action(
            Path("book.pdf"), ".pdf", "sourcebooks/book.pdf", [], []
        )
        self.assertEqual(action, 'Run `oude digest --scaffold "sourcebooks/book.pdf"`')
        self.assertNotIn(".agents/scripts/generate_digests.py", action)

    def test_resolve_drive_dir_raises_yaml_error_on_malformed_yaml(self):
        (self.context_dir / "tier1_sources.yml").write_text("drive_dir: [unclosed\n")
        with self.assertRaises(yaml.YAMLError):
            audit_coverage.resolve_drive_dir(self.repo_root)

    def test_resolve_drive_dir_propagates_read_errors_loudly(self):
        # A directory in place of the YAML file forces an OSError on read.
        (self.context_dir / "tier1_sources.yml").mkdir()
        with self.assertRaises(OSError):
            audit_coverage.resolve_drive_dir(self.repo_root)

        # Invalid UTF-8 forces a UnicodeDecodeError on read.
        (self.context_dir / "tier1_sources.yml").rmdir()
        (self.context_dir / "tier1_sources.yml").write_bytes(b"drive_dir: \xff\xfe\x00bad")
        with self.assertRaises(UnicodeDecodeError):
            audit_coverage.resolve_drive_dir(self.repo_root)

    def test_resolve_drive_dir_treats_non_dict_yaml_as_unset(self):
        (self.context_dir / "tier1_sources.yml").write_text("- just\n- a\n- list\n")
        self.assertEqual(
            audit_coverage.resolve_drive_dir(self.repo_root),
            self.repo_root.resolve(),
        )

    def test_format_markdown_report_has_no_google_drive_phrasing(self):
        report = {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "repo_root": str(self.repo_root),
            "drive_audit": {
                "drive_accessible": True,
                "indexed_sources": [],
                "unindexed_files": [],
                "missing_digests": [],
            },
            "location": {"latest_episode": None, "raw_region": "Unknown"},
            "route_graph_available": False,
            "unillustrated_entries": [],
        }
        output = audit_coverage.format_markdown_report(report)
        self.assertNotIn("Google Drive", output)

    def test_format_markdown_report_summarises_unillustrated_counts(self):
        report = {
            "timestamp": "2026-01-01T00:00:00+00:00",
            "repo_root": str(self.repo_root),
            "drive_audit": {
                "drive_accessible": True,
                "indexed_sources": [],
                "unindexed_files": [],
                "missing_digests": [],
            },
            "location": {"latest_episode": None, "raw_region": "Unknown"},
            "route_graph_available": False,
            "unillustrated_entries": [
                {"path": "a.md", "title": "A", "type": "Note", "badge": "b.png", "status": "fallback_badge"},
                {"path": "b.md", "title": "B", "type": "Note", "badge": "none", "status": "missing_images"},
                {"path": "c.md", "title": "C", "type": "Note", "badge": "none", "status": "missing_images"},
            ],
        }
        output = audit_coverage.format_markdown_report(report)
        self.assertIn("- **Unillustrated Entries:** 3 (1 with fallback badge, 2 missing image)", output)


if __name__ == "__main__":
    unittest.main()
