import io
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

    def test_compile_references_excludes_flat_stub_colliding_with_nested_wiki(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests"
        nested = digests_dir / "hostile_synthetics"
        nested.mkdir(parents=True)
        flat = digests_dir / "hostile_synthetics.md"
        flat.write_text(
            "# Hostile Synthetics — Reference Digest\n\n## Placeholder\n\nStale stub.\n"
        )
        (nested / "_index.md").write_text("# Hostile Synthetics Overview\n\n## Overview\n\nIntro.\n")
        (nested / "note.md").write_text("# Note\n\n## Section\n\nText.\n")
        # Nested-level collision: a/b.md alongside a/b/
        deep = digests_dir / "a"
        deep.mkdir(parents=True)
        nested_dir_level = deep / "b.md"
        nested_dir_level.write_text("# Stale\n")
        deep_nested = deep / "b"
        deep_nested.mkdir(parents=True)
        (deep_nested / "_index.md").write_text("# B\n")

        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            generate_digests.compile_references(self.repo_root, self.repo_root)

        output = buf.getvalue()
        self.assertIn("[WARN]", output)
        self.assertIn(str(flat), output)
        self.assertIn(str(nested), output)
        self.assertIn(str(nested_dir_level), output)
        self.assertIn("references.json", output)

        refs = json.loads((self.context_dir / "references.json").read_text())
        by_slug = {entry["slug"]: entry for entry in refs["sources"]}
        # Colliding flat stubs are excluded; the nested wiki supersedes them.
        self.assertEqual(
            sorted(by_slug.keys()),
            ["a/b/_index", "hostile_synthetics/_index", "hostile_synthetics/note"],
        )

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




def _make_pdf(path, pages_text, outline=None):
    """Build a synthetic PDF with extractable text per page (zero binary fixtures committed)."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    font = DictionaryObject()
    font[NameObject("/Type")] = NameObject("/Font")
    font[NameObject("/Subtype")] = NameObject("/Type1")
    font[NameObject("/BaseFont")] = NameObject("/Helvetica")
    font_ref = writer._add_object(font)
    for text in pages_text:
        page = writer.add_blank_page(width=612, height=792)
        if text:
            stream = DecodedStreamObject()
            escaped = text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")
            ops = ["BT", "/F1 12 Tf", "72 720 Td"]
            for line in escaped.split("\n"):
                ops.append(f"({line}) Tj")
                ops.append("0 -14 Td")
            ops.append("ET")
            stream.set_data(" ".join(ops).encode("latin-1", "replace"))
            page[NameObject("/Contents")] = writer._add_object(stream)
            fonts = DictionaryObject()
            fonts[NameObject("/F1")] = font_ref
            resources = DictionaryObject()
            resources[NameObject("/Font")] = fonts
            page[NameObject("/Resources")] = writer._add_object(resources)
    if outline:
        for title, page_index in outline:
            writer.add_outline_item(title, page_index)
    with open(path, "wb") as fh:
        writer.write(fh)


class TestExtractAndValidate(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.repo_root = Path(self.temp_dir.name) / "repo"
        self.repo_root.mkdir(parents=True)
        (self.repo_root / ".agents" / "context").mkdir(parents=True)
        (self.repo_root / "_config.yml").write_text("title: Test\n", encoding="utf-8")
        self.dense = "Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor " * 3

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_extract_text_mode_outline_windows(self):
        pdf = Path(self.temp_dir.name) / "book.pdf"
        _make_pdf(pdf, [self.dense, self.dense, self.dense], outline=[("Chapter 1", 0), ("Chapter 2", 2)])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["total_pages"], 3)
        self.assertEqual(manifest["format_requested"], "text")
        self.assertEqual([(s["title"], s["start_page"], s["end_page"], s["format"]) for s in manifest["slices"]],
                         [("Chapter 1", 1, 2, "text"), ("Chapter 2", 3, 3, "text")])
        first = (out_dir / manifest["slices"][0]["path"]).read_text(encoding="utf-8")
        self.assertTrue(first.startswith("--- Page 1 ---"))
        self.assertIn("--- Page 2 ---", first)

    def test_extract_chunking_respects_max_bytes(self):
        pdf = Path(self.temp_dir.name) / "big.pdf"
        _make_pdf(pdf, ["word " * 20] * 25)
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text", max_bytes=300, chunk_pages=4)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreater(len(manifest["slices"]), 3)
        for s in manifest["slices"]:
            self.assertLessEqual(s["byte_size"], 300)
            self.assertTrue((out_dir / s["path"]).exists())

    def test_extract_single_page_line_split(self):
        pdf = Path(self.temp_dir.name) / "one.pdf"
        _make_pdf(pdf, ["x" * 5000])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text", max_bytes=1000)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertGreater(len(manifest["slices"]), 1)
        reconstructed = []
        for s in manifest["slices"]:
            self.assertLessEqual(s["byte_size"], 1000)
            content = (out_dir / s["path"]).read_text(encoding="utf-8")
            self.assertIn("--- Page 1 (part", content[:40])
            reconstructed.append(content.split("\n", 1)[1])
        self.assertEqual("".join(reconstructed).count("x"), 5000)
        with self.assertRaises(ValueError):
            generate_digests._split_single_page("abc", 1, 10)

    def test_extract_auto_fallback_to_pdf_on_sparse_page(self):
        pdf = Path(self.temp_dir.name) / "sparse.pdf"
        _make_pdf(pdf, [self.dense, "x"], outline=[("Dense", 0), ("Sparse", 1)])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="auto", min_chars_per_page=80)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["slices"][0]["format"], "text")
        self.assertIsNone(manifest["slices"][0]["auto_fallback_reason"])
        self.assertEqual(manifest["slices"][1]["format"], "pdf")
        self.assertIn("low text density", manifest["slices"][1]["auto_fallback_reason"])
        self.assertTrue((out_dir / manifest["slices"][1]["path"]).read_bytes().startswith(b"%PDF"))

    def test_extract_pdf_mode_splits_by_pdf_slice_pages(self):
        pdf = Path(self.temp_dir.name) / "twelve.pdf"
        _make_pdf(pdf, ["text page"] * 12)
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf", pdf_slice_pages=5)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual([(s["start_page"], s["end_page"], s["format"]) for s in manifest["slices"]],
                         [(1, 5, "pdf"), (6, 10, "pdf"), (11, 12, "pdf")])

    def test_extract_missing_pdf_raises_file_not_found(self):
        with self.assertRaises(FileNotFoundError):
            generate_digests.extract_pdf("nope.pdf", self.repo_root, out_dir=str(Path(self.temp_dir.name) / "out"))

    def test_extract_pages_filter_merges_into_existing_manifest(self):
        pdf = Path(self.temp_dir.name) / "four.pdf"
        _make_pdf(pdf, [self.dense, "x", self.dense, self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        m1 = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="auto", min_chars_per_page=80)
        first = json.loads(m1.read_text(encoding="utf-8"))
        covered1 = set()
        for s in first["slices"]:
            covered1.update(range(s["start_page"], s["end_page"] + 1))
        self.assertEqual(covered1, {1, 2, 3, 4})
        # Re-extract pages 2-3 as pdf into the same out_dir: manifest must merge, not wipe.
        m2 = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf", page_spec="2-3")
        merged = json.loads(m2.read_text(encoding="utf-8"))
        by_page = {}
        for s in merged["slices"]:
            for p in range(s["start_page"], s["end_page"] + 1):
                by_page[p] = s["format"]
        self.assertEqual(by_page, {1: "text", 2: "pdf", 3: "pdf", 4: "text"})
        self.assertEqual([s["index"] for s in merged["slices"]], list(range(1, len(merged["slices"]) + 1)))
        # Fresh full run still clears stale files.
        m3 = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text")
        fresh = json.loads(m3.read_text(encoding="utf-8"))
        self.assertTrue(all(s["format"] == "text" for s in fresh["slices"]))

    def test_extract_auto_fallback_splits_sparse_page_inside_text_window(self):
        pdf = Path(self.temp_dir.name) / "mixed.pdf"
        _make_pdf(pdf, [self.dense, "x", self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="auto", min_chars_per_page=80)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_page = {}
        for s in manifest["slices"]:
            for p in range(s["start_page"], s["end_page"] + 1):
                by_page[p] = s
        self.assertEqual(set(by_page), {1, 2, 3})
        self.assertEqual(by_page[1]["format"], "text")
        self.assertEqual(by_page[3]["format"], "text")
        self.assertEqual(by_page[2]["format"], "pdf")
        self.assertIn("page 2", by_page[2]["auto_fallback_reason"])
        self.assertIn("low text density", by_page[2]["auto_fallback_reason"])

    def test_extract_covers_pages_before_first_outline_item(self):
        pdf = Path(self.temp_dir.name) / "late_outline.pdf"
        _make_pdf(pdf, [self.dense, self.dense, self.dense], outline=[("Chapter 1", 2)])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        spans = sorted((s["start_page"], s["end_page"]) for s in manifest["slices"])
        covered = set()
        for a, b in spans:
            covered.update(range(a, b + 1))
        self.assertEqual(covered, {1, 2, 3})
        self.assertEqual(spans[0], (1, 2))
        self.assertEqual(manifest["slices"][0]["title"], "Front Matter")

    def _write_valid_note(self, digest_dir, name="_index.md", folder="", with_link=False):
        target_dir = digest_dir / folder if folder else digest_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        note = target_dir / name
        body = "See [Guild](factions/guild.md).\n" if with_link else "Intro.\n"
        note.write_text(
            "---\nsource: book\ntier: 3\nentity_type: index\ntitle: Book\n---\n\n# Book\n\n" + body,
            encoding="utf-8",
        )
        return note

    def test_validate_pass(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        self._write_valid_note(digest_dir, with_link=True)
        (digest_dir / "factions").mkdir()
        (digest_dir / "factions" / "guild.md").write_text(
            "---\nsource: book\ntier: 3\nentity_type: faction\ntitle: Guild\n---\n\n# Guild\n\nText.\n",
            encoding="utf-8",
        )
        with patch("sys.stdout", new=io.StringIO()):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 0)

    def test_validate_failures_report_file_line(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        note = self._write_valid_note(digest_dir, name="guild.md", folder="factions")
        note.write_text(
            "---\nsource: book\ntier: 2\nentity_type: faction\ntitle: Guild\n---\n\n# Guild\nNo blank line.\n\n[bad](missing.md)\n[esc](../../../../../../etc/hostname)\n",
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 1)
        out = buf.getvalue()
        self.assertIn("guild.md:1: frontmatter 'tier' must equal 3", out)
        self.assertIn("guild.md:8: heading not followed by a blank line", out)
        self.assertIn("guild.md:11: broken relative link 'missing.md'", out)
        self.assertIn("guild.md:12:", out)
        self.assertIn("escapes the digest directory and repository root", out)

    def test_validate_manifest_fallback_telemetry(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        self._write_valid_note(digest_dir)
        manifest = Path(self.temp_dir.name) / "manifest.json"
        manifest.write_text(json.dumps({"slices": [{"auto_fallback_reason": "low text density: 3 chars"}, {"auto_fallback_reason": None}]}), encoding="utf-8")
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir, manifest=str(manifest))
        self.assertEqual(rc, 0)
        self.assertIn("auto-fallback slice counts", buf.getvalue())

    def test_validate_staged_dir_outside_repo_root(self):
        # Simulates SKILL.md's <out-dir>/staged/<source> validation, which lives outside the repo.
        staged = Path(self.temp_dir.name) / "extract" / "staged" / "mybook"
        (staged / "factions").mkdir(parents=True)
        (staged / "_index.md").write_text(
            "---\nsource: mybook\ntier: 3\nentity_type: index\ntitle: Mybook\n---\n\n# Mybook\n\nSee [Guild](factions/guild.md).\n",
            encoding="utf-8",
        )
        (staged / "factions" / "guild.md").write_text(
            "---\nsource: mybook\ntier: 3\nentity_type: faction\ntitle: Guild\n---\n\n# Guild\n\nBack to [Index](../_index.md).\n",
            encoding="utf-8",
        )
        with patch("sys.stdout", new=io.StringIO()):
            rc = generate_digests.validate_digests(self.repo_root, staged)
        self.assertEqual(rc, 0)
        # A link escaping the staged dir (and the repo) must still fail.
        (staged / "_index.md").write_text(
            "---\nsource: mybook\ntier: 3\nentity_type: index\ntitle: Mybook\n---\n\n# Mybook\n\n[esc](../../../../etc/hostname)\n",
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, staged)
        self.assertEqual(rc, 1)
        self.assertIn("escapes the digest directory and repository root", buf.getvalue())

    def test_validate_ignores_links_in_fenced_code_blocks(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        note = self._write_valid_note(digest_dir)
        note.write_text(
            "---\nsource: book\ntier: 3\nentity_type: index\ntitle: Book\n---\n\n# Book\n\nExample:\n\n```\n[bad](missing.md)\n```\n",
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 0)
        self.assertNotIn("broken relative link", buf.getvalue())

    def test_extract_sequential_pages_overrides_are_preserved(self):
        pdf = Path(self.temp_dir.name) / "four.pdf"
        _make_pdf(pdf, [self.dense, self.dense, self.dense, self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="text")
        m = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf", page_spec="2-3")
        by_page = {}
        for s in json.loads(m.read_text(encoding="utf-8"))["slices"]:
            for p in range(s["start_page"], s["end_page"] + 1):
                by_page[p] = s["format"]
        self.assertEqual(by_page, {1: "text", 2: "pdf", 3: "pdf", 4: "text"})
        # A second, disjoint --pages run must not revert the first override.
        m2 = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf", page_spec="4")
        by_page2 = {}
        for s in json.loads(m2.read_text(encoding="utf-8"))["slices"]:
            for p in range(s["start_page"], s["end_page"] + 1):
                by_page2[p] = s["format"]
        self.assertEqual(by_page2, {1: "text", 2: "pdf", 3: "pdf", 4: "pdf"})

    def test_validate_rejects_empty_and_comment_frontmatter(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        digest_dir.mkdir(parents=True)
        for idx, header in enumerate(["---\n\n---\n", "---\n# only a comment\n---\n"], start=1):
            (digest_dir / f"n{idx}.md").write_text(f"{header}\n# Empty\n\nBody.\n", encoding="utf-8")
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 1)
        self.assertIn("frontmatter must be a YAML mapping, got NoneType", buf.getvalue())

    def test_validate_empty_digest_dir_fails(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "empty"
        digest_dir.mkdir(parents=True)
        with patch("sys.stdout", new=io.StringIO()):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 1)

    def test_validate_handles_link_titles_and_url_encoded_spaces(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        (digest_dir / "factions").mkdir(parents=True)
        (digest_dir / "factions" / "guild hall.md").write_text(
            "---\nsource: book\ntier: 3\nentity_type: faction\ntitle: Guild Hall\n---\n\n# Guild Hall\n\nText.\n",
            encoding="utf-8",
        )
        (digest_dir / "_index.md").write_text(
            '---\nsource: book\ntier: 3\nentity_type: index\ntitle: Book\n---\n\n# Book\n\nSee [Guild](factions/guild%20hall.md "Guild Hall").\n',
            encoding="utf-8",
        )
        with patch("sys.stdout", new=io.StringIO()):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir)
        self.assertEqual(rc, 0)

    def test_validate_manifest_telemetry_groups_reasons(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        self._write_valid_note(digest_dir)
        manifest = Path(self.temp_dir.name) / "manifest.json"
        manifest.write_text(
            json.dumps({
                "slices": [
                    {"auto_fallback_reason": "low text density: page 1 has 3 chars below 80"},
                    {"auto_fallback_reason": "low text density: page 4 has 12 chars below 80"},
                    {"auto_fallback_reason": None},
                ]
            }),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir, manifest=str(manifest))
        self.assertEqual(rc, 0)
        self.assertIn('{"low text density": 2}', buf.getvalue())

    def test_extract_pages_auto_format_checks_density_and_defaults_rest_to_auto(self):
        pdf = Path(self.temp_dir.name) / "mixed_pages.pdf"
        _make_pdf(pdf, [self.dense, "x", self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        # Fresh --pages run with --format auto must check density on page 2 and default rest to auto.
        m = generate_digests.extract_pdf(
            str(pdf), self.repo_root, out_dir=str(out_dir), format="auto", page_spec="2", min_chars_per_page=80
        )
        manifest = json.loads(m.read_text(encoding="utf-8"))
        by_page = {p: s["format"] for s in manifest["slices"] for p in range(s["start_page"], s["end_page"] + 1)}
        self.assertEqual(by_page, {1: "text", 2: "pdf", 3: "text"})
        # Monotonic emission: filenames 001, 002, 003 align with pages 1, 2, 3.
        self.assertTrue(manifest["slices"][0]["path"].startswith("001_"))
        self.assertTrue(manifest["slices"][1]["path"].startswith("002_"))
        self.assertTrue(manifest["slices"][2]["path"].startswith("003_"))

    def test_extract_invalid_pages_spec_raises_value_error(self):
        pdf = Path(self.temp_dir.name) / "two.pdf"
        _make_pdf(pdf, [self.dense, self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        for bad in ("5-2", "-1", "99", "abc", ","):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), page_spec=bad)

    def test_extract_pdf_mode_skips_text_sizing_and_records_portable_source_pdf(self):
        sub = self.repo_root / "books"
        sub.mkdir()
        pdf = sub / "module.pdf"
        _make_pdf(pdf, [self.dense, self.dense])
        out_dir = Path(self.temp_dir.name) / "out"
        with patch.object(generate_digests, "_page_text", side_effect=AssertionError("should not extract text")) :
            m = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf")
        manifest = json.loads(m.read_text(encoding="utf-8"))
        self.assertEqual(manifest["source_pdf"], "books/module.pdf")
        m_override = generate_digests.extract_pdf(
            str(pdf), self.repo_root, out_dir=str(out_dir), format="pdf", source_pdf="custom/mod.pdf"
        )
        self.assertEqual(json.loads(m_override.read_text(encoding="utf-8"))["source_pdf"], "custom/mod.pdf")

    def test_compile_references_source_field_parity(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        digests_dir.mkdir(parents=True)
        (digests_dir / "_index.md").write_text(
            "---\nsource: morgansfort\ntier: 3\nentity_type: index\ntitle: Morgansfort\n---\n\n# Morgansfort\n\nIntro.\n",
            encoding="utf-8",
        )
        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.repo_root / ".agents" / "context" / "references.json").read_text(encoding="utf-8"))
        self.assertEqual(refs["sources"][0]["source"], "morgansfort")

    def test_main_validate_exit_code(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        self._write_valid_note(digest_dir)
        argv = ["generate_digests.py", "--repo-root", str(self.repo_root), "--validate"]
        with patch.object(sys, "argv", argv), patch("sys.stdout", new=io.StringIO()):
            with self.assertRaises(SystemExit) as ctx:
                generate_digests.main()
        self.assertEqual(ctx.exception.code, 0)

    def test_compile_references_nested_leaf_stems_do_not_misclassify_category(self):
        digests_dir = self.repo_root / "_gm-materials" / "digests" / "gradient_descent"
        (digests_dir / "locations").mkdir(parents=True)
        (digests_dir / "tables").mkdir(parents=True)
        (digests_dir / "_index.md").write_text(
            "---\nsource: gradient_descent\nsource_pdf: Gradient-Descent-v1.1.pdf\ntier: 3\nentity_type: index\ntitle: Gradient Descent\n---\n\n# Gradient Descent\n\nIntro.\n",
            encoding="utf-8",
        )
        (digests_dir / "locations" / "floor_5_ai_core.md").write_text(
            "---\nsource: gradient_descent\nsource_pdf: Gradient-Descent-v1.1.pdf\ntier: 3\nentity_type: location\ntitle: Floor 5 AI Core\n---\n\n# Floor 5 AI Core\n\nDetails.\n",
            encoding="utf-8",
        )
        (digests_dir / "locations" / "station_map.md").write_text(
            "---\nsource: gradient_descent\nsource_pdf: Gradient-Descent-v1.1.pdf\ntier: 3\nentity_type: location\ntitle: Station Map\n---\n\n# Station Map\n\nDetails.\n",
            encoding="utf-8",
        )
        (digests_dir / "tables" / "bell_rumours.md").write_text(
            "---\nsource: gradient_descent\nsource_pdf: Gradient-Descent-v1.1.pdf\ncategory: supplement\ntier: 3\nentity_type: table\ntitle: Bell Rumours\n---\n\n# Bell Rumours\n\nDetails.\n",
            encoding="utf-8",
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.repo_root / ".agents" / "context" / "references.json").read_text(encoding="utf-8"))
        by_slug = {s["slug"]: s for s in refs["sources"]}
        self.assertEqual(by_slug["gradient_descent/_index"]["category"], "module")
        self.assertEqual(by_slug["gradient_descent/locations/floor_5_ai_core"]["category"], "module")
        self.assertEqual(by_slug["gradient_descent/locations/station_map"]["category"], "module")
        self.assertEqual(by_slug["gradient_descent/tables/bell_rumours"]["category"], "supplement")

    def test_compile_references_nested_book_inherits_index_category_and_slug(self):
        ep_dir = self.repo_root / "_gm-materials" / "digests" / "eclipse_phase"
        (ep_dir / "locations").mkdir(parents=True)
        (ep_dir / "_index.md").write_text(
            "---\nsource: eclipse_phase\nsource_pdf: Eclipse-Phase.pdf\ncategory: core_setting\ntier: 3\nentity_type: index\ntitle: Eclipse Phase\n---\n\n# Eclipse Phase\n\nIntro.\n",
            encoding="utf-8",
        )
        (ep_dir / "locations" / "locus.md").write_text(
            "---\nsource: eclipse_phase\nsource_pdf: Eclipse-Phase.pdf\ntier: 3\nentity_type: location\ntitle: Locus\n---\n\n# Locus\n\nIntro.\n",
            encoding="utf-8",
        )

        core_dir = self.repo_root / "_gm-materials" / "digests" / "mothership_core"
        (core_dir / "factions").mkdir(parents=True)
        (core_dir / "_index.md").write_text(
            "---\nsource: mothership_core\nsource_pdf: Mothership.pdf\ntier: 3\nentity_type: index\ntitle: Mothership Core\n---\n\n# Mothership Core\n\nIntro.\n",
            encoding="utf-8",
        )
        (core_dir / "factions" / "company.md").write_text(
            "---\nsource: mothership_core\nsource_pdf: Mothership.pdf\ntier: 3\nentity_type: faction\ntitle: Company\n---\n\n# Company\n\nIntro.\n",
            encoding="utf-8",
        )

        generate_digests.compile_references(self.repo_root, self.repo_root)
        refs = json.loads((self.repo_root / ".agents" / "context" / "references.json").read_text(encoding="utf-8"))
        by_slug = {s["slug"]: s for s in refs["sources"]}
        self.assertEqual(by_slug["eclipse_phase/_index"]["category"], "core_setting")
        self.assertEqual(by_slug["eclipse_phase/locations/locus"]["category"], "core_setting")
        self.assertEqual(by_slug["mothership_core/_index"]["category"], "core_setting")
        self.assertEqual(by_slug["mothership_core/factions/company"]["category"], "core_setting")

    def test_extract_default_min_chars_per_page_is_160_and_catches_sparse_page(self):
        pdf = Path(self.temp_dir.name) / "calibrated.pdf"
        caption_only = "Figure 1.2: Cargo bay exterior schematic showing docking clamps and hull plating."  # 83 chars
        _make_pdf(pdf, [self.dense, caption_only])
        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="auto")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["min_chars_per_page"], 160)
        self.assertEqual(manifest["slices"][0]["format"], "text")
        self.assertEqual(manifest["slices"][1]["format"], "pdf")
        self.assertIn("low text density", manifest["slices"][1]["auto_fallback_reason"])

    def test_extract_image_heavy_fallback_and_large_image_telemetry(self):
        from pypdf import PdfWriter
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

        pdf = Path(self.temp_dir.name) / "illustrated.pdf"
        _make_pdf(
            pdf,
            [
                "Caption text for full-page station map showing docking ring, reactor spine, and airlocks. " * 2,  # ~180 chars
                self.dense * 2,  # ~468 chars (>= 320)
                "Tiny icon caption text repeated enough to exceed threshold cleanly without large artwork. " * 2,  # ~178 chars
            ],
        )

        # Inject /Image XObjects onto pages 1, 2 (400x400 large) and page 3 (32x32 tiny icon)
        from pypdf import PdfReader
        reader = PdfReader(str(pdf))
        writer = PdfWriter()
        for idx, page in enumerate(reader.pages):
            writer.add_page(page)
            target_page = writer.pages[idx]
            img = DecodedStreamObject()
            img[NameObject("/Type")] = NameObject("/XObject")
            img[NameObject("/Subtype")] = NameObject("/Image")
            side = 32 if idx == 2 else 400
            img[NameObject("/Width")] = NumberObject(side)
            img[NameObject("/Height")] = NumberObject(side)
            img.set_data(b"\x00")
            img_ref = writer._add_object(img)
            res = target_page["/Resources"].get_object()
            xobj = DictionaryObject()
            xobj[NameObject("/Im0")] = img_ref
            res[NameObject("/XObject")] = xobj
        with open(pdf, "wb") as fh:
            writer.write(fh)

        out_dir = Path(self.temp_dir.name) / "out"
        manifest_path = generate_digests.extract_pdf(str(pdf), self.repo_root, out_dir=str(out_dir), format="auto")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        by_page = {p: s for s in manifest["slices"] for p in range(s["start_page"], s["end_page"] + 1)}

        # Page 1: sparse caption + large image -> auto fallback to pdf
        self.assertEqual(by_page[1]["format"], "pdf")
        self.assertIn("image-heavy page", by_page[1]["auto_fallback_reason"])
        self.assertEqual(by_page[1]["image_count"], 1)
        self.assertTrue(by_page[1]["has_large_images"])
        self.assertEqual(by_page[1]["large_image_pages"], [1])

        # Pages 2-3 coalesce into one text slice: p.2 has 400x400 image, p.3 has 32x32 icon
        self.assertEqual(by_page[2]["format"], "text")
        self.assertIsNone(by_page[2]["auto_fallback_reason"])
        self.assertEqual((by_page[2]["start_page"], by_page[2]["end_page"]), (2, 3))
        self.assertEqual(by_page[2]["image_count"], 2)
        self.assertTrue(by_page[2]["has_large_images"])
        self.assertEqual(by_page[2]["large_image_pages"], [2])

    def test_count_xobject_images_handles_forms_and_cycles(self):
        from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject

        img = DecodedStreamObject()
        img[NameObject("/Subtype")] = NameObject("/Image")
        img[NameObject("/Width")] = NumberObject(600)
        img[NameObject("/Height")] = NumberObject(150)

        form = DictionaryObject()
        form[NameObject("/Subtype")] = NameObject("/Form")
        form_xobj = DictionaryObject()
        form_xobj[NameObject("/Banner")] = img
        form_xobj[NameObject("/SelfLoop")] = form  # cyclic /Form reference
        form[NameObject("/Resources")] = DictionaryObject({NameObject("/XObject"): form_xobj})

        page = DictionaryObject()
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/XObject"): DictionaryObject({NameObject("/Fm0"): form})}
        )

        total, large = generate_digests._count_xobject_images(page, set())
        self.assertEqual(total, 1)
        self.assertEqual(large, 1)

        # Non-numeric /Width on an /Image XObject still counts the image as non-large
        from pypdf.generic import TextStringObject
        bad_img = DecodedStreamObject()
        bad_img[NameObject("/Subtype")] = NameObject("/Image")
        bad_img[NameObject("/Width")] = TextStringObject("unknown")
        bad_img[NameObject("/Height")] = NumberObject(400)
        bad_page = DictionaryObject(
            {NameObject("/Resources"): DictionaryObject({NameObject("/XObject"): DictionaryObject({NameObject("/ImBad"): bad_img})})}
        )
        self.assertEqual(generate_digests._count_xobject_images(bad_page, set()), (1, 0))

    def test_validate_manifest_telemetry_reports_large_image_pages(self):
        digest_dir = self.repo_root / "_gm-materials" / "digests" / "book"
        self._write_valid_note(digest_dir)
        manifest = Path(self.temp_dir.name) / "manifest.json"
        manifest.write_text(
            json.dumps({
                "slices": [
                    {"format": "text", "has_large_images": True, "large_image_pages": [18, 23], "auto_fallback_reason": None},
                    {"format": "text", "has_large_images": True, "large_image_pages": None, "auto_fallback_reason": None},
                    {"format": "text", "has_large_images": False, "large_image_pages": [], "auto_fallback_reason": None},
                ]
            }),
            encoding="utf-8",
        )
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            rc = generate_digests.validate_digests(self.repo_root, digest_dir, manifest=str(manifest))
        self.assertEqual(rc, 0)
        self.assertIn("text slices with large images: 2 slice(s) (pages: [18, 23])", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
