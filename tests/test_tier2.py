#!/usr/bin/env python3
"""Unit tests for scripts/tier2.py (Design 006 — Tier 2 rulings compiler & validator).

Covers the full validator/compiler surface:
1. Valid `ruling` and `faction-turn` compilation into `_gm-materials/.cache/tier2.json`
   with `schema_version: 1` and `catalog_sha`, and `opinions` prose omitted from the index.
2. Idempotent write skip, atomic write safety (no corrupt cache on FAIL), and
   absent/empty `_gm-materials/rulings/` exiting 0 without creating anything.
3. Compile-time left-join against `catalog.json` (`resolved_entities`, null-id entries ignored).
4. Active-entity overlap advisories, unresolved-slug WARNs, filename prefix WARN.
5. Supersession DAG invariants (self-loops, 2/3-node cycles, dangling targets, invalid
   promoted/retracted targets, orphaned superseded rulings, forked active successors).
6. Status-to-partner-field matrix and strict `opinions` validation.
7. `load_active_rulings_text()` direct parsing (ignoring stale cache), fail-loud
   ValueError on malformed rulings, >50 active-ruling WARN, legacy decisions.md fallback.

All test assertions and docstrings strictly adhere to British English.
"""

import hashlib
import io
import json
import contextlib
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import tier2  # noqa: E402


def make_ruling_text(fm: dict, body: str = "Narrative body of the ruling.\n") -> str:
    """Serialise a ruling front-matter dict into a Markdown file text."""
    fm_raw = yaml.safe_dump(fm, sort_keys=False).rstrip("\n")
    return f"---\n{fm_raw}\n---\n\n{body}"


class Tier2TestCase(unittest.TestCase):
    """Base class scaffolding a minimal campaign vault with a rulings directory."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        (self.root / "_gm-materials" / "rulings").mkdir(parents=True)
        (self.root / ".agents" / "context").mkdir(parents=True)
        (self.root / "campaigns").mkdir()
        (self.root / "directory").mkdir()
        (self.root / ".agents" / "context" / "tier1_sources.yml").write_text(
            "drive_dir: .\ninclude_paths:\n  - campaigns\n  - directory\n",
            encoding="utf-8",
        )
        (self.root / "directory" / "sigisfarne.md").write_text(
            "---\ntitle: Sigisfarne\nid: sigisfarne\n---\n\nA Tier 1 note.\n",
            encoding="utf-8",
        )
        (self.root / "campaigns" / "ep_014.md").write_text(
            "---\ntitle: Episode 14\n---\n\nA published chapter.\n",
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def base_fm(self, **overrides) -> dict:
        fm = {
            "id": "R-001",
            "title": "Test Ruling",
            "date": "2026-11-01",
            "kind": "ruling",
            "status": "active",
            "fact": "The sky is red.",
            "entities": ["sigisfarne"],
        }
        fm.update(overrides)
        return fm

    def write_ruling(self, fm: dict, body: str = "Narrative body.\n", filename: str = None,
                     raw_text: str = None) -> Path:
        text = raw_text if raw_text is not None else make_ruling_text(fm, body)
        name = filename or f"{fm.get('id', 'R-000')}_slug.md"
        path = self.root / "_gm-materials" / "rulings" / name
        path.write_text(text, encoding="utf-8")
        return path

    def write_catalog(self, entries: list) -> Path:
        path = self.root / ".agents" / "context" / "catalog.json"
        path.write_text(json.dumps({"engine_version": "0.9.1", "entries": entries}), encoding="utf-8")
        return path

    def catalog_with_sigisfarne(self) -> Path:
        return self.write_catalog([
            {"path": "directory/sigisfarne.md", "id": "sigisfarne", "title": "Sigisfarne"},
            {"path": "campaigns/ep_014.md", "id": None, "title": "Episode 14"},
        ])

    def fails(self, diagnostics) -> list:
        return [d for d in diagnostics if d.severity == "FAIL"]

    def warns(self, diagnostics) -> list:
        return [d for d in diagnostics if d.severity == "WARN"]

    def compile(self, write: bool = True):
        return tier2.compile_tier2_index(self.root, write=write)


class TestCompilation(Tier2TestCase):
    """Happy-path compilation into _gm-materials/.cache/tier2.json."""

    def test_valid_ruling_compiles_with_schema_and_catalog_sha(self):
        self.write_ruling(self.base_fm())
        catalog_path = self.catalog_with_sigisfarne()
        payload, diagnostics, overlaps = self.compile()
        self.assertEqual(self.fails(diagnostics), [])
        self.assertIsNotNone(payload)
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(
            payload["catalog_sha"],
            hashlib.sha256(catalog_path.read_bytes()).hexdigest()[:8],
        )
        self.assertEqual(len(payload["entries"]), 1)
        entry = payload["entries"][0]
        self.assertEqual(entry["id"], "R-001")
        self.assertEqual(entry["title"], "Test Ruling")
        self.assertEqual(entry["date"], "2026-11-01")
        self.assertEqual(entry["kind"], "ruling")
        self.assertEqual(entry["status"], "active")
        self.assertEqual(entry["fact"], "The sky is red.")
        self.assertEqual(entry["entities"], ["sigisfarne"])
        self.assertEqual(entry["actors"], [])
        self.assertEqual(entry["supersedes"], [])
        self.assertEqual(entry["superseded_by"], [])
        self.assertEqual(entry["resolved_entities"], {"sigisfarne": "directory/sigisfarne.md"})
        self.assertEqual(entry["path"], "_gm-materials/rulings/R-001_slug.md")
        self.assertEqual(entry["sha"], hashlib.sha256(
            (self.root / "_gm-materials" / "rulings" / "R-001_slug.md").read_bytes()
        ).hexdigest()[:8])
        cache = self.root / "_gm-materials" / ".cache" / "tier2.json"
        self.assertTrue(cache.is_file())
        on_disk = json.loads(cache.read_text(encoding="utf-8"))
        self.assertEqual(on_disk["schema_version"], 1)
        self.assertEqual(on_disk["catalog_sha"], payload["catalog_sha"])

    def test_faction_turn_compiles_and_omits_opinions_prose(self):
        fm = self.base_fm(
            id="R-004",
            kind="faction-turn",
            actors=["piot_chant", "iron_pot_6_body"],
            entities=["sigisfarne"],
            turn={"active_actor": "piot_chant", "trio_tier": "Obvious", "roll": 17},
            opinions=[
                {"actor": "piot_chant", "vote": 1, "shifted": True, "stance": "Push the tribute."},
                {"actor": "iron_pot_6_body", "vote": -1, "shifted": False, "stance": "Too risky."},
            ],
        )
        self.write_ruling(fm)
        self.catalog_with_sigisfarne()
        payload, diagnostics, _ = self.compile()
        self.assertEqual(self.fails(diagnostics), [])
        entry = payload["entries"][0]
        self.assertEqual(entry["kind"], "faction-turn")
        self.assertEqual(entry["actors"], ["piot_chant", "iron_pot_6_body"])
        self.assertNotIn("opinions", entry, "opinions prose must be omitted from the index")
        self.assertEqual(entry["resolved_entities"]["sigisfarne"], "directory/sigisfarne.md")
        self.assertIsNone(entry["resolved_entities"]["piot_chant"])
        warns = self.warns(diagnostics)
        self.assertTrue(any("piot_chant" in d.message and "unresolved" in d.message for d in warns))

    def test_idempotent_write_skips_unchanged_cache(self):
        self.write_ruling(self.base_fm())
        self.catalog_with_sigisfarne()
        payload, _, _ = self.compile()
        cache = self.root / "_gm-materials" / ".cache" / "tier2.json"
        first_bytes = cache.read_bytes()
        payload2, _, _ = self.compile()
        self.assertEqual(cache.read_bytes(), first_bytes, "unchanged content must not be rewritten")
        self.assertIsNotNone(payload2)

    def test_fail_does_not_write_or_corrupt_cache(self):
        self.write_ruling(self.base_fm())
        self.catalog_with_sigisfarne()
        self.compile()
        cache = self.root / "_gm-materials" / ".cache" / "tier2.json"
        good_bytes = cache.read_bytes()
        # Introduce an invalid ruling; recompilation must fail and leave the old cache intact.
        self.write_ruling(self.base_fm(id="R-002", title="", fact="x"))
        payload, diagnostics, _ = self.compile()
        self.assertIsNone(payload)
        self.assertTrue(self.fails(diagnostics))
        self.assertEqual(cache.read_bytes(), good_bytes, "FAIL must never corrupt the existing cache")

    def test_fail_on_fresh_vault_writes_no_cache(self):
        self.write_ruling(self.base_fm(id="R-1"))  # invalid id grammar
        payload, diagnostics, _ = self.compile()
        self.assertIsNone(payload)
        self.assertTrue(self.fails(diagnostics))
        self.assertFalse((self.root / "_gm-materials" / ".cache" / "tier2.json").exists())

    def test_absent_or_empty_rulings_dir_exits_zero_without_creating_cache(self):
        # Empty rulings directory.
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = tier2.main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "_gm-materials" / ".cache").exists())
        # Absent rulings directory entirely.
        import shutil
        shutil.rmtree(self.root / "_gm-materials" / "rulings")
        with contextlib.redirect_stdout(buf):
            rc = tier2.main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        self.assertFalse((self.root / "_gm-materials" / ".cache").exists())

    def test_main_bad_root_returns_two(self):
        with contextlib.redirect_stderr(io.StringIO()):
            rc = tier2.main(["--root", str(self.root / "does-not-exist")])
        self.assertEqual(rc, 2)

    def test_main_prints_overlap_advisories_and_warns(self):
        self.write_ruling(self.base_fm(id="R-001", title="First"))
        self.write_ruling(self.base_fm(id="R-002", title="Second"))
        self.catalog_with_sigisfarne()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = tier2.main(["--root", str(self.root)])
        self.assertEqual(rc, 0)
        out = buf.getvalue()
        self.assertIn("overlap", out)
        self.assertIn("sigisfarne", out)
        self.assertIn("R-001", out)
        self.assertIn("R-002", out)

    def test_left_join_ignores_null_id_catalog_entries(self):
        # A catalog entry without id must not resolve any slug.
        self.write_ruling(self.base_fm(entities=["ep_014"]))
        self.write_catalog([{"path": "campaigns/ep_014.md", "id": None, "title": "Episode 14"}])
        payload, diagnostics, _ = self.compile()
        self.assertEqual(self.fails(diagnostics), [])
        entry = payload["entries"][0]
        self.assertIsNone(entry["resolved_entities"]["ep_014"])
        self.assertTrue(any("ep_014" in d.message for d in self.warns(diagnostics)))
        # catalog.json absent entirely -> catalog_sha null, everything unresolved.
        (self.root / ".agents" / "context" / "catalog.json").unlink()
        payload2, _, _ = self.compile(write=False)
        self.assertIsNone(payload2["catalog_sha"])
        self.assertIsNone(payload2["entries"][0]["resolved_entities"]["ep_014"])

    def test_find_active_entity_overlaps_only_active_and_entities(self):
        r1 = self.write_ruling(self.base_fm(id="R-001"))
        r2 = self.write_ruling(self.base_fm(id="R-002"))
        self.write_ruling(self.base_fm(id="R-003", status="superseded", entities=["sigisfarne"]))
        rulings, _, _, diagnostics = tier2.validate_rulings(self.root)
        # R-003 is orphaned-superseded -> FAIL expected here; filter to active for overlap check.
        overlaps = tier2.find_active_entity_overlaps([r for r in rulings if r.status == "active"])
        self.assertIn("sigisfarne", overlaps)
        self.assertEqual(sorted(r.id for r in overlaps["sigisfarne"]), ["R-001", "R-002"])
        self.assertTrue(self.fails(diagnostics), "orphaned superseded ruling must FAIL")

    def test_filename_prefix_mismatch_warns(self):
        self.write_ruling(self.base_fm(id="R-007"), filename="renamed_note.md")
        _, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])
        self.assertTrue(any("R-007_" in d.message for d in self.warns(diagnostics)))


class TestSchemaValidation(Tier2TestCase):
    """Front-matter schema validation (Component 2)."""

    def assert_single_fail(self, fm=None, raw_text=None, fragment=""):
        if raw_text is not None:
            self.write_ruling({}, raw_text=raw_text)
        else:
            self.write_ruling(fm if fm is not None else self.base_fm())
        _, diagnostics, _ = self.compile(write=False)
        fails = self.fails(diagnostics)
        self.assertTrue(fails, "expected at least one FAIL diagnostic")
        if fragment:
            self.assertTrue(any(fragment in d.message for d in fails), f"no FAIL mentions {fragment!r}: {[d.message for d in fails]}")
        return fails

    def test_authored_superseded_by_rejected(self):
        fm = self.base_fm()
        fm["superseded_by"] = ["R-000"]
        self.assert_single_fail(fm=fm, fragment="superseded_by")

    def test_missing_front_matter_fails(self):
        self.assert_single_fail(raw_text="# No front matter\n\nBody.\n", fragment="front matter")

    def test_invalid_yaml_fails(self):
        self.assert_single_fail(raw_text="---\nid: [unclosed\n---\n\nBody.\n", fragment="YAML")

    def test_non_mapping_front_matter_fails(self):
        self.assert_single_fail(raw_text="---\n- just\n- a\n- list\n---\n\nBody.\n", fragment="mapping")

    def test_field_grammar_failures(self):
        cases = [
            ({"id": "R-1"}, "id"),
            ({"id": "r-001"}, "id"),
            ({"title": ""}, "title"),
            ({"date": "2026-13-45"}, "date"),
            ({"date": "not-a-date"}, "date"),
            ({"kind": "edict"}, "kind"),
            ({"status": "pending"}, "status"),
            ({"fact": "  "}, "fact"),
            ({"entities": ["Bad Slug"]}, "entities"),
            ({"entities": "sigisfarne"}, "entities"),
            ({"actors": ["UPPER"]}, "actors"),
            ({"supersedes": ["R-1"]}, "supersedes"),
            ({"promoted_to": 42}, "promoted_to"),
            ({"retraction_reason": ""}, "retraction_reason"),
            ({"turn": "not-a-map"}, "turn"),
            ({"opinions": "not-a-list"}, "opinions"),
        ]
        for overrides, fragment in cases:
            with self.subTest(fragment=fragment, overrides=overrides):
                # fresh vault per case
                self.tearDown()
                self.setUp()
                self.assert_single_fail(fm=self.base_fm(**overrides), fragment=fragment)

    def test_datetime_date_rejected_but_date_object_accepted(self):
        self.assert_single_fail(
            raw_text="---\nid: R-001\ntitle: T\ndate: 2026-11-01 10:30:00\nkind: ruling\nstatus: active\nfact: F.\nentities: []\n---\n\nB.\n",
            fragment="date",
        )
        self.tearDown()
        self.setUp()
        # Unquoted ISO date parses as datetime.date and is normalised to an ISO string.
        self.write_ruling({}, raw_text="---\nid: R-001\ntitle: T\ndate: 2026-11-01\nkind: ruling\nstatus: active\nfact: F.\nentities: []\n---\n\nB.\n")
        payload, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])
        self.assertEqual(payload["entries"][0]["date"], "2026-11-01")

    def test_in_world_date_stringified_when_date(self):
        self.write_ruling({}, raw_text=(
            "---\nid: R-001\ntitle: T\ndate: 2026-11-01\nin_world_date: 1025-12-01\n"
            "kind: ruling\nstatus: active\nfact: F.\nentities: []\n---\n\nB.\n"
        ))
        payload, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])
        self.assertEqual(payload["entries"][0]["in_world_date"], "1025-12-01")

    def test_faction_turn_requires_actors_and_opinions(self):
        fm = self.base_fm(id="R-010", kind="faction-turn", actors=[], opinions=[])
        fails = self.assert_single_fail(fm=fm)
        messages = " | ".join(d.message for d in fails)
        self.assertIn("actors", messages)
        self.assertIn("opinions", messages)

    def test_opinions_item_validation(self):
        base_op = {"actor": "piot_chant", "vote": 1, "shifted": True, "stance": "Go."}
        cases = [
            ({**base_op, "actor": "other_actor"}, "actors"),        # actor not listed in actors
            ({**base_op, "vote": True}, "vote"),                    # bool rejected as vote
            ({**base_op, "vote": 2}, "vote"),                       # out of range
            ({**base_op, "vote": "1"}, "vote"),                     # non-int
            ({**base_op, "shifted": "yes"}, "shifted"),             # non-bool
            ({**base_op, "stance": ""}, "stance"),                  # empty stance
        ]
        for bad_op, fragment in cases:
            with self.subTest(fragment=fragment, op=bad_op):
                self.tearDown()
                self.setUp()
                fm = self.base_fm(
                    id="R-011",
                    kind="faction-turn",
                    actors=["piot_chant"],
                    opinions=[bad_op],
                )
                self.assert_single_fail(fm=fm, fragment=fragment)

    def test_optional_opinions_on_plain_ruling(self):
        fm = self.base_fm(opinions=[{"actor": "sigisfarne", "vote": 0, "shifted": False, "stance": "Meh."}])
        # actors defaults to [] for a ruling, so the opinion actor is not listed -> FAIL
        self.assert_single_fail(fm=fm, fragment="actors")
        self.tearDown()
        self.setUp()
        fm = self.base_fm(
            actors=["sigisfarne"],
            opinions=[{"actor": "sigisfarne", "vote": 0, "shifted": False, "stance": "Meh."}],
        )
        payload, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])
        self.assertNotIn("opinions", payload["entries"][0])

    def test_duplicate_ruling_ids_fail(self):
        self.write_ruling(self.base_fm(id="R-001"), filename="R-001_a.md")
        self.write_ruling(self.base_fm(id="R-001", title="Other"), filename="R-001_b.md")
        _, diagnostics, _ = self.compile(write=False)
        fails = self.fails(diagnostics)
        self.assertTrue(any("duplicate ruling id 'R-001'" in d.message for d in fails))


class TestSupersessionDAG(Tier2TestCase):
    """Supersession state machine & DAG invariants (Component 3)."""

    def test_valid_chain_compiles_and_derives_superseded_by(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", entities=[]))
        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
        payload, diagnostics, _ = self.compile()
        self.assertEqual(self.fails(diagnostics), [])
        by_id = {e["id"]: e for e in payload["entries"]}
        self.assertEqual(by_id["R-001"]["superseded_by"], ["R-002"])
        self.assertEqual(by_id["R-002"]["superseded_by"], [])
        self.assertEqual(by_id["R-002"]["supersedes"], ["R-001"])

    def test_self_loop_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", supersedes=["R-001"]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("self" in d.message.lower() for d in self.fails(diagnostics)))

    def test_two_node_cycle_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", supersedes=["R-002"], entities=[]))
        self.write_ruling(self.base_fm(id="R-002", status="superseded", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("cycle" in d.message for d in self.fails(diagnostics)))

    def test_three_node_cycle_rejected_with_path(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", supersedes=["R-002"], entities=[]))
        self.write_ruling(self.base_fm(id="R-002", status="superseded", supersedes=["R-003"], entities=[]))
        self.write_ruling(self.base_fm(id="R-003", status="superseded", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        cycle_fails = [d for d in self.fails(diagnostics) if "cycle" in d.message]
        self.assertTrue(cycle_fails)
        self.assertTrue(any("R-001" in d.message and "R-003" in d.message for d in cycle_fails))

    def test_dangling_target_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", supersedes=["R-999"]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("R-999" in d.message and "not exist" in d.message.lower() for d in self.fails(diagnostics)))

    def test_active_target_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", status="active", entities=[]))
        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("superseded" in d.message for d in self.fails(diagnostics)))

    def test_promoted_and_retracted_targets_rejected(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted", promoted_to="campaigns/ep_014.md", entities=[]))
        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("promoted" in d.message for d in self.fails(diagnostics)))

        self.tearDown()
        self.setUp()
        self.write_ruling(self.base_fm(
            id="R-001", status="retracted", retraction_reason="Wrong call.", entities=[]))
        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("retracted" in d.message for d in self.fails(diagnostics)))

    def test_orphaned_superseded_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("supersedes" in d.message for d in self.fails(diagnostics)))

    def test_forked_active_successor_rejected(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", entities=[]))
        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
        self.write_ruling(self.base_fm(id="R-003", supersedes=["R-001"], entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        fails = self.fails(diagnostics)
        self.assertTrue(any("R-002" in d.message and "R-003" in d.message for d in fails))


class TestStatusMatrix(Tier2TestCase):
    """Status-to-partner-field matrix (Component 3 rule 4)."""

    def test_promoted_valid(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted", promoted_to="campaigns/ep_014.md", entities=[]))
        payload, diagnostics, _ = self.compile()
        self.assertEqual(self.fails(diagnostics), [])
        self.assertEqual(payload["entries"][0]["promoted_to"], "campaigns/ep_014.md")

    def test_promoted_broken_path_rejected(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted", promoted_to="campaigns/missing.md", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("promoted_to" in d.message for d in self.fails(diagnostics)))

    def test_promoted_non_tier1_path_rejected(self):
        (self.root / "README.md").write_text("# Root readme\n", encoding="utf-8")
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted", promoted_to="README.md", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("promoted_to" in d.message or "include_paths" in d.message for d in self.fails(diagnostics)))

    def test_promoted_gm_materials_path_rejected(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted",
            promoted_to="_gm-materials/rulings/R-001_slug.md", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(self.fails(diagnostics))

    def test_promoted_may_retain_historical_supersedes(self):
        self.write_ruling(self.base_fm(id="R-001", status="superseded", entities=[]))
        self.write_ruling(self.base_fm(
            id="R-002", status="promoted", supersedes=["R-001"],
            promoted_to="campaigns/ep_014.md", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])

    def test_promoted_forbids_retraction_reason(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="promoted", promoted_to="campaigns/ep_014.md",
            retraction_reason="oops", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertTrue(any("retraction_reason" in d.message for d in self.fails(diagnostics)))

    def test_retracted_valid_and_invalid_variants(self):
        self.write_ruling(self.base_fm(
            id="R-001", status="retracted", retraction_reason="Withdrawn.", entities=[]))
        _, diagnostics, _ = self.compile(write=False)
        self.assertEqual(self.fails(diagnostics), [])

        for overrides, fragment in [
            ({"status": "retracted"}, "retraction_reason"),                       # missing reason
            ({"status": "retracted", "retraction_reason": "x", "promoted_to": "campaigns/ep_014.md"}, "promoted_to"),
            ({"status": "retracted", "retraction_reason": "x", "supersedes": ["R-001"]}, "supersedes"),
        ]:
            with self.subTest(overrides=overrides):
                self.tearDown()
                self.setUp()
                fm = self.base_fm(id="R-001", entities=[], **overrides)
                self.write_ruling(fm)
                _, diagnostics, _ = self.compile(write=False)
                self.assertTrue(any(fragment in d.message for d in self.fails(diagnostics)),
                                f"expected FAIL mentioning {fragment}")

    def test_active_and_superseded_forbid_partner_fields(self):
        for status in ("active", "superseded"):
            for overrides, fragment in [
                ({"promoted_to": "campaigns/ep_014.md"}, "promoted_to"),
                ({"retraction_reason": "why"}, "retraction_reason"),
            ]:
                with self.subTest(status=status, overrides=overrides):
                    self.tearDown()
                    self.setUp()
                    fm = self.base_fm(id="R-001", status=status, entities=[], **overrides)
                    if status == "superseded":
                        # needs a supersessor to avoid the orphan FAIL
                        self.write_ruling(self.base_fm(id="R-002", supersedes=["R-001"], entities=[]))
                    self.write_ruling(fm)
                    _, diagnostics, _ = self.compile(write=False)
                    self.assertTrue(any(fragment in d.message for d in self.fails(diagnostics)),
                                    f"expected FAIL mentioning {fragment} for status {status}")


class TestLoadActiveRulingsText(Tier2TestCase):
    """Shared active-rulings reader consumed by transcribe/scribe scripts."""

    def test_active_only_sorted_and_formatted(self):
        self.write_ruling(self.base_fm(id="R-002", title="Second", fact="Two.", entities=[]))
        self.write_ruling(self.base_fm(id="R-001", title="First", fact="One.", entities=[]))
        self.write_ruling(self.base_fm(id="R-003", status="superseded", entities=[]))
        self.write_ruling(self.base_fm(id="R-004", supersedes=["R-003"], entities=[]))
        self.write_ruling(self.base_fm(
            id="R-005", status="retracted", retraction_reason="No.", entities=[]))
        self.write_ruling(self.base_fm(
            id="R-006", status="promoted", promoted_to="campaigns/ep_014.md", entities=[]))
        text = tier2.load_active_rulings_text(self.root)
        lines = text.splitlines()
        self.assertEqual(lines, [
            "- **R-001 — First:** One.",
            "- **R-002 — Second:** Two.",
        ])

    def test_ignores_stale_cache(self):
        self.write_ruling(self.base_fm(id="R-001", title="Fresh", fact="From disk.", entities=[]))
        cache = self.root / "_gm-materials" / ".cache" / "tier2.json"
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"schema_version": 1, "entries": [
            {"id": "R-999", "title": "Stale", "status": "active", "fact": "Stale fact."}
        ]}), encoding="utf-8")
        text = tier2.load_active_rulings_text(self.root)
        self.assertIn("From disk.", text)
        self.assertNotIn("Stale fact.", text)

    def test_malformed_ruling_raises_value_error_with_stderr(self):
        self.write_ruling(self.base_fm(id="R-1"))  # invalid id
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            with self.assertRaises(ValueError):
                tier2.load_active_rulings_text(self.root)
        self.assertIn("FAIL", err.getvalue())

    def test_warn_above_threshold(self):
        for i in range(1, tier2.ACTIVE_RULINGS_WARN_THRESHOLD + 2):
            self.write_ruling(self.base_fm(id=f"R-{i:03d}", entities=[]))
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            text = tier2.load_active_rulings_text(self.root)
        self.assertIn("WARN", err.getvalue())
        self.assertEqual(len(text.splitlines()), tier2.ACTIVE_RULINGS_WARN_THRESHOLD + 1)

    def test_legacy_decisions_fallback_when_rulings_dir_absent(self):
        import shutil
        shutil.rmtree(self.root / "_gm-materials" / "rulings")
        decisions = self.root / ".agents" / "context" / "decisions.md"
        decisions.write_text("- Decision: Androids leak hydraulic fluid.\n", encoding="utf-8")
        text = tier2.load_active_rulings_text(self.root)
        self.assertIn("hydraulic fluid", text)
        # And with neither present, returns empty string.
        decisions.unlink()
        self.assertEqual(tier2.load_active_rulings_text(self.root), "")


class TestDiscoveryAndCatalog(Tier2TestCase):
    """Discovery and catalog-state helpers."""

    def test_discover_ignores_dotfiles_and_non_md(self):
        self.write_ruling(self.base_fm(id="R-001"))
        (self.root / "_gm-materials" / "rulings" / ".hidden.md").write_text("---\nid: R-009\n---\n", encoding="utf-8")
        (self.root / "_gm-materials" / "rulings" / "notes.txt").write_text("nope", encoding="utf-8")
        files = tier2.discover_ruling_files(self.root)
        self.assertEqual([f.name for f in files], ["R-001_slug.md"])

    def test_discover_missing_dir_returns_empty(self):
        import shutil
        shutil.rmtree(self.root / "_gm-materials" / "rulings")
        self.assertEqual(tier2.discover_ruling_files(self.root), [])

    def test_load_catalog_state_absent_and_unreadable(self):
        ids, sha = tier2.load_catalog_state(self.root)
        self.assertEqual(ids, {})
        self.assertIsNone(sha)
        (self.root / ".agents" / "context" / "catalog.json").write_text("{corrupt", encoding="utf-8")
        ids, sha = tier2.load_catalog_state(self.root)
        self.assertEqual((ids, sha), ({}, None))


if __name__ == "__main__":
    unittest.main()
