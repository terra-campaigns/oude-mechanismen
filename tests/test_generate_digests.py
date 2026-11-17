import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pypdf
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import generate_digests


class TestGenerateDigests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "repo"
        self.repo_root.mkdir(parents=True)
        self.context_dir = self.repo_root / ".agents" / "context"
        self.context_dir.mkdir(parents=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_find_drive_dir_relative_dot(self):
        (self.context_dir / "tier1_sources.yml").write_text('drive_dir: "."\n')
        other_cwd = Path(self.temp_dir.name) / "elsewhere"
        other_cwd.mkdir()
        prev_cwd = Path.cwd()
        try:
            os.chdir(other_cwd)
            resolved = generate_digests.find_drive_dir(self.repo_root)
        finally:
            os.chdir(prev_cwd)
        self.assertEqual(resolved, self.repo_root.resolve())

    def test_find_drive_dir_relative_subpath(self):
        sub = self.repo_root / "custom_sub"
        sub.mkdir()
        (self.context_dir / "tier1_sources.yml").write_text("drive_dir: custom_sub\n")
        resolved = generate_digests.find_drive_dir(self.repo_root)
        self.assertEqual(resolved, sub.resolve())

    def test_find_drive_dir_explicit_relative_path(self):
        sub = self.repo_root / "explicit_sub"
        sub.mkdir()
        resolved = generate_digests.find_drive_dir(self.repo_root, "explicit_sub")
        self.assertEqual(resolved, sub.resolve())

    def test_find_drive_dir_nonexistent_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            generate_digests.find_drive_dir(self.repo_root, "does_not_exist")

    def test_find_drive_dir_file_not_directory_raises_file_not_found(self):
        file_path = self.repo_root / "some_file.txt"
        file_path.write_text("not a dir\n")
        (self.context_dir / "tier1_sources.yml").write_text("drive_dir: some_file.txt\n")
        with self.assertRaises(FileNotFoundError):
            generate_digests.find_drive_dir(self.repo_root)

    def test_find_drive_dir_malformed_yaml_raises_yaml_error(self):
        (self.context_dir / "tier1_sources.yml").write_text("drive_dir: [unclosed\n")
        with self.assertRaises(yaml.YAMLError):
            generate_digests.find_drive_dir(self.repo_root)

    def test_find_drive_dir_fallback_to_repo_root_when_missing_or_empty(self):
        self.assertEqual(
            generate_digests.find_drive_dir(self.repo_root),
            self.repo_root.resolve(),
        )
        (self.context_dir / "tier1_sources.yml").write_text('drive_dir: ""\n')
        self.assertEqual(
            generate_digests.find_drive_dir(self.repo_root),
            self.repo_root.resolve(),
        )

    def test_compile_references_recursive_flat_and_nested_collision_free_slugs(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        (digests_dir / "sector_module" / "factions").mkdir(parents=True)
        (digests_dir / "other_module" / "factions").mkdir(parents=True)

        (digests_dir / "core_rules.md").write_text(
            "# Core Rules — Reference Digest\n\n> **Source PDF:** `Core_Rules.pdf`\n\n## Mechanics\n\n### Page 10\n\nText.\n"
        )
        (digests_dir / "sector_module" / "_index.md").write_text(
            "# Sector Module Overview\n\n## Overview\n\nIntro.\n"
        )
        (digests_dir / "sector_module" / "factions" / "harbour_guild.md").write_text(
            "# Harbour Guild\n\n## Assets\n\nShips.\n"
        )
        (digests_dir / "other_module" / "factions" / "harbour_guild.md").write_text(
            "# Other Harbour Guild\n\n## Rivals\n\nPirates.\n"
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)

        refs_path = self.context_dir / "references.json"
        self.assertTrue(refs_path.exists())
        refs = json.loads(refs_path.read_text())
        by_slug = {entry["slug"]: entry for entry in refs["sources"]}

        self.assertEqual(
            list(by_slug.keys()),
            [
                "core_rules",
                "other_module/factions/harbour_guild",
                "sector_module/_index",
                "sector_module/factions/harbour_guild",
            ],
        )

        core = by_slug["core_rules"]
        self.assertEqual(core["digest_path"], "_gm-materials/digests/core_rules.md")
        self.assertTrue(core["digest_exists"])
        self.assertEqual(core["source_pdf"], "Core_Rules.pdf")
        self.assertNotIn("entity_type", core)
        self.assertNotIn("pages", core)
        self.assertNotIn("tags", core)

        nested = by_slug["sector_module/factions/harbour_guild"]
        self.assertEqual(
            nested["digest_path"],
            "_gm-materials/digests/sector_module/factions/harbour_guild.md",
        )
        self.assertEqual(nested["title"], "Harbour Guild")

    def test_compile_references_frontmatter_metadata_and_malformed_fallback(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        (digests_dir / "book_a").mkdir(parents=True)

        alpha_md = digests_dir / "book_a" / "faction_alpha.md"
        alpha_content = (
            "---\n"
            "## Frontmatter Comment That Looks Like H2\n"
            "title: Frontmatter Alpha\n"
            "source_pdf: Book_A.pdf\n"
            "entity_type: faction\n"
            "pages: 14-18\n"
            "tags:\n"
            "  - syndicate\n"
            "  - trade\n"
            "---\n"
            "# Heading Alpha\n\n"
            "## Operations\n\n"
            "Details.\n"
        )
        alpha_md.write_text(alpha_content)
        (digests_dir / "book_a" / "broken_frontmatter.md").write_text(
            "---\n"
            "title: [unclosed\n"
            "---\n"
            "# Fallback Heading\n\n"
            "> **Source PDF:** `Fallback.pdf`\n\n"
            "## Chapter 1\n\n"
            "Body.\n"
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.context_dir / "references.json").read_text())
        by_slug = {entry["slug"]: entry for entry in refs["sources"]}

        alpha = by_slug["book_a/faction_alpha"]
        self.assertEqual(alpha["title"], "Frontmatter Alpha")
        self.assertEqual(alpha["source_pdf"], "Book_A.pdf")
        self.assertEqual(alpha["entity_type"], "faction")
        self.assertEqual(alpha["pages"], "14-18")
        self.assertEqual(alpha["tags"], ["syndicate", "trade"])
        self.assertEqual(alpha["sections"], [{"level": 2, "heading": "Operations", "line": 13}])

        # Ensure --clean-headings ignores YAML frontmatter comments while keeping body clean.
        generate_digests.compile_references(self.repo_root, self.repo_root, clean_headings=True)
        self.assertEqual(alpha_md.read_text(), alpha_content)

        broken = by_slug["book_a/broken_frontmatter"]
        self.assertEqual(broken["title"], "Fallback Heading")
        self.assertEqual(broken["source_pdf"], "Fallback.pdf")
        self.assertNotIn("entity_type", broken)

    def test_compile_references_empty_frontmatter_source_pdf_falls_back_to_body(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        digests_dir.mkdir(parents=True)
        supp_pdf = self.repo_root / "supplements" / "Local_Sub.pdf"
        supp_pdf.parent.mkdir(parents=True)
        supp_pdf.write_bytes(b"%PDF-1.4")

        (digests_dir / "empty_fm_src.md").write_text(
            "---\n"
            "title: Local Sub\n"
            'source_pdf: ""\n'
            "---\n"
            "# Local Sub — Reference Digest\n\n"
            "> **Source PDF:** `supplements/Local_Sub.pdf`\n\n"
            "## Contents\n\n"
            "Intro.\n"
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.context_dir / "references.json").read_text())
        entry = refs["sources"][0]
        self.assertEqual(entry["source_pdf"], "supplements/Local_Sub.pdf")
        self.assertEqual(entry["category"], "supplement")

    def test_compile_references_idempotent_generated_timestamp(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        digests_dir.mkdir(parents=True)
        (digests_dir / "sample.md").write_text("# Sample\n\n## Section\n\nContent.\n")

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs_path = self.context_dir / "references.json"
        first = json.loads(refs_path.read_text())
        fixed_ts = "2026-01-01T00:00:00+00:00"
        first["generated"] = fixed_ts
        refs_path.write_text(json.dumps(first, indent=2) + "\n")

        generate_digests.compile_references(self.repo_root, self.repo_root)
        second = json.loads(refs_path.read_text())
        self.assertEqual(second["generated"], fixed_ts)

    def test_find_drive_dir_propagates_os_error_when_config_is_directory(self):
        (self.context_dir / "tier1_sources.yml").mkdir()
        with self.assertRaises(OSError):
            generate_digests.find_drive_dir(self.repo_root)

    def test_find_drive_dir_propagates_unicode_decode_error_on_invalid_utf8(self):
        (self.context_dir / "tier1_sources.yml").write_bytes(b"drive_dir: \xff\xfe\x80 invalid utf8\n")
        with self.assertRaises(UnicodeDecodeError):
            generate_digests.find_drive_dir(self.repo_root)

    def test_compile_references_thematic_break_not_treated_as_frontmatter(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        digests_dir.mkdir(parents=True)
        content = "---\n\n# Thematic Title\n\nIntro.\n\n---\n\n## Section\nText.\n"
        md_file = digests_dir / "thematic.md"
        md_file.write_text(content)

        for clean in (False, True):
            generate_digests.compile_references(self.repo_root, self.repo_root, clean_headings=clean)
            refs = json.loads((self.context_dir / "references.json").read_text())
            entry = refs["sources"][0]
            self.assertEqual(entry["title"], "Thematic Title")
            self.assertEqual(entry["sections"], [{"level": 2, "heading": "Section", "line": 9}])
            self.assertIn("# Thematic Title", md_file.read_text())

    def test_compile_references_non_mapping_yaml_frontmatter_preserved_as_body(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        digests_dir.mkdir(parents=True)
        content = "---\n- item\n---\n\n# List Doc\n\n## Section\nText.\n"
        md_file = digests_dir / "list_doc.md"
        md_file.write_text(content)

        for clean in (False, True):
            generate_digests.compile_references(self.repo_root, self.repo_root, clean_headings=clean)
            refs = json.loads((self.context_dir / "references.json").read_text())
            entry = refs["sources"][0]
            self.assertEqual(entry["title"], "List Doc")
            self.assertEqual(entry["sections"], [{"level": 2, "heading": "Section", "line": 7}])
            self.assertIn("# List Doc", md_file.read_text())

    def test_compile_references_normalises_absolute_source_pdf_paths(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        digests_dir.mkdir(parents=True)
        inside_pdf = self.repo_root / "books" / "Inside.pdf"
        inside_pdf.parent.mkdir(parents=True)
        inside_pdf.write_bytes(b"%PDF-1.4")

        (digests_dir / "abs_inside.md").write_text(
            "---\n"
            "title: Abs Inside\n"
            f"source_pdf: {inside_pdf}\n"
            "---\n"
            "# Abs Inside\n\n## S\nText.\n"
        )
        (digests_dir / "abs_outside.md").write_text(
            "---\n"
            "title: Abs Outside\n"
            "source_pdf: /host/specific/path/Outside.pdf\n"
            "---\n"
            "# Abs Outside\n\n## S\nText.\n"
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.context_dir / "references.json").read_text())
        by_slug = {entry["slug"]: entry for entry in refs["sources"]}
        self.assertEqual(by_slug["abs_inside"]["source_pdf"], "books/Inside.pdf")
        self.assertEqual(by_slug["abs_outside"]["source_pdf"], "Outside.pdf")

    def _make_two_page_pdf(self, path: Path) -> None:
        writer = pypdf.PdfWriter()
        writer.add_blank_page(width=612, height=792)
        writer.add_blank_page(width=612, height=792)
        with open(path, "wb") as fh:
            writer.write(fh)

    def test_scaffold_digest_external_pdf_records_portable_name(self):
        external_dir = Path(self.temp_dir.name) / "external"
        external_dir.mkdir()
        pdf_path = external_dir / "External_Book.pdf"
        self._make_two_page_pdf(pdf_path)

        out = generate_digests.scaffold_digest(self.repo_root, self.repo_root, str(pdf_path))
        text = out.read_text()
        self.assertIn("External_Book.pdf", text)
        self.assertNotIn(str(external_dir), text)
        self.assertNotIn(str(Path(self.temp_dir.name)), text)

    def test_scaffold_digest_pdf_in_legacy_rpg_root_records_name_not_absolute(self):
        drive_dir = self.repo_root / "drive"
        drive_dir.mkdir()
        rpg_root = drive_dir.parents[1]
        pdf_path = rpg_root / "Legacy_Root.pdf"
        self._make_two_page_pdf(pdf_path)

        out = generate_digests.scaffold_digest(self.repo_root, drive_dir, str(pdf_path))
        text = out.read_text()
        self.assertIn("Legacy_Root.pdf", text)
        self.assertNotIn(str(rpg_root), text)

    def test_scaffold_digest_source_pdf_override(self):
        external_dir = Path(self.temp_dir.name) / "external"
        external_dir.mkdir()
        pdf_path = external_dir / "External_Book.pdf"
        self._make_two_page_pdf(pdf_path)

        out = generate_digests.scaffold_digest(
            self.repo_root, self.repo_root, str(pdf_path), source_pdf="canonical/portable.pdf"
        )
        self.assertIn("canonical/portable.pdf", out.read_text())

    def test_scaffold_digest_missing_explicit_pdf_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            generate_digests.scaffold_digest(self.repo_root, self.repo_root, "does_not_exist.pdf")

    def test_find_pdf_removed(self):
        self.assertFalse(hasattr(generate_digests, "find_pdf"))

    def test_scaffold_digest_writes_to_gm_materials_digests(self):
        pdf_path = self.repo_root / "Test_Book.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 dummy")

        fake_reader = unittest.mock.MagicMock()
        fake_reader.pages = [None] * 12
        fake_reader.metadata = None
        with patch.object(generate_digests.pypdf, "PdfReader", return_value=fake_reader), \
             patch.object(generate_digests, "extract_pdf_outline", return_value=[("Intro", 1, 12)]):
            generate_digests.scaffold_digest(self.repo_root, self.repo_root, "Test_Book.pdf")

        expected_out = self.repo_root / "_gm-materials" / "digests" / "test_book.md"
        self.assertTrue(expected_out.exists())
        self.assertIn("Test_Book.pdf", expected_out.read_text())


if __name__ == "__main__":
    unittest.main()
