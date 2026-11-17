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

# Ensure repo root is on sys.path
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import lint_wiki


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


class TestUnusedImages(LintWikiTestCase):
    def test_unused_badge_is_warn_and_gallery_exempt(self):
        self._write("imgs/badges/unused.png", "PNG")
        self._write("imgs/gallery/hero.png", "PNG")
        self._write("imgs/badges/used.png", "PNG")
        ep = (self.root / "campaigns/arc/ep001.md").read_text(encoding="utf-8")
        self._write(
            "campaigns/arc/ep001.md",
            ep.replace("Prose sentence number 4.", "Prose sentence number 4.\n![badge](../imgs/badges/used.png)"),
        )
        report = lint_wiki.lint_wiki(self.root)
        unused = self._findings(report, "unused-image")
        self.assertEqual([u.file for u in unused], ["imgs/badges/unused.png"])

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
    def test_missing_catalog_is_fail(self):
        (self.root / ".agents/context/catalog.json").unlink()
        report = lint_wiki.lint_wiki(self.root)
        cat = self._findings(report, "catalogue")
        self.assertTrue(any(c.severity == "FAIL" and "missing" in c.message for c in cat))

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


if __name__ == "__main__":
    unittest.main()
