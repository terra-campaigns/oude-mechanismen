#!/usr/bin/env python3
"""
tests/test_lint_wiki.py — Unit and integration tests for scripts/lint_wiki.py.
"""

import contextlib
import hashlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_wiki
import scribe_session
import tier2  # noqa: E402


def note_content(title: str, prose_lines: int = 4, extra_fm: str = "") -> str:
    """Build a compliant content note with front matter and prose body."""
    body = "\n".join(f"Prose sentence number {i}." for i in range(1, prose_lines + 1))
    fm_extra = f"{extra_fm}\n" if extra_fm else ""
    return f"---\ntitle: {title}\nparent: Index\n{fm_extra}---\n\n{body}\n"


class LintWikiTestCase(unittest.TestCase):
    """Base class scaffolding a minimal clean campaign vault."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        for d in (
            "campaigns/arc",
            "directory",
            "systems",
            "statblocks",
            "imgs/gallery",
            "imgs/badges",
            ".agents/context",
        ):
            (self.root / d).mkdir(parents=True, exist_ok=True)
        self._write(
            ".agents/context/tier1_sources.yml",
            "drive_dir: .\ninclude_paths:\n  - campaigns\n  - directory\n  - systems\n",
        )
        self._write(
            "index.md",
            "---\ntitle: Home\n---\n\nWelcome to the campaign wiki.\nLinks follow below.\nSee the arc.\n",
        )
        self._write("campaigns/arc/ep001.md", note_content("Episode 001"))
        self._write("directory/place.md", note_content("The Place"))
        # Index links to both notes so nothing is orphaned or dead.
        self._write(
            "index.md",
            "---\ntitle: Home\n---\n\nWelcome to the campaign wiki.\nSee [Episode 001](campaigns/arc/ep001.md).\nAnd [The Place](directory/place.md).\n",
        )
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md"])

    def tearDown(self):
        self.temp_dir.cleanup()

    def _write(self, rel: str, content: str) -> Path:
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return p

    def _write_catalog(self, rels):
        entries = []
        for rel in rels:
            note_path = self.root / rel
            content = note_path.read_text(encoding="utf-8") if note_path.exists() else ""
            fm, body, _ = lint_wiki.parse_front_matter(content)
            entries.append(
                {
                    "path": rel,
                    "title": fm.get("title", Path(rel).stem),
                    "summary": "summary" if lint_wiki.prose_line_count(body) >= 3 else None,
                    "sha": hashlib.sha256(content.encode("utf-8")).hexdigest()[:8],
                }
            )
        self._write(
            ".agents/context/catalog.json", json.dumps({"total_entries": len(entries), "entries": entries})
        )

    def _findings(self, report, check):
        return [f for f in report.findings if f.check == check]

    def _run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = lint_wiki.main(argv)
        return rc, buf.getvalue()


class TestCleanVault(LintWikiTestCase):
    def test_clean_vault_has_no_findings(self):
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(report.mode, "full")
        self.assertEqual(report.findings, [])
        self.assertFalse(report.has_failures())

    def test_main_clean_returns_zero(self):
        rc, out = self._run_main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertIn("Wiki is clean", out)

    def test_json_output_is_machine_readable(self):
        rc, out = self._run_main(["--root", str(self.root), "--format", "json"])
        self.assertEqual(rc, 0)
        payload = json.loads(out)
        self.assertEqual(payload["mode"], "full")
        self.assertEqual(payload["findings"], [])
        self.assertEqual(payload["summary"]["total"], 0)


class TestDeadLinks(LintWikiTestCase):
    def test_dead_link_is_fail_with_line_number(self):
        self._write(
            "campaigns/arc/ep001.md",
            note_content("Episode 001", extra_fm="") .replace(
                "Prose sentence number 1.", "See [missing](directory/nowhere.md)."
            ),
        )
        report = lint_wiki.lint_wiki(self.root)
        dead = self._findings(report, "dead-link")
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].severity, "FAIL")
        self.assertEqual(dead[0].file, "campaigns/arc/ep001.md")
        self.assertEqual(dead[0].line, 6)
        self.assertTrue(report.has_failures())

    def test_external_links_are_ignored(self):
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.", "See [site](https://example.com/page)."
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_root_absolute_link_resolves(self):
        content = note_content("The Place").replace(
            "Prose sentence number 2.", "Back to [home](/index.md)."
        )
        self._write("directory/place.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_gm_materials_link_exempt_when_dir_absent(self):
        # _gm-materials/ is gitignored and absent on CI; its targets must not FAIL.
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "{% comment %}\n"
            "- [GM link](../../_gm-materials/digests/foo/bar.md)\n"
            "- [GM abs](/_gm-materials/digests/foo/bar.md)\n"
            "{% endcomment %}",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_comment_block_link_to_missing_tier1_file_still_fails(self):
        # Comment blocks stay scannable: hidden links to real vault paths are validated.
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "{% comment %}\n- [hidden](../directory/nowhere.md)\n{% endcomment %}",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        dead = self._findings(report, "dead-link")
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].severity, "FAIL")

    def test_gm_materials_link_fails_when_dir_present_but_target_missing(self):
        # When _gm-materials/ exists on disk, its targets are validated normally.
        (self.root / "_gm-materials/digests").mkdir(parents=True)
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "{% comment %}\n- [GM link](../../_gm-materials/digests/foo/missing.md)\n{% endcomment %}",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        dead = self._findings(report, "dead-link")
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].severity, "FAIL")

    def test_percent_encoded_gm_materials_target_exempt_when_dir_absent(self):
        # Encoded or query-wrapped _gm-materials segments are still exempt (dir absent).
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "- [enc](../../_gm-materials%2Fdigests/foo/bar.md)\n"
            "- [q](/_gm-materials/digests/foo/bar.md?next=x)\n"
            "- [case](../../_GM-Materials/digests/foo/bar.md)\n",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])


class TestOrphans(LintWikiTestCase):
    def test_orphan_directory_note_is_warn(self):
        self._write("directory/lonely.md", note_content("Lonely"))
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md", "directory/lonely.md"])
        report = lint_wiki.lint_wiki(self.root)
        orphans = self._findings(report, "orphan")
        self.assertEqual([o.file for o in orphans], ["directory/lonely.md"])
        self.assertEqual(orphans[0].severity, "WARN")

    def test_campaign_notes_are_never_orphans(self):
        self._write("campaigns/arc/ep002.md", note_content("Episode 002"))
        self._write_catalog(
            ["campaigns/arc/ep001.md", "campaigns/arc/ep002.md", "directory/place.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "orphan"), [])

    def test_inbound_link_prevents_orphan(self):
        self._write("directory/linked.md", note_content("Linked"))
        ep = (self.root / "campaigns/arc/ep001.md").read_text(encoding="utf-8")
        self._write(
            "campaigns/arc/ep001.md",
            ep.replace("Prose sentence number 3.", "Prose sentence number 3.\nSee [Linked](../../directory/linked.md)."),
        )
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/linked.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "orphan"), [])


class TestStubs(LintWikiTestCase):
    def test_stub_is_warn(self):
        self._write("directory/stub.md", "---\ntitle: Stub\nparent: Index\n---\n\nOnly one line.\n")
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md", "directory/stub.md"])
        report = lint_wiki.lint_wiki(self.root)
        stubs = self._findings(report, "stub")
        self.assertEqual([s.file for s in stubs], ["directory/stub.md"])

    def test_liquid_only_body_counts_as_stub(self):
        self._write(
            "directory/liquid.md",
            "---\ntitle: Liquid\nparent: Index\n---\n\n{% include header_directories.md %}\n{{ page.title }}\n",
        )
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/liquid.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual([s.file for s in self._findings(report, "stub")], ["directory/liquid.md"])

    def test_comment_blocks_and_liquid_includes_count_as_stub_without_null_summary_warning(self):
        # Issue #109: multi-line {% comment %} blocks (Dataview / crosslink-tiers) carry zero published prose.
        body = (
            "{% include header_directories.md %}\n\n"
            "{% comment %}\n"
            "```dataview\n"
            "LIST FROM [[]] SORT file.name ASC\n"
            "```\n"
            "- [Tier 3 link](../../_gm-materials/digests/book/entry.md)\n"
            "{% endcomment %}\n\n"
            "{%- comment -%}\n"
            "Whitespace-trimmed GM note line 1.\n"
            "Whitespace-trimmed GM note line 2.\n"
            "{%- endcomment -%}\n"
        )
        self.assertEqual(lint_wiki.prose_line_count(body), 0)
        self._write(
            "directory/comment_stub.md",
            f"---\ntitle: Comment Stub\nparent: Index\n---\n\n{body}",
        )
        # Re-link from index so it isn't flagged as orphan; populate catalog.json with summary: null
        self._write(
            "index.md",
            "---\ntitle: Home\n---\n\nWelcome.\n[Ep](campaigns/arc/ep001.md)\n[Place](directory/place.md)\n[Stub](directory/comment_stub.md)\n",
        )
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/comment_stub.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual([s.file for s in self._findings(report, "stub")], ["directory/comment_stub.md"])
        null_summary_warns = [
            f for f in self._findings(report, "catalogue") if "summary is null" in f.message
        ]
        self.assertEqual(null_summary_warns, [])

    def test_inline_liquid_comment_on_prose_line_still_counts_prose(self):
        body = (
            "First visible line. {% comment %}hidden note{% endcomment %}\n"
            "Second visible line.\n"
            "Third visible line.\n"
        )
        self.assertEqual(lint_wiki.prose_line_count(body), 3)


class TestUnusedImages(LintWikiTestCase):
    def test_unused_image_is_warn_but_gallery_and_badges_exempt(self):
        self._write("imgs/extra/unused.png", "PNG")
        self._write("imgs/gallery/hero.png", "PNG")
        self._write("imgs/badges/fallback.png", "PNG")
        ep = (self.root / "campaigns/arc/ep001.md").read_text(encoding="utf-8")
        self._write(
            "campaigns/arc/ep001.md",
            ep.replace("Prose sentence number 4.", "Prose sentence number 4.\n![badge](../imgs/badges/used.png)"),
        )
        self._write("imgs/badges/used.png", "PNG")
        report = lint_wiki.lint_wiki(self.root)
        unused = self._findings(report, "unused-image")
        self.assertEqual([u.file for u in unused], ["imgs/extra/unused.png"])

    def test_front_matter_image_reference_counts(self):
        self._write("imgs/badges/fm.png", "PNG")
        self._write(
            "directory/place.md",
            note_content("The Place", extra_fm="image: ../imgs/badges/fm.png"),
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "unused-image"), [])


class TestDeprecatedHooks(LintWikiTestCase):
    def test_hooks_field_is_warn(self):
        self._write("directory/hooked.md", note_content("Hooked", extra_fm="hooks: on_session_end"))
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/hooked.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        hooks = self._findings(report, "deprecated-hook")
        self.assertEqual([h.file for h in hooks], ["directory/hooked.md"])
        self.assertIn("hooks", hooks[0].message)


class TestCatalogue(LintWikiTestCase):
    def test_missing_catalog_is_warn(self):
        (self.root / ".agents/context/catalog.json").unlink()
        report = lint_wiki.lint_wiki(self.root)
        cat = self._findings(report, "catalogue")
        self.assertTrue(any(c.severity == "WARN" and "bundle exec jekyll build" in c.message for c in cat))
        self.assertFalse(report.has_failures())

    def test_sha_mismatch_is_fail(self):
        self._write("directory/place.md", note_content("The Place") + "\nExtra prose line.\n")
        report = lint_wiki.lint_wiki(self.root)
        cat = [c for c in self._findings(report, "catalogue") if "sha" in c.message]
        self.assertEqual(len(cat), 1)
        self.assertEqual(cat[0].severity, "FAIL")
        self.assertEqual(cat[0].file, "directory/place.md")

    def test_unindexed_note_is_warn(self):
        self._write("directory/new.md", note_content("New Note"))
        report = lint_wiki.lint_wiki(self.root)
        cat = [c for c in self._findings(report, "catalogue") if "absent from catalog" in c.message]
        self.assertEqual([c.file for c in cat], ["directory/new.md"])

    def test_stale_catalog_entry_is_warn(self):
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md", "directory/ghost.md"])
        report = lint_wiki.lint_wiki(self.root)
        cat = [c for c in self._findings(report, "catalogue") if "stale" in c.message]
        self.assertEqual([c.file for c in cat], ["directory/ghost.md"])


class TestFrontMatter(LintWikiTestCase):
    def test_missing_title_and_parent_are_fail(self):
        self._write("directory/notitle.md", "---\nparent: Index\n---\n\nOne prose.\nTwo prose.\nThree prose.\n")
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/notitle.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        fm = self._findings(report, "front-matter")
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0].severity, "FAIL")
        self.assertIn("title", fm[0].message)

    def test_non_default_layout_is_warn(self):
        self._write(
            "directory/custom.md",
            note_content("Custom", extra_fm="layout: custom"),
        )
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/custom.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        fm = [f for f in self._findings(report, "front-matter") if "layout" in f.message]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0].severity, "WARN")

    def test_index_md_layout_exempt(self):
        self._write("index.md", "---\ntitle: Home\nlayout: home\n---\n\nOne.\nTwo.\nThree.\n")
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "front-matter"), [])


class TestDuplicateTitles(LintWikiTestCase):
    def test_duplicate_title_is_fail(self):
        self._write("directory/place2.md", note_content("The Place"))
        self._write_catalog(
            ["campaigns/arc/ep001.md", "directory/place.md", "directory/place2.md"]
        )
        report = lint_wiki.lint_wiki(self.root)
        dups = self._findings(report, "duplicate-title")
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].severity, "FAIL")
        self.assertIn("The Place", dups[0].message)


class TestTargetedMode(LintWikiTestCase):
    def test_targeted_paths_skip_global_checks(self):
        self._write("directory/orphaned.md", note_content("Orphaned"))
        self._write(
            "campaigns/arc/ep001.md",
            note_content("Episode 001").replace(
                "Prose sentence number 1.", "See [missing](nope.md)."
            ),
        )
        report = lint_wiki.lint_wiki(self.root, paths=["campaigns/arc/ep001.md"])
        self.assertEqual(report.mode, "targeted")
        self.assertEqual(report.files_scanned, 1)
        self.assertIn("orphan", report.checks_skipped)
        self.assertEqual(self._findings(report, "orphan"), [])
        self.assertEqual(self._findings(report, "catalogue"), [])
        dead = self._findings(report, "dead-link")
        self.assertEqual(len(dead), 1)

    def test_targeted_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            lint_wiki.lint_wiki(self.root, paths=["does/not/exist.md"])


class TestExitCodes(LintWikiTestCase):
    def test_fail_finding_returns_one(self):
        self._write(
            "campaigns/arc/ep001.md",
            note_content("Episode 001").replace(
                "Prose sentence number 1.", "See [missing](nope.md)."
            ),
        )
        rc, _ = self._run_main(["--root", str(self.root)])
        self.assertEqual(rc, 1)

    def test_strict_turns_warn_into_failure(self):
        self._write("directory/stub.md", "---\ntitle: Stub\nparent: Index\n---\n\nOnly one line.\n")
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md", "directory/stub.md"])
        rc, _ = self._run_main(["--root", str(self.root), "--strict"])
        self.assertEqual(rc, 1)
        rc, _ = self._run_main(["--root", str(self.root)])
        self.assertEqual(rc, 0)  # WARN-only is fine without --strict

    def test_bad_root_returns_two(self):
        rc, _ = self._run_main(["--root", str(self.root / "nope")])
        self.assertEqual(rc, 2)


class TestPrReviewRegressions(LintWikiTestCase):
    """Regression tests for the external PR #50 review findings."""

    def test_section_index_pages_exempt_from_parent_and_stub(self):
        """Section index.md (has_children, no parent, Liquid-only body) is clean."""
        self._write(
            "directory/index.md",
            "---\nlayout: default\ntitle: Directory\nhas_children: true\n---\n\n{% include header_directories.md %}\n",
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "front-matter"), [])
        self.assertEqual(self._findings(report, "stub"), [])

    def test_links_inside_code_fences_are_ignored(self):
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "Prose sentence number 2.\n```\nSee [example](missing.md).\n```",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_liquid_link_targets_are_ignored(self):
        content = note_content("Episode 001").replace(
            "Prose sentence number 2.",
            "Prose sentence number 2.\n![img]({{ '/imgs/a.png' | relative_url }}) and [x]({{ page.url }}).",
        )
        self._write("campaigns/arc/ep001.md", content)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_invalid_catalog_json_is_fail(self):
        self._write(".agents/context/catalog.json", "{not valid json")
        report = lint_wiki.lint_wiki(self.root)
        cat = self._findings(report, "catalogue")
        self.assertTrue(any(c.severity == "FAIL" and "not valid JSON" in c.message for c in cat))

    def test_null_summary_for_non_stub_is_warn(self):
        self._write(
            ".agents/context/catalog.json",
            json.dumps(
                {
                    "entries": [
                        {
                            "path": "campaigns/arc/ep001.md",
                            "title": "Episode 001",
                            "summary": "ok",
                            "sha": lint_wiki.content_sha(self.root / "campaigns/arc/ep001.md"),
                        },
                        {
                            "path": "directory/place.md",
                            "title": "The Place",
                            "summary": None,
                            "sha": lint_wiki.content_sha(self.root / "directory/place.md"),
                        },
                    ]
                }
            ),
        )
        report = lint_wiki.lint_wiki(self.root)
        cat = [c for c in self._findings(report, "catalogue") if "summary is null" in c.message]
        self.assertEqual([c.file for c in cat], ["directory/place.md"])
        self.assertEqual(cat[0].severity, "WARN")

    def test_targeted_dir_scan_respects_exclude_paths(self):
        self._write("_TODO.md", note_content("Scratch").replace("Prose sentence number 1.", "See [x](nope.md)."))
        report = lint_wiki.lint_wiki(self.root, paths=["."])
        self.assertEqual(self._findings(report, "dead-link"), [])

    def test_targeted_mode_skips_duplicate_title(self):
        self._write("directory/place2.md", note_content("The Place"))
        report = lint_wiki.lint_wiki(self.root, paths=["directory/place2.md"])
        self.assertIn("duplicate-title", report.checks_skipped)
        self.assertEqual(self._findings(report, "duplicate-title"), [])

    def test_hidden_dotfiles_under_imgs_are_ignored(self):
        self._write("imgs/.DS_Store", "junk")
        self._write("imgs/extra/.DS_Store", "junk")
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "unused-image"), [])

    def test_config_yml_logo_and_favicon_count_as_referenced(self):
        self._write("imgs/favicon.ico", "ICO")
        self._write("imgs/logo.png", "PNG")
        self._write("imgs/extra/unused.png", "PNG")
        self._write(
            "_config.yml",
            'title: Test\nfavicon_ico: "/imgs/favicon.ico"\nlogo: "imgs/logo.png"\n',
        )
        report = lint_wiki.lint_wiki(self.root)
        unused = self._findings(report, "unused-image")
        self.assertEqual([u.file for u in unused], ["imgs/extra/unused.png"])

    def test_nav_exclude_exempts_parent_requirement(self):
        self._write(
            "directory/hidden.md",
            "---\ntitle: Hidden Note\nnav_exclude: true\n---\n\nOne.\nTwo.\nThree.\n",
        )
        self._write(
            "directory/not_excluded.md",
            "---\ntitle: Visible Note\nnav_exclude: false\n---\n\nOne.\nTwo.\nThree.\n",
        )
        self._write_catalog(
            [
                "campaigns/arc/ep001.md",
                "directory/place.md",
                "directory/hidden.md",
                "directory/not_excluded.md",
            ]
        )
        report = lint_wiki.lint_wiki(self.root)
        fm = self._findings(report, "front-matter")
        self.assertEqual([f.file for f in fm], ["directory/not_excluded.md"])
        self.assertIn("parent", fm[0].message)


class TestRollingGlossary(LintWikiTestCase):
    """Tests for rolling glossary validation against published canon (#28)."""

    def test_missing_glossary_is_silent(self):
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rolling-glossary"), [])

    def test_entry_without_definition_fails(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## Kael Vorn\n\n- First seen: `2026-11-20_001`\n",
        )
        report = lint_wiki.lint_wiki(self.root)
        rg = self._findings(report, "rolling-glossary")
        self.assertTrue(any(f.severity == "FAIL" and "no definition" in f.message for f in rg))

    def test_canon_title_casing_conflict_fails(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## kael vorn\n\n- Definition: Protagonist.\n",
        )
        self._write(
            ".agents/context/catalog.json",
            json.dumps({"entries": [{"title": "Kael Vorn", "path": "directory/kael.md", "type": "people"}]}),
        )
        report = lint_wiki.lint_wiki(self.root)
        rg = self._findings(report, "rolling-glossary")
        self.assertTrue(any("conflicts with published canon" in f.message for f in rg))

    def test_matching_canon_title_passes(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## Kael Vorn\n\n- Definition: Protagonist.\n- First seen: `2026-11-20_001`\n",
        )
        self._write(
            ".agents/context/catalog.json",
            json.dumps({"entries": [{"title": "Kael Vorn", "path": "directory/kael.md", "type": "people"}]}),
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rolling-glossary"), [])

    def test_pending_definition_is_warn_not_fail(self):
        # Issue #103: default placeholder from scribe_session must warn, not fail Gate 3.
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## Monarch\n\n- Definition: Pending canonical definition.\n- First seen: `2026-11-21_001`\n",
        )
        report = lint_wiki.lint_wiki(self.root)
        rg = self._findings(report, "rolling-glossary")
        self.assertEqual(len(rg), 1)
        self.assertEqual(rg[0].severity, "WARN")
        self.assertIn("pending", rg[0].message)
        self.assertFalse(report.has_failures())

        rc, out = self._run_main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertIn("- 1 rolling-glossary", out)
        self.assertIn("## Rolling Glossary", out)

        rc_strict, _ = self._run_main(["--root", str(self.root), "--strict"])
        self.assertEqual(rc_strict, 1)

    def test_blank_definition_line_still_fails(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## Monarch\n\n- Definition:   \n- First seen: `2026-11-21_001`\n",
        )
        report = lint_wiki.lint_wiki(self.root)
        rg = self._findings(report, "rolling-glossary")
        self.assertEqual(len(rg), 1)
        self.assertEqual(rg[0].severity, "FAIL")
        self.assertIn("no definition", rg[0].message)

    def test_canon_title_casing_conflict_with_pending_definition_still_fails(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## kael vorn\n\n- Definition: Pending canonical definition.\n",
        )
        self._write(
            ".agents/context/catalog.json",
            json.dumps({"entries": [{"title": "Kael Vorn", "path": "directory/kael.md", "type": "people"}]}),
        )
        report = lint_wiki.lint_wiki(self.root)
        rg = self._findings(report, "rolling-glossary")
        severities = {f.severity for f in rg}
        self.assertEqual(severities, {"WARN", "FAIL"})
        self.assertTrue(report.has_failures())

    def test_scribe_session_to_lint_wiki_rolling_glossary_round_trip(self):
        terms = scribe_session.session_glossary_terms(
            "Monarch met Kael Vorn at Fomalhaut Station.", skip_titles={"kael vorn"}
        )
        self.assertTrue(terms)
        scribe_session.update_rolling_glossary(
            self.root, "2026-11-21_001", terms, skip_titles={"kael vorn"}
        )
        rc, out = self._run_main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertIn("rolling-glossary", out)

        # Filling in definitions clears all rolling-glossary warnings
        defined_terms = [(term, f"Canonical note for {term}.") for term, _ in terms]
        scribe_session.update_rolling_glossary(
            self.root, "2026-11-21_002", defined_terms, skip_titles={"kael vorn"}
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rolling-glossary"), [])

    def test_render_text_report_includes_rolling_glossary_and_unexpected_checks(self):
        # Issue #102: text report renders rolling-glossary FAILs/WARNs and unexpected checks.
        report = lint_wiki.WikiReport(
            root=str(self.root),
            mode="full",
            files_scanned=2,
            findings=[
                lint_wiki.Finding(
                    check="rolling-glossary",
                    severity="FAIL",
                    file=".agents/context/rolling_glossary.md",
                    line=3,
                    message="rolling glossary entry 'Bad' has no definition line",
                ),
                lint_wiki.Finding(
                    check="custom-check",
                    severity="WARN",
                    file="directory/place.md",
                    line=1,
                    message="unexpected future diagnostic",
                ),
            ],
        )
        rendered = lint_wiki.render_text_report(report)
        self.assertIn("- 1 rolling-glossary", rendered)
        self.assertIn("## Rolling Glossary", rendered)
        self.assertIn("rolling glossary entry 'Bad' has no definition line", rendered)
        self.assertIn("- 1 custom-check", rendered)
        self.assertIn("## Custom Check", rendered)
        self.assertIn("unexpected future diagnostic", rendered)

    def test_targeted_mode_skips_rolling_glossary_unless_explicitly_targeted(self):
        self._write(
            ".agents/context/rolling_glossary.md",
            "# Rolling Campaign Glossary\n\n## Broken\n\n- First seen: `2026-11-21_001`\n",
        )
        regular = lint_wiki.lint_wiki(self.root, paths=["campaigns/arc/ep001.md"])
        self.assertIn("rolling-glossary", regular.checks_skipped)
        self.assertEqual(self._findings(regular, "rolling-glossary"), [])
        self.assertFalse(regular.has_failures())

        # Directory scan at root skips .agents/ so rolling_glossary is not accidentally swept in.
        dot_scan = lint_wiki.lint_wiki(self.root, paths=["."])
        self.assertIn("rolling-glossary", dot_scan.checks_skipped)
        self.assertEqual(self._findings(dot_scan, "rolling-glossary"), [])

        # Minimal explicitly targeted glossary must NOT emit a spurious stub warning.
        self._write(
            ".agents/context/rolling_glossary.md",
            "## Broken\n",
        )
        explicit = lint_wiki.lint_wiki(
            self.root, paths=[".agents/context/rolling_glossary.md"]
        )
        self.assertNotIn("rolling-glossary", explicit.checks_skipped)
        self.assertEqual(self._findings(explicit, "stub"), [])
        rg = self._findings(explicit, "rolling-glossary")
        self.assertEqual(len(rg), 1)
        self.assertEqual(rg[0].severity, "FAIL")

    def test_load_tier1_config_honours_empty_exclude_paths_and_normalises_rel_paths(self):
        self._write(
            ".agents/context/tier1_sources.yml",
            "include_paths:\n  - ././campaigns/\n  - .\nexclude_paths: []\n",
        )
        # Root _TODO.md is excluded by DEFAULT_EXCLUDE_PATHS, so retaining it proves exclude_paths: [] works.
        self._write("_TODO.md", note_content("Root Scratch"))
        self._write("campaigns/_TODO.md", note_content("Scratch Notes"))
        include_paths, exclude_paths = lint_wiki.load_tier1_config(self.root)
        self.assertEqual(include_paths, ["campaigns", "."])
        self.assertEqual(exclude_paths, [])
        files = lint_wiki.iter_content_files(self.root, include_paths, exclude_paths)
        rels = {f.relative_to(self.root).as_posix() for f in files}
        self.assertIn("_TODO.md", rels)
        self.assertIn("campaigns/_TODO.md", rels)

    def test_config_helpers_delegate_to_tier2_single_owner(self):
        self.assertIs(lint_wiki.load_tier1_config, tier2.load_tier1_config)
        self.assertIs(lint_wiki.is_excluded, tier2.is_excluded)
        self.assertIs(lint_wiki.FRONT_MATTER_RE, tier2.FRONT_MATTER_RE)
        # Dead aliases removed in the round-2 review: lint_wiki must not re-expose them.
        self.assertFalse(hasattr(lint_wiki, "normalise_rel_path"))
        self.assertFalse(hasattr(lint_wiki, "DEFAULT_INCLUDE_PATHS"))
        self.assertFalse(hasattr(lint_wiki, "DEFAULT_EXCLUDE_PATHS"))
        # Single fallback convention: corrupt YAML warns on stderr and falls back to defaults.
        self._write(".agents/context/tier1_sources.yml", "include_paths: [unclosed\n")
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            include, exclude = lint_wiki.load_tier1_config(self.root)
        self.assertEqual(include, tier2.DEFAULT_INCLUDE_PATHS)
        self.assertEqual(exclude, tier2.DEFAULT_EXCLUDE_PATHS)
        self.assertIn("Warning", err.getvalue())

    def test_targeted_scan_resolves_parent_traversal_symlinks_and_skips_md_dirs(self):
        # Parent traversal ('campaigns/..') and symlinks must still enforce skipped/excluded rules.
        self._write("_TODO.md", note_content("Ignored").replace("Prose sentence number 1.", "See [x](nope.md)."))
        self._write(
            "_gm-materials/digests/secret.md",
            note_content("Secret").replace("Prose sentence number 1.", "See [x](nope.md)."),
        )
        self._write(
            ".agents/context/rolling_glossary.md",
            "## Broken\n",
        )
        (self.root / "campaigns" / "subdir.md").mkdir()  # directory ending in .md must not crash

        traversal = lint_wiki.lint_wiki(self.root, paths=["campaigns/.."])
        self.assertIn("rolling-glossary", traversal.checks_skipped)
        self.assertEqual(self._findings(traversal, "dead-link"), [])
        self.assertEqual(self._findings(traversal, "rolling-glossary"), [])

        # Symlinked alias to the vault root must also enforce skipped segments and exclusions.
        alias_dir = Path(self.temp_dir.name) / "vault_alias"
        alias_dir.symlink_to(self.root)
        aliased = lint_wiki.lint_wiki(self.root, paths=[str(alias_dir)])
        self.assertIn("rolling-glossary", aliased.checks_skipped)
        self.assertEqual(self._findings(aliased, "dead-link"), [])
        self.assertEqual(self._findings(aliased, "rolling-glossary"), [])

    def test_front_matter_eof_without_trailing_newline_and_crlf_link_offsets(self):
        fm, body, fm_lines = lint_wiki.parse_front_matter("---\ntitle: EOF Only\n---")
        self.assertEqual(fm.get("title"), "EOF Only")
        self.assertEqual(body, "")
        self.assertEqual(fm_lines, 2)

        crlf_note = "---\r\ntitle: CRLF Note\r\nparent: Index\r\n---\r\n\r\nSee [x](missing.md).\r\n"
        links = lint_wiki.extract_links(crlf_note)
        self.assertEqual(links, [(6, "missing.md", False)])



def ruling_file_text(fm: dict, body: str = "Narrative body.\n") -> str:
    """Serialise a ruling front-matter dict into Markdown file text."""
    return "---\n" + yaml.safe_dump(fm, sort_keys=False) + "---\n\n" + body


class TestDuplicateIds(LintWikiTestCase):
    """Tier 1 optional `id:` grammar (front-matter) and uniqueness (duplicate-id)."""

    def test_optional_id_omitted_is_clean(self):
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "duplicate-id"), [])
        self.assertEqual([f for f in self._findings(report, "front-matter") if "'id'" in f.message], [])

    def test_valid_id_passes_full_scan(self):
        self._write("directory/alpha.md", note_content("Alpha", extra_fm="id: alpha"))
        self._write_catalog(["campaigns/arc/ep001.md", "directory/place.md", "directory/alpha.md"])
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "duplicate-id"), [])
        self.assertEqual([f for f in self._findings(report, "front-matter") if "'id'" in f.message], [])

    def test_invalid_id_grammar_is_front_matter_fail(self):
        self._write("directory/bad.md", note_content("Bad", extra_fm="id: Bad Slug!"))
        report = lint_wiki.lint_wiki(self.root)
        fm = [f for f in self._findings(report, "front-matter") if "'id'" in f.message]
        self.assertEqual(len(fm), 1)
        self.assertEqual(fm[0].severity, "FAIL")
        self.assertIn("Bad Slug!", fm[0].message)

    def test_duplicate_id_is_fail_listing_all_paths(self):
        self._write("directory/alpha.md", note_content("Alpha One", extra_fm="id: alpha"))
        self._write("directory/beta.md", note_content("Beta", extra_fm="id: alpha"))
        report = lint_wiki.lint_wiki(self.root)
        dups = self._findings(report, "duplicate-id")
        self.assertEqual(len(dups), 1)
        self.assertEqual(dups[0].severity, "FAIL")
        self.assertIn("directory/alpha.md", dups[0].file)
        self.assertIn("directory/beta.md", dups[0].file)

    def test_targeted_mode_validates_grammar_but_skips_duplicate_check(self):
        self._write("directory/alpha.md", note_content("Alpha One", extra_fm="id: alpha"))
        self._write("directory/beta.md", note_content("Beta", extra_fm="id: alpha"))
        report = lint_wiki.lint_wiki(self.root, paths=["directory/alpha.md", "directory/beta.md"])
        self.assertEqual(self._findings(report, "duplicate-id"), [])
        self.assertIn("duplicate-id", report.checks_skipped)
        # Grammar is still validated in targeted mode.
        self._write("directory/bad.md", note_content("Bad", extra_fm="id: NOPE"))
        report2 = lint_wiki.lint_wiki(self.root, paths=["directory/bad.md"])
        self.assertTrue(any("'id'" in f.message for f in self._findings(report2, "front-matter")))


class TestRulings(LintWikiTestCase):
    """check_rulings() integration (Design 006): validation, cache freshness, targeted mode."""

    def _write_ruling(self, fm: dict = None, filename: str = None, raw: str = None) -> Path:
        fm = fm or {
            "id": "R-001",
            "title": "Test Ruling",
            "date": "2026-11-01",
            "kind": "ruling",
            "status": "active",
            "fact": "The sky is red.",
            "entities": [],
        }
        text = raw if raw is not None else ruling_file_text(fm)
        rel = filename or f"{fm.get('id', 'R-000')}_slug.md"
        return self._write(f"_gm-materials/rulings/{rel}", text)

    def test_clean_skip_when_rulings_dir_absent(self):
        # Simulates public CI runners where _gm-materials/ is absent.
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rulings"), [])

    def test_clean_skip_when_rulings_dir_empty(self):
        (self.root / "_gm-materials" / "rulings").mkdir(parents=True)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rulings"), [])

    def test_empty_rulings_dir_with_legacy_decisions_warns(self):
        """M4: existing-but-empty rulings/ + legacy decisions.md still yields a rulings WARN."""
        (self.root / "_gm-materials" / "rulings").mkdir(parents=True)
        self._write(".agents/context/decisions.md", "- Decision: legacy\n")
        report = lint_wiki.lint_wiki(self.root)
        rulings = self._findings(report, "rulings")
        self.assertEqual(len(rulings), 1)
        self.assertEqual(rulings[0].severity, "WARN")
        self.assertIn("decisions.md", rulings[0].message)

    def test_absent_cache_is_warn_not_fail(self):
        self._write_ruling()
        report = lint_wiki.lint_wiki(self.root)
        rulings = self._findings(report, "rulings")
        self.assertEqual(len(rulings), 1)
        self.assertEqual(rulings[0].severity, "WARN")
        self.assertIn("absent", rulings[0].message)
        self.assertFalse(report.has_failures())

    def test_fresh_cache_passes_clean(self):
        self._write_ruling()
        tier2.compile_tier2_index(self.root, write=True)
        report = lint_wiki.lint_wiki(self.root)
        self.assertEqual(self._findings(report, "rulings"), [])

    def test_corrupt_cache_is_fail(self):
        self._write_ruling()
        self._write("_gm-materials/.cache/tier2.json", "{corrupt")
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and "valid JSON" in f.message for f in self._findings(report, "rulings")))

    def test_unknown_schema_version_is_fail(self):
        self._write_ruling()
        self._write("_gm-materials/.cache/tier2.json", json.dumps({"schema_version": 99, "entries": []}))
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and "schema_version" in f.message for f in self._findings(report, "rulings")))

    def test_ruling_sha_drift_is_stale_fail(self):
        path = self._write_ruling()
        tier2.compile_tier2_index(self.root, write=True)
        path.write_text(path.read_text(encoding="utf-8") + "\nExtra narrative line.\n", encoding="utf-8")
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and "stale" in f.message for f in self._findings(report, "rulings")))

    def test_extra_on_disk_ruling_is_stale_fail(self):
        self._write_ruling()
        tier2.compile_tier2_index(self.root, write=True)
        self._write_ruling(fm={"id": "R-002", "title": "Second", "date": "2026-11-02", "kind": "ruling",
                               "status": "active", "fact": "Two.", "entities": []})
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and "stale" in f.message for f in self._findings(report, "rulings")))

    def test_catalog_sha_drift_is_stale_fail(self):
        self._write_ruling()
        tier2.compile_tier2_index(self.root, write=True)
        self._write(".agents/context/catalog.json", json.dumps({"entries": [{"path": "x.md", "id": "x_note"}]}))
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and "stale" in f.message for f in self._findings(report, "rulings")))

    def test_volatile_catalog_rewrite_is_not_stale(self):
        self._write_ruling()
        self._write(
            ".agents/context/catalog.json",
            json.dumps({
                "generated": "2026-11-25T10:00:00+00:00",
                "engine_version": "0.9.1",
                "entries": [
                    {"path": "directory/place.md", "id": "the_place", "title": "The Place", "sha": "aaaa1111"},
                    {"path": "campaigns/arc/ep001.md", "id": None, "title": "Episode 001", "sha": "bbbb2222"},
                ],
            }),
        )
        tier2.compile_tier2_index(self.root, write=True)
        # Volatile-only rewrite: new stamps, changed per-entry sha, renamed title,
        # and an extra null-id entry — the id→path projection is unchanged.
        self._write(
            ".agents/context/catalog.json",
            json.dumps({
                "generated": "2026-11-26T12:00:00+00:00",
                "engine_version": "0.9.2",
                "entries": [
                    {"path": "directory/place.md", "id": "the_place", "title": "The Place (renamed)", "sha": "cccc3333"},
                    {"path": "campaigns/arc/ep001.md", "id": None, "title": "Episode 001", "sha": "dddd4444"},
                    {"path": ".agents/context/rolling_glossary.md", "id": None, "title": "Rolling Glossary", "sha": "eeee5555"},
                ],
            }),
        )
        report = lint_wiki.lint_wiki(self.root)
        self.assertFalse(
            any(f.severity == "FAIL" and "stale" in f.message for f in self._findings(report, "rulings"))
        )

    def test_invalid_ruling_is_fail_under_rulings_check(self):
        self._write_ruling(raw="---\nid: R-1\ntitle: T\n---\n\nBody.\n")
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "FAIL" and f.check == "rulings" for f in report.findings))
        self.assertTrue(report.has_failures())

    def test_legacy_decisions_coexistence_is_warn(self):
        self._write_ruling()
        self._write(".agents/context/decisions.md", "- Decision: legacy\n")
        report = lint_wiki.lint_wiki(self.root)
        self.assertTrue(any(f.severity == "WARN" and "decisions.md" in f.message for f in self._findings(report, "rulings")))

    def test_targeted_rulings_dir_runs_check_rulings(self):
        self._write_ruling()
        report = lint_wiki.lint_wiki(self.root, paths=["_gm-materials/rulings"])
        self.assertEqual(report.mode, "targeted")
        self.assertNotIn("rulings", report.checks_skipped)
        self.assertNotIn("duplicate-id", report.checks_skipped)
        self.assertEqual(report.files_scanned, 1)
        # Ruling files are scanned but kept out of Tier 1 file-level checks.
        self.assertEqual(self._findings(report, "stub"), [])
        self.assertTrue(any("absent" in f.message for f in self._findings(report, "rulings")))

    def test_targeted_single_ruling_file_runs_check_rulings(self):
        self._write_ruling()
        report = lint_wiki.lint_wiki(self.root, paths=["_gm-materials/rulings/R-001_slug.md"])
        self.assertNotIn("rulings", report.checks_skipped)
        self.assertTrue(self._findings(report, "rulings"))

    def test_targeted_non_rulings_path_skips_rulings_and_duplicate_id(self):
        self._write_ruling()
        report = lint_wiki.lint_wiki(self.root, paths=["campaigns/arc/ep001.md"])
        self.assertIn("rulings", report.checks_skipped)
        self.assertIn("duplicate-id", report.checks_skipped)
        self.assertEqual(self._findings(report, "rulings"), [])

    def test_report_order_includes_duplicate_id_and_rulings(self):
        report = lint_wiki.WikiReport(
            root=str(self.root),
            mode="full",
            files_scanned=0,
            findings=[
                lint_wiki.Finding(check="rulings", severity="WARN", file="x", message="r"),
                lint_wiki.Finding(check="duplicate-id", severity="FAIL", file="y", message="d"),
            ],
        )
        rendered = lint_wiki.render_text_report(report)
        self.assertIn("- 1 duplicate-id", rendered)
        self.assertIn("- 1 rulings", rendered)
        self.assertLess(rendered.index("duplicate-id"), rendered.index("## Rulings"))

if __name__ == "__main__":
    unittest.main()
