import contextlib
import io
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

    def test_proximity_gaps_follow_route_graph_connections(self):
        """Regression test for #29: route_graph.json drives audit proximity analysis."""
        graph = {
            "stations": {"A": {"num": 1}, "B": {"num": 2}, "C": {"num": 3}},
            "connections": [
                {"origin": "A", "destination": "B", "weeks": 2, "direction": "East", "terrain": "road"},
                {"origin": "B", "destination": "C", "weeks": 1, "direction": "North", "terrain": "trail"},
            ],
        }
        gaps = audit_coverage.calculate_proximity_gaps("A", graph, {}, max_hops=2)
        self.assertEqual([g["station"] for g in gaps], ["B", "C"])
        self.assertEqual(gaps[0]["hops"], 1)
        self.assertEqual(gaps[1]["total_weeks"], 3)
        # Without the graph's connections nothing is reachable.
        empty = audit_coverage.calculate_proximity_gaps("A", {"stations": {"A": {}}}, {}, max_hops=2)
        self.assertEqual(empty, [])

    def _write_note(self, rel_path: str, front_matter: str, body: str = "Body.\n") -> Path:
        p = self.repo_root / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"---\n{front_matter.strip()}\n---\n\n{body}", encoding="utf-8")
        return p

    def test_audit_unillustrated_entries_honours_exclude_paths_and_prefix_boundaries(self):
        # Issue #110: YAML parsing of tier1_sources.yml + exclude_paths filtering.
        (self.context_dir / "tier1_sources.yml").write_text(
            "drive_dir: .\n"
            "include_paths:\n"
            "  - campaigns # inline comment\n"
            "  - directory/\n"
            "exclude_paths:\n"
            "  - campaigns/Anthology/\n"
            "  - campaigns/FailedExports\n"
            "  - directory/FoldedBelow\n"
            "  - directory/draft.md\n",
            encoding="utf-8",
        )
        self._write_note("campaigns/Anthology/old.md", "title: Old Story\ntype: session")
        self._write_note("campaigns/FailedExports/broken.md", "title: Broken\ntype: session")
        self._write_note("directory/FoldedBelow/entity.md", "title: Folded\ntype: location")
        self._write_note("directory/draft.md", "title: Draft\ntype: location")
        # Sibling prefix directory must NOT be excluded by prefix-boundary check
        self._write_note("campaigns/AnthologyExtra/ep1.md", "title: Ep 1\ntype: session")
        self._write_note("directory/Active/inn.md", "title: The Inn\ntype: location")

        entries = audit_coverage.audit_unillustrated_entries(self.repo_root)
        paths = [e["path"] for e in entries]
        self.assertEqual(paths, ["campaigns/AnthologyExtra/ep1.md", "directory/Active/inn.md"])

    def test_audit_unillustrated_entries_yaml_image_and_images_variants(self):
        (self.context_dir / "tier1_sources.yml").write_text(
            "include_paths:\n  - directory\nexclude_paths: []\n", encoding="utf-8"
        )
        # Illustrated variants (all should be excluded from unillustrated list)
        self._write_note("directory/scalar_image.md", 'title: S1\nimage: "/imgs/s1.png"')
        self._write_note("directory/inline_images.md", 'title: S2\nimages: ["/imgs/s2.png"]')
        self._write_note("directory/scalar_images.md", "title: S3\nimages: /imgs/s3.png")
        self._write_note("directory/block_images.md", "title: S4\nimages:\n  - /imgs/s4.png")
        self._write_note(
            "directory/custom_plus_badge.md",
            "title: S5\nimages:\n  - /imgs/badges/people.png\n  - /imgs/portrait.png",
        )
        # Unillustrated variants
        self._write_note("directory/empty_list.md", "title: E1\nimages: []")
        self._write_note("directory/null_images.md", "title: E2\nimages: null")
        self._write_note("directory/omitted.md", "title: E3")

        entries = audit_coverage.audit_unillustrated_entries(self.repo_root)
        self.assertEqual(
            [e["path"] for e in entries],
            ["directory/empty_list.md", "directory/null_images.md", "directory/omitted.md"],
        )

    def test_audit_unillustrated_entries_fallback_badge_classification(self):
        (self.context_dir / "tier1_sources.yml").write_text(
            "include_paths:\n  - directory\n  - campaigns\nexclude_paths: []\n", encoding="utf-8"
        )
        # Explicit badge in image: or images:
        self._write_note(
            "directory/explicit_badge.md",
            "title: Explicit\ntype: session\nimage: /imgs/badges/custom.png",
        )
        # Dynamic fallback badge types (matching connected_to.html) when images are empty/omitted
        for entity_type in ("people", "faction", "location", "creature"):
            self._write_note(
                f"directory/{entity_type}_note.md",
                f"title: {entity_type.title()} Note\ntype: {entity_type}",
            )
        # Types without dynamic fallback badges -> missing_images
        self._write_note("campaigns/ep1.md", "title: Episode 1\ntype: session")
        self._write_note("directory/untyped.md", "title: Untyped")

        by_path = {e["path"]: e for e in audit_coverage.audit_unillustrated_entries(self.repo_root)}
        self.assertEqual(by_path["directory/explicit_badge.md"]["status"], "fallback_badge")
        self.assertEqual(by_path["directory/explicit_badge.md"]["badge"], "custom")
        for entity_type in ("people", "faction", "location", "creature"):
            rec = by_path[f"directory/{entity_type}_note.md"]
            self.assertEqual(rec["status"], "fallback_badge")
            self.assertEqual(rec["badge"], entity_type)
        self.assertEqual(by_path["campaigns/ep1.md"]["status"], "missing_images")
        self.assertEqual(by_path["campaigns/ep1.md"]["badge"], "none")
        self.assertEqual(by_path["directory/untyped.md"]["status"], "missing_images")
        self.assertEqual(by_path["directory/untyped.md"]["badge"], "none")

    def test_audit_unillustrated_entries_handles_malformed_yaml_gracefully(self):
        (self.context_dir / "tier1_sources.yml").write_text("include_paths: [broken\n", encoding="utf-8")
        self._write_note("directory/bad_fm.md", "title: [unclosed\n")
        self._write_note("directory/good.md", "title: Good\ntype: location")

        stderr_buf = io.StringIO()
        with contextlib.redirect_stderr(stderr_buf):
            entries = audit_coverage.audit_unillustrated_entries(self.repo_root)
        self.assertEqual([e["path"] for e in entries], ["directory/good.md"])
        self.assertIn("Warning: Failed to parse", stderr_buf.getvalue())
        self.assertIn("directory/bad_fm.md", stderr_buf.getvalue())

    def test_audit_unillustrated_entries_skips_engine_dirs_on_dot_include_and_nested_yaml(self):
        (self.context_dir / "tier1_sources.yml").write_text(
            "include_paths:\n  - .\nexclude_paths: []\n", encoding="utf-8"
        )
        for skipped in ("_gm-materials/digests/secret.md", "_site/index.md", "vendor/readme.md", "_plugins/note.md"):
            self._write_note(skipped, "title: Ignored\ntype: location")
        # Nested dict/list elements inside images: must not crash or count as valid image strings
        self._write_note("directory/nested_images.md", "title: Nested\nimages:\n  - [nested]\n  - {bad: true}")
        self._write_note("directory/normal.md", "title: Normal\ntype: location")

        paths = [e["path"] for e in audit_coverage.audit_unillustrated_entries(self.repo_root)]
        self.assertEqual(paths, ["directory/nested_images.md", "directory/normal.md"])


if __name__ == "__main__":
    unittest.main()
