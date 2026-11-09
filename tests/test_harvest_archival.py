#!/usr/bin/env python3
"""
Unit tests for Archival Scriptorium (scripts/harvest_archival.py).

Verifies licensing validation, anti-AI lexical scanning, relative path calculation,
HTML footer formatting, front-matter patching, payload parsing, API clients,
Ollama query generation, and disk cleanup.
"""

import io
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure scripts directory is in python path
ENGINE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ENGINE_ROOT / "scripts"))

from harvest_archival import (
    ArchivalCandidate,
    calculate_relative_image_path,
    cleanup_temp_candidates,
    download_candidate_image,
    format_footer_html,
    generate_deterministic_fallback_queries,
    is_ai_provenance,
    parse_met_object_payload,
    parse_note_metadata,
    parse_wikimedia_imageinfo,
    patch_note_frontmatter,
    query_ollama_search_terms,
    search_met_museum,
    search_wikimedia_commons,
    validate_licence_string,
)


class TestLicenceValidation(unittest.TestCase):
    """Test machine-readable rights and licence normalisation."""

    def test_valid_cc0_and_public_domain(self):
        """Ensure CC0 and historical public domain variants pass."""
        valid_licences = [
            "CC0",
            "CC0 1.0",
            "CC0 1.0 Universal",
            "cc0",
            "Public domain",
            "Public Domain",
            "PD",
            "PD-Art",
            "PD-old-100",
            "PD-US",
            "PD-scan",
            "Public Domain Mark 1.0",
            "No Copyright",
        ]
        for lic in valid_licences:
            with self.subTest(licence=lic):
                self.assertTrue(validate_licence_string(lic), f"Expected '{lic}' to be valid.")

    def test_valid_creative_commons_attribution(self):
        """Ensure open CC BY and CC BY-SA licences pass."""
        valid_cc = [
            "CC BY 4.0",
            "CC-BY 4.0",
            "CC BY-SA 4.0",
            "CC-BY-SA 4.0",
            "CC BY 3.0",
            "CC BY-SA 3.0",
            "cc by 2.0",
        ]
        for lic in valid_cc:
            with self.subTest(licence=lic):
                self.assertTrue(validate_licence_string(lic), f"Expected '{lic}' to be valid.")

    def test_rejected_restrictive_and_ambiguous_licences(self):
        """Ensure non-commercial, no-derivatives, copyrighted, and empty licences fail."""
        rejected_licences = [
            "All Rights Reserved",
            "Copyrighted",
            "In copyright",
            "CC BY-NC 4.0",
            "CC BY-NC-SA 4.0",
            "CC BY-ND 4.0",
            "Fair Use",
            "",
            "   ",
            None,
        ]
        for lic in rejected_licences:
            with self.subTest(licence=lic):
                self.assertFalse(validate_licence_string(lic), f"Expected '{lic}' to be rejected.")


class TestAIProvenanceScanner(unittest.TestCase):
    """Test detection and immediate rejection of generative AI imagery."""

    def test_rejects_ai_categories(self):
        """Ensure categories containing AI markers are flagged as AI provenance."""
        ai_categories = [
            ["Category:Images generated with Midjourney", "Category:Portraits"],
            ["Category:AI-generated art", "Category:Digital paintings"],
            ["Category:Stable Diffusion images"],
            ["Category:DALL-E 3 illustrations"],
            ["Category:Generative AI media", "Category:Sci-fi"],
        ]
        for cats in ai_categories:
            with self.subTest(categories=cats):
                self.assertTrue(is_ai_provenance(cats), f"Expected {cats} to be flagged as AI.")

    def test_rejects_ai_descriptions(self):
        """Ensure description text mentioning AI generation is caught."""
        ai_descriptions = [
            "Created using Midjourney v6 and Photoshop touch-up.",
            "Prompt for DALL-E: antique automaton engraving.",
            "Rendered with Stable Diffusion checkpoint realistic_vision.",
            "Experimental generative AI plate, public domain release.",
        ]
        for desc in ai_descriptions:
            with self.subTest(desc=desc):
                self.assertTrue(
                    is_ai_provenance(["Category:Historical prints"], description=desc),
                    f"Expected '{desc}' to be flagged as AI.",
                )

    def test_accepts_authentic_historical_artefacts(self):
        """Ensure genuine museum categories and descriptions pass cleanly."""
        cats = [
            "Category:18th-century engravings",
            "Category:Automata in art",
            "Category:Collections of the Metropolitan Museum of Art",
            "Category:Edo period metalwork",
        ]
        desc = "Copperplate engraving of an astronomical celestial globe by Johann Doppelmayr, Nuremberg, 1742."
        self.assertFalse(is_ai_provenance(cats, description=desc))


class TestRelativePathCalculation(unittest.TestCase):
    """Test note-relative image path calculation for Jekyll data_extractor compatibility."""

    def setUp(self):
        self.repo_root = Path("/vault")

    def test_directory_subdir_depth_two(self):
        """Note in directory/Atles/IronPot.md -> ../../imgs/gallery/iron-pot.jpg."""
        note = self.repo_root / "directory" / "Atles" / "IronPot.md"
        rel_path = calculate_relative_image_path(note, self.repo_root, "imgs/gallery/iron-pot.jpg")
        self.assertEqual(rel_path, "../../imgs/gallery/iron-pot.jpg")

    def test_campaign_subdir_depth_two(self):
        """Note in campaigns/gradient-descent/001.md -> ../../imgs/gallery/airlock.jpg."""
        note = self.repo_root / "campaigns" / "gradient-descent" / "001.md"
        rel_path = calculate_relative_image_path(note, self.repo_root, "imgs/gallery/airlock.jpg")
        self.assertEqual(rel_path, "../../imgs/gallery/airlock.jpg")

    def test_systems_subdir_depth_one(self):
        """Note in systems/trade.md -> ../imgs/gallery/ledger.jpg."""
        note = self.repo_root / "systems" / "trade.md"
        rel_path = calculate_relative_image_path(note, self.repo_root, "imgs/gallery/ledger.jpg")
        self.assertEqual(rel_path, "../imgs/gallery/ledger.jpg")

    def test_root_index_depth_zero(self):
        """Note at repository root index.md -> imgs/gallery/cover.jpg."""
        note = self.repo_root / "index.md"
        rel_path = calculate_relative_image_path(note, self.repo_root, "imgs/gallery/cover.jpg")
        self.assertEqual(rel_path, "imgs/gallery/cover.jpg")


class TestHTMLFooterFormatting(unittest.TestCase):
    """Test theme-compliant HTML attribution formatting in footer_content."""

    def test_format_footer_html(self):
        """Ensure footer_content contains valid <a> markup with security attributes."""
        candidate = ArchivalCandidate(
            candidate_id="abc123hash",
            title="Cast-iron Tetsubin kettle",
            creator="Unknown Edo craftsman",
            date_created="Edo period",
            institution="Rijksmuseum collection via Wikimedia Commons",
            source_page_url="https://commons.wikimedia.org/wiki/File:Kettle.jpg",
            raw_image_url="https://upload.wikimedia.org/.../Kettle.jpg",
            licence="CC0",
            is_public_domain=True,
        )
        footer = format_footer_html(candidate)
        self.assertIn('<a href="https://commons.wikimedia.org/wiki/File:Kettle.jpg"', footer)
        self.assertIn('target="_blank"', footer)
        self.assertIn('rel="noopener noreferrer"', footer)
        self.assertIn("Cast-iron Tetsubin kettle", footer)
        self.assertIn("(Edo period)", footer)
        self.assertIn("Rijksmuseum collection via Wikimedia Commons", footer)
        self.assertIn("CC0", footer)


class TestFrontmatterPatching(unittest.TestCase):
    """Test non-destructive front-matter mutation."""

    def test_patch_new_images_and_footer(self):
        """Insert images and footer_content when neither existed."""
        original = (
            "---\n"
            "layout: default\n"
            "title: Iron Pot\n"
            "parent: Atles\n"
            "---\n\n"
            "# Iron Pot\n\n"
            "A biomechanical cultist chassis.\n"
        )
        patched = patch_note_frontmatter(
            original,
            "../../imgs/gallery/iron-pot.jpg",
            'Image adapted from <a href="url">Kettle</a>. CC0.',
        )
        self.assertIn("images:\n  - ../../imgs/gallery/iron-pot.jpg", patched)
        self.assertIn('footer_content: \'Image adapted from <a href="url">Kettle</a>. CC0.\'', patched)
        self.assertIn("title: Iron Pot", patched)
        self.assertIn("A biomechanical cultist chassis.", patched)

    def test_prepend_to_existing_images_list(self):
        """Prepend new image to an existing images list, preserving existing items."""
        original = (
            "---\n"
            "layout: default\n"
            "title: Iron Pot\n"
            "images:\n"
            "  - ../../imgs/gallery/old_render.jpg\n"
            "---\n\n"
            "Body text.\n"
        )
        patched = patch_note_frontmatter(
            original,
            "../../imgs/gallery/iron-pot.jpg",
            'Image adapted from <a href="url">Kettle</a>. CC0.',
        )
        expected_images = (
            "images:\n"
            "  - ../../imgs/gallery/iron-pot.jpg\n"
            "  - ../../imgs/gallery/old_render.jpg"
        )
        self.assertIn(expected_images, patched)

    def test_replace_placeholder_badge(self):
        """Replace fallback geometric badge with real gallery image."""
        original = (
            "---\n"
            "layout: default\n"
            "title: Iron Pot\n"
            "images:\n"
            "  - /imgs/badges/people.png\n"
            "---\n\n"
            "Body text.\n"
        )
        patched = patch_note_frontmatter(
            original,
            "../../imgs/gallery/iron-pot.jpg",
            'Image adapted from <a href="url">Kettle</a>. CC0.',
        )
        self.assertIn("images:\n  - ../../imgs/gallery/iron-pot.jpg", patched)
        self.assertNotIn("/imgs/badges/people.png", patched)

    def test_preserves_comments_and_dataview(self):
        """Ensure comments and Dataview blocks survive surgical patching."""
        original = (
            "---\n"
            "layout: default\n"
            "# Important note comment\n"
            "title: Iron Pot\n"
            "---\n\n"
            "```dataview\n"
            "TABLE file.mtime WHERE parent = this.file.link\n"
            "```\n"
        )
        patched = patch_note_frontmatter(
            original,
            "../../imgs/gallery/iron-pot.jpg",
            'Image adapted from <a href="url">Kettle</a>. CC0.',
        )
        self.assertIn("# Important note comment", patched)
        self.assertIn("```dataview\nTABLE file.mtime WHERE parent = this.file.link\n```", patched)


class TestDeterministicFallbackQueries(unittest.TestCase):
    """Test fallback query generator when Ollama is offline."""

    def test_fallback_queries(self):
        """Verify queries derived from title and parent metadata."""
        meta = {"title": "Iron Pot", "parent": "Atles"}
        queries = generate_deterministic_fallback_queries(meta)
        self.assertEqual(len(queries), 3)
        self.assertIn("Iron Pot", queries)
        self.assertIn("Iron Pot engraving", queries)
        self.assertIn("Atles artifact", queries)


class TestMetObjectParser(unittest.TestCase):
    """Test parsing The Met Museum API JSON responses."""

    def test_valid_public_domain_object(self):
        """Parse valid public domain object with image."""
        data = {
            "objectID": 436535,
            "isPublicDomain": True,
            "title": "Wheat Field with Cypresses",
            "artistDisplayName": "Vincent van Gogh",
            "objectDate": "1889",
            "repository": "Metropolitan Museum of Art, New York, NY",
            "objectURL": "https://www.metmuseum.org/art/collection/search/436535",
            "primaryImage": "https://images.metmuseum.org/.../DT1567.jpg",
            "primaryImageSmall": "https://images.metmuseum.org/.../web-large/DT1567.jpg",
        }
        cand = parse_met_object_payload(data)
        self.assertIsNotNone(cand)
        self.assertEqual(cand.title, "Wheat Field with Cypresses")
        self.assertEqual(cand.creator, "Vincent van Gogh")
        self.assertEqual(cand.institution, "The Metropolitan Museum of Art")
        self.assertTrue(cand.is_public_domain)
        self.assertEqual(cand.licence, "Public Domain (Met Open Access)")
        self.assertEqual(cand.raw_image_url, "https://images.metmuseum.org/.../DT1567.jpg")

    def test_rejects_non_public_domain(self):
        """Skip objects where isPublicDomain is False."""
        data = {
            "objectID": 12345,
            "isPublicDomain": False,
            "title": "Modern Artwork",
            "primaryImage": "https://images.metmuseum.org/.../image.jpg",
        }
        self.assertIsNone(parse_met_object_payload(data))

    def test_rejects_empty_image(self):
        """Skip objects without images."""
        data = {
            "objectID": 67890,
            "isPublicDomain": True,
            "title": "Unphotographed Coin",
            "primaryImage": "",
            "primaryImageSmall": "",
        }
        self.assertIsNone(parse_met_object_payload(data))


class TestWikimediaImageInfoParser(unittest.TestCase):
    """Test parsing Wikimedia Commons API responses."""

    def test_valid_wikimedia_item(self):
        """Parse Wikimedia imageinfo payload with dictionary LicenseShortName."""
        data = {
            "query": {
                "pages": {
                    "101": {
                        "pageid": 101,
                        "title": "File:Antique automaton.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/.../Antique_automaton.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Antique_automaton.jpg",
                                "width": 1200,
                                "height": 1600,
                                "extmetadata": {
                                    "ObjectName": {"value": "Antique automaton monk"},
                                    "Artist": {"value": "Juanelo Turriano (attributed)"},
                                    "DateTime": {"value": "ca. 1560"},
                                    "LicenseShortName": {"value": "CC0"},
                                    "Categories": {"value": "16th-century automata|Spanish Renaissance"},
                                },
                            }
                        ],
                    }
                }
            }
        }
        candidates = parse_wikimedia_imageinfo(data)
        self.assertEqual(len(candidates), 1)
        cand = candidates[0]
        self.assertEqual(cand.title, "Antique automaton monk")
        self.assertEqual(cand.creator, "Juanelo Turriano (attributed)")
        self.assertEqual(cand.licence, "CC0")
        self.assertTrue(cand.is_public_domain)

    def test_rejects_ai_categories_in_wikimedia(self):
        """Discard Wikimedia items flagged as AI generated."""
        data = {
            "query": {
                "pages": {
                    "202": {
                        "pageid": 202,
                        "title": "File:AI_automaton.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/.../AI_automaton.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:AI_automaton.jpg",
                                "width": 1024,
                                "height": 1024,
                                "extmetadata": {
                                    "ObjectName": {"value": "Midjourney Automaton"},
                                    "LicenseShortName": {"value": "CC0"},
                                    "Categories": {"value": "Images generated with Midjourney|Robots in art"},
                                },
                            }
                        ],
                    }
                }
            }
        }
        candidates = parse_wikimedia_imageinfo(data)
        self.assertEqual(len(candidates), 0)

    def test_rejects_low_resolution(self):
        """Discard Wikimedia items smaller than 800px width."""
        data = {
            "query": {
                "pages": {
                    "303": {
                        "pageid": 303,
                        "title": "File:Tiny_scan.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/.../Tiny_scan.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Tiny_scan.jpg",
                                "width": 400,
                                "height": 300,
                                "extmetadata": {
                                    "ObjectName": {"value": "Tiny Thumbnail"},
                                    "LicenseShortName": {"value": "Public domain"},
                                    "Categories": {"value": "Historical prints"},
                                },
                            }
                        ],
                    }
                }
            }
        }
        candidates = parse_wikimedia_imageinfo(data)
        self.assertEqual(len(candidates), 0)


class TestOllamaQueryExpansion(unittest.TestCase):
    """Test querying Ollama and deterministic fallback handling."""

    @patch("urllib.request.urlopen")
    def test_successful_ollama_query_expansion(self, mock_urlopen):
        """Parse valid JSON list from Ollama response."""
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"response": '["18th-century automaton", "renaissance clockwork", "antique brazier"]'}
        ).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        queries = query_ollama_search_terms({"title": "Iron Pot", "parent": "Atles"})
        self.assertEqual(len(queries), 3)
        self.assertEqual(queries[0], "18th-century automaton")

    @patch("urllib.request.urlopen")
    def test_ollama_offline_fallback(self, mock_urlopen):
        """Verify fallback to deterministic terms when Ollama connection fails."""
        mock_urlopen.side_effect = ConnectionRefusedError("Ollama offline")

        queries = query_ollama_search_terms({"title": "Iron Pot", "parent": "Atles"})
        self.assertEqual(len(queries), 3)
        self.assertIn("Iron Pot", queries)
        self.assertIn("Iron Pot engraving", queries)


class TestMetMuseumClient(unittest.TestCase):
    """Test querying The Met Museum API with bounds."""

    @patch("urllib.request.urlopen")
    def test_search_met_museum_bounded(self, mock_urlopen):
        """Verify search queries search endpoint and bounds candidate detail fetches."""
        search_payload = {"total": 50, "objectIDs": [101, 102, 103, 104, 105, 106, 107, 108]}
        obj_payload = {
            "objectID": 101,
            "isPublicDomain": True,
            "title": "Ancient Relic",
            "artistDisplayName": "Unknown",
            "objectDate": "ca. 1400",
            "primaryImage": "https://images.metmuseum.org/.../relic.jpg",
        }

        mock_search_resp = MagicMock()
        mock_search_resp.read.return_value = json.dumps(search_payload).encode("utf-8")
        mock_search_resp.__enter__.return_value = mock_search_resp

        mock_obj_resp = MagicMock()
        mock_obj_resp.read.return_value = json.dumps(obj_payload).encode("utf-8")
        mock_obj_resp.__enter__.return_value = mock_obj_resp

        # First call is search, subsequent calls are object IDs
        mock_urlopen.side_effect = [mock_search_resp] + [mock_obj_resp] * 6

        candidates = search_met_museum("relic", max_candidates=3)
        self.assertTrue(len(candidates) >= 1)
        self.assertEqual(candidates[0].title, "Ancient Relic")


class TestWikimediaCommonsClient(unittest.TestCase):
    """Test querying Wikimedia Commons Action API."""

    @patch("urllib.request.urlopen")
    def test_search_wikimedia_commons(self, mock_urlopen):
        """Verify Wikimedia search returns parsed candidates."""
        wiki_payload = {
            "query": {
                "pages": {
                    "555": {
                        "pageid": 555,
                        "title": "File:Armillary_sphere.jpg",
                        "imageinfo": [
                            {
                                "url": "https://upload.wikimedia.org/.../Armillary_sphere.jpg",
                                "descriptionurl": "https://commons.wikimedia.org/wiki/File:Armillary_sphere.jpg",
                                "width": 1200,
                                "height": 1200,
                                "extmetadata": {
                                    "ObjectName": {"value": "Renaissance Armillary Sphere"},
                                    "LicenseShortName": {"value": "CC0"},
                                    "Categories": {"value": "Astronomical instruments"},
                                },
                            }
                        ],
                    }
                }
            }
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(wiki_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        candidates = search_wikimedia_commons("armillary sphere", max_candidates=2)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].title, "Renaissance Armillary Sphere")


class TestDiskHygieneAndCleanup(unittest.TestCase):
    """Test candidate asset download and cleanup routines."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="scriptorium_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cleanup_unselected_candidates(self):
        """Verify discarded candidate raw and styled files are removed, preserving chosen candidate."""
        c1 = ArchivalCandidate(
            candidate_id="c1",
            title="Candidate 1",
            creator="Artist",
            date_created="1700",
            institution="Met",
            source_page_url="url1",
            raw_image_url="img1",
            licence="CC0",
            is_public_domain=True,
        )
        c2 = ArchivalCandidate(
            candidate_id="c2",
            title="Candidate 2",
            creator="Artist",
            date_created="1800",
            institution="Wiki",
            source_page_url="url2",
            raw_image_url="img2",
            licence="PD",
            is_public_domain=True,
        )

        f1 = self.test_dir / "c1_raw.jpg"
        f1.write_bytes(b"dummy image 1")
        c1.raw_file_path = f1

        f2_raw = self.test_dir / "c2_raw.jpg"
        f2_raw.write_bytes(b"dummy image 2")
        c2.raw_file_path = f2_raw

        f2_styled = self.test_dir / "c2_styled.jpg"
        f2_styled.write_bytes(b"dummy styled 2")
        c2.styled_variants["classic"] = f2_styled

        # Choose c1, discard c2
        cleanup_temp_candidates([c1, c2], chosen_candidate=c1)

        self.assertFalse(f2_raw.exists())
        self.assertFalse(f2_styled.exists())


class TestNoteMetadataParser(unittest.TestCase):
    """Test extracting title, parent, and body snippets from markdown notes."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="note_meta_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_parse_note_metadata(self):
        """Extract metadata from full front-matter markdown file."""
        note_file = self.test_dir / "IronPot.md"
        note_file.write_text(
            "---\n"
            "layout: default\n"
            "title: Iron Pot\n"
            "parent: Atles\n"
            "---\n\n"
            "# Iron Pot 6-body\n\n"
            "A biomechanical cultist chassis wandering the trail.\n",
            encoding="utf-8",
        )
        meta = parse_note_metadata(note_file)
        self.assertEqual(meta["title"], "Iron Pot")
        self.assertEqual(meta["parent"], "Atles")
        self.assertIn("A biomechanical cultist chassis wandering the trail.", meta["body_snippet"])


if __name__ == "__main__":
    unittest.main()
