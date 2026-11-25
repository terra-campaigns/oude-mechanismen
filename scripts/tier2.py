#!/usr/bin/env python3
"""
scripts/tier2.py — Tier 2 rulings compiler, validator, and shared reader (`oude tier2`).

Compiles structured GM rulings and faction-turn records from
`_gm-materials/rulings/*.md` (YAML front matter + narrative body) into the
entries-only derived index `_gm-materials/.cache/tier2.json`
(`{schema_version, generated, catalog_sha, entries[]}`), validates the
supersession DAG, left-joins entity/actor slugs against
`.agents/context/catalog.json`, and exposes `load_active_rulings_text()` for
`scripts/transcribe_session.py` and `scripts/scribe_session.py`.

Usage:
  python3 scripts/tier2.py [--root PATH]     # compile + validate (oude tier2)

Exit code is 0 when the rulings directory is absent/empty or compilation
succeeds (advisories printed as plain text), 1 on any FAIL diagnostic, and 2
when --root is not a directory. All messages and docstrings strictly adhere
to British English.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

SCHEMA_VERSION = 1
ACTIVE_RULINGS_WARN_THRESHOLD = 50
RULING_ID_RE = re.compile(r"^R-[0-9]{3,}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
VALID_KINDS = frozenset({"ruling", "faction-turn"})
VALID_STATUSES = frozenset({"active", "superseded", "retracted", "promoted"})
RULINGS_REL_DIR = Path("_gm-materials") / "rulings"
CACHE_REL_PATH = Path("_gm-materials") / ".cache" / "tier2.json"
CATALOG_REL_PATH = Path(".agents") / "context" / "catalog.json"
LEGACY_DECISIONS_REL_PATH = Path(".agents") / "context" / "decisions.md"

# Defaults mirror jekyll/_plugins/data_extractor.rb so promoted_to resolution
# agrees with the Tier 1 catalogue on what constitutes published canon.
DEFAULT_INCLUDE_PATHS = ["campaigns", "directory", "systems", "statblocks", "trading"]

FRONT_MATTER_RE = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n(.*)|\Z)", re.DOTALL)
ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass
class Tier2Diagnostic:
    """A single validation diagnostic; severity is FAIL or WARN."""

    severity: str
    file: str
    line: int
    message: str


@dataclass
class ParsedRuling:
    """A fully validated ruling parsed from one _gm-materials/rulings/*.md file."""

    id: Optional[str]
    title: str
    date: Optional[str]
    in_world_date: Optional[str]
    kind: Optional[str]
    status: Optional[str]
    fact: str
    entities: List[str]
    actors: List[str]
    supersedes: List[str]
    promoted_to: Optional[str]
    retraction_reason: Optional[str]
    turn: Optional[Dict[str, Any]]
    opinions: List[Dict[str, Any]]
    rel_path: str
    sha: str


def discover_ruling_files(root: Path) -> List[Path]:
    """Return sorted *.md files directly inside root/_gm-materials/rulings/ (dot-files ignored)."""
    rulings_dir = root / RULINGS_REL_DIR
    if not rulings_dir.is_dir():
        return []
    return sorted(
        p
        for p in rulings_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".md" and not p.name.startswith(".")
    )


def _normalise_rel_path(raw: Any) -> str:
    """Normalise a vault-relative config path for prefix comparison."""
    cleaned = str(raw).strip().replace("\\", "/").rstrip("/")
    if cleaned == ".":
        return "."
    return re.sub(r"^(?:\./+)+", "", cleaned).lstrip("/")


def _load_include_paths(root: Path) -> List[str]:
    """Load include_paths from .agents/context/tier1_sources.yml (engine fallback when absent)."""
    config_path = root / ".agents" / "context" / "tier1_sources.yml"
    if not config_path.is_file():
        return list(DEFAULT_INCLUDE_PATHS)
    try:
        cfg = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return list(DEFAULT_INCLUDE_PATHS)
    if not isinstance(cfg, dict):
        return list(DEFAULT_INCLUDE_PATHS)
    raw = cfg.get("include_paths")
    if isinstance(raw, list):
        normalised = [n for p in raw if p is not None and (n := _normalise_rel_path(p))]
        if normalised:
            return normalised
    return list(DEFAULT_INCLUDE_PATHS)


def _valid_slug_list(value: Any) -> Optional[List[str]]:
    """Return the value when it is a list of valid slugs, else None."""
    if not isinstance(value, list):
        return None
    if any(not isinstance(item, str) or not SLUG_RE.match(item) for item in value):
        return None
    return list(value)


def parse_ruling_file(root: Path, path: Path) -> Tuple[Optional[ParsedRuling], List[Tier2Diagnostic]]:
    """Parse and schema-validate one ruling file; returns (ruling-or-None, diagnostics).

    The ruling is None when any FAIL-severity diagnostic was emitted (hard
    parse failures or invalid fields), so callers never act on partial data.
    """
    try:
        rel_path = path.relative_to(root).as_posix()
    except ValueError:
        rel_path = str(path)
    diagnostics: List[Tier2Diagnostic] = []

    def fail(message: str, line: int = 1) -> None:
        diagnostics.append(Tier2Diagnostic("FAIL", rel_path, line, message))

    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()[:8]
    text = raw.decode("utf-8", errors="replace")

    match = FRONT_MATTER_RE.match(text)
    if not match:
        return None, [Tier2Diagnostic("FAIL", rel_path, 1, "missing YAML front matter")]
    try:
        fm = yaml.safe_load(match.group(1))
    except yaml.YAMLError as exc:
        return None, [Tier2Diagnostic("FAIL", rel_path, 1, f"invalid YAML front matter: {exc}")]
    if not isinstance(fm, dict):
        return None, [Tier2Diagnostic("FAIL", rel_path, 1, "front matter must be a YAML mapping")]

    if "superseded_by" in fm:
        fail("authored 'superseded_by' is forbidden; it is derived at compile time from 'supersedes'")

    rid = fm.get("id")
    if not isinstance(rid, str) or not RULING_ID_RE.match(rid):
        fail(f"'id' must be a string matching {RULING_ID_RE.pattern} (e.g. R-004), got {rid!r}")
        rid = None

    title = fm.get("title")
    if not isinstance(title, str) or not title.strip():
        fail(f"'title' must be a non-empty string, got {title!r}")
        title = title if isinstance(title, str) else ""

    raw_date = fm.get("date")
    date_str: Optional[str] = None
    if isinstance(raw_date, datetime):
        fail(f"'date' must be an ISO date YYYY-MM-DD, not a datetime, got {raw_date!r}")
    elif isinstance(raw_date, date):
        date_str = raw_date.isoformat()
    elif isinstance(raw_date, str) and ISO_DATE_RE.match(raw_date):
        try:
            date_str = date.fromisoformat(raw_date).isoformat()
        except ValueError:
            fail(f"'date' is not a real calendar date: {raw_date!r}")
    else:
        fail(f"'date' must be an ISO date YYYY-MM-DD, got {raw_date!r}")

    in_world_date = fm.get("in_world_date")
    if isinstance(in_world_date, datetime):
        fail(f"'in_world_date' must be a string label or date, not a datetime, got {in_world_date!r}")
        in_world_date = None
    elif isinstance(in_world_date, date):
        in_world_date = in_world_date.isoformat()
    elif in_world_date is not None and not isinstance(in_world_date, str):
        fail(f"'in_world_date' must be a string, date, or null, got {in_world_date!r}")
        in_world_date = None

    kind = fm.get("kind")
    if not isinstance(kind, str) or kind not in VALID_KINDS:
        fail(f"'kind' must be one of {sorted(VALID_KINDS)}, got {kind!r}")
        kind = None

    status = fm.get("status")
    if not isinstance(status, str) or status not in VALID_STATUSES:
        fail(f"'status' must be one of {sorted(VALID_STATUSES)}, got {status!r}")
        status = None

    fact = fm.get("fact")
    if not isinstance(fact, str) or not fact.strip():
        fail(f"'fact' must be a non-empty string, got {fact!r}")
        fact = fact if isinstance(fact, str) else ""

    entities = _valid_slug_list(fm.get("entities"))
    if entities is None:
        fail(f"'entities' must be a list of slugs matching {SLUG_RE.pattern}, got {fm.get('entities')!r}")
        entities = []

    actors = _valid_slug_list(fm.get("actors")) if fm.get("actors") is not None else []
    if fm.get("actors") is not None and actors is None:
        fail(f"'actors' must be a list of slugs matching {SLUG_RE.pattern}, got {fm.get('actors')!r}")
        actors = []
    if kind == "faction-turn" and not actors:
        fail("'actors' must be a non-empty slug list when kind is 'faction-turn'")

    supersedes_raw = fm.get("supersedes")
    if supersedes_raw is None:
        supersedes: List[str] = []
    elif (
        isinstance(supersedes_raw, list)
        and all(isinstance(s, str) and RULING_ID_RE.match(s) for s in supersedes_raw)
    ):
        supersedes = list(supersedes_raw)
    else:
        fail(f"'supersedes' must be a list of ruling IDs matching {RULING_ID_RE.pattern}, got {supersedes_raw!r}")
        supersedes = []

    promoted_to = fm.get("promoted_to")
    if promoted_to is not None and (not isinstance(promoted_to, str) or not promoted_to.strip()):
        fail(f"'promoted_to' must be a non-empty vault-relative path string or null, got {promoted_to!r}")
        promoted_to = None

    retraction_reason = fm.get("retraction_reason")
    if retraction_reason is not None and (
        not isinstance(retraction_reason, str) or not retraction_reason.strip()
    ):
        fail(f"'retraction_reason' must be a non-empty string or null, got {retraction_reason!r}")
        retraction_reason = None

    turn = fm.get("turn")
    if turn is not None and not isinstance(turn, dict):
        fail(f"'turn' must be a mapping or null, got {turn!r}")
        turn = None

    opinions_raw = fm.get("opinions")
    opinions: List[Dict[str, Any]] = []
    if opinions_raw is None:
        if kind == "faction-turn":
            fail("'opinions' must be a non-empty list when kind is 'faction-turn'")
    elif not isinstance(opinions_raw, list) or not opinions_raw:
        fail(f"'opinions' must be a non-empty list when present, got {opinions_raw!r}")
    else:
        for idx, item in enumerate(opinions_raw):
            if not isinstance(item, dict):
                fail(f"opinions[{idx}] must be a mapping, got {item!r}")
                continue
            ok = True
            actor = item.get("actor")
            if not isinstance(actor, str) or not SLUG_RE.match(actor):
                fail(f"opinions[{idx}].actor must be a slug matching {SLUG_RE.pattern}, got {actor!r}")
                ok = False
            elif actor not in actors:
                fail(f"opinions[{idx}].actor '{actor}' is not listed in the ruling's 'actors'")
                ok = False
            vote = item.get("vote")
            if isinstance(vote, bool) or not isinstance(vote, int) or vote not in (-1, 0, 1):
                fail(f"opinions[{idx}].vote must be an integer in {{-1, 0, 1}}, got {vote!r}")
                ok = False
            shifted = item.get("shifted")
            if not isinstance(shifted, bool):
                fail(f"opinions[{idx}].shifted must be a boolean, got {shifted!r}")
                ok = False
            stance = item.get("stance")
            if not isinstance(stance, str) or not stance.strip():
                fail(f"opinions[{idx}].stance must be a non-empty string, got {stance!r}")
                ok = False
            if ok:
                opinions.append(dict(item))

    if rid is not None and not path.name.startswith(f"{rid}_"):
        diagnostics.append(
            Tier2Diagnostic("WARN", rel_path, 1, f"filename does not start with '{rid}_' (recommended '<id>_<slug>.md')")
        )

    if any(d.severity == "FAIL" for d in diagnostics):
        return None, diagnostics
    ruling = ParsedRuling(
        id=rid,
        title=title,
        date=date_str,
        in_world_date=in_world_date,
        kind=kind,
        status=status,
        fact=fact,
        entities=entities,
        actors=actors,
        supersedes=supersedes,
        promoted_to=promoted_to,
        retraction_reason=retraction_reason,
        turn=turn,
        opinions=opinions,
        rel_path=rel_path,
        sha=sha,
    )
    return ruling, diagnostics


def load_catalog_state(root: Path) -> Tuple[Dict[str, str], Optional[str]]:
    """Return ({id: path} for catalog entries with a non-empty string id, 8-char sha or None)."""
    catalog_path = root / CATALOG_REL_PATH
    if not catalog_path.is_file():
        return {}, None
    try:
        raw = catalog_path.read_bytes()
        data = json.loads(raw)
    except (OSError, ValueError):
        return {}, None
    if not isinstance(data, dict):
        return {}, None
    sha = hashlib.sha256(raw).hexdigest()[:8]
    id_to_path: Dict[str, str] = {}
    entries = data.get("entries", [])
    if isinstance(entries, list):
        for entry in entries:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("id"), str)
                and entry["id"]
                and isinstance(entry.get("path"), str)
            ):
                id_to_path[entry["id"]] = entry["path"]
    return id_to_path, sha


def _check_promoted_to(root: Path, rel_path: str, promoted_to: str, include_paths: List[str]) -> Optional[str]:
    """Validate a promoted_to vault-relative Tier 1 path; returns an error message or None."""
    resolved = (root / promoted_to).resolve()
    if not resolved.is_relative_to(root.resolve()):
        return f"'promoted_to' escapes the vault root: {promoted_to!r}"
    rel_posix = resolved.relative_to(root.resolve()).as_posix()
    if not resolved.is_file() or resolved.suffix.lower() != ".md":
        return f"'promoted_to' must resolve to an existing Tier 1 .md file: {promoted_to!r}"
    if rel_posix.startswith("_gm-materials/") or rel_posix.startswith(".agents/"):
        return f"'promoted_to' must point outside _gm-materials/ and .agents/: {promoted_to!r}"
    if not any(rel_posix == inc or rel_posix.startswith(f"{inc}/") for inc in include_paths):
        return f"'promoted_to' must match include_paths from tier1_sources.yml: {promoted_to!r}"
    return None


def validate_rulings(
    root: Path,
    catalog_ids: Optional[Dict[str, str]] = None,
) -> Tuple[List[ParsedRuling], Dict[str, List[str]], Dict[str, Dict[str, Optional[str]]], List[Tier2Diagnostic]]:
    """Parse all rulings and enforce uniqueness, DAG invariants, and the status matrix.

    Returns (rulings, superseded_by map, per-ruling resolved_entities, diagnostics).
    """
    if catalog_ids is None:
        catalog_ids, _ = load_catalog_state(root)
    diagnostics: List[Tier2Diagnostic] = []
    rulings: List[ParsedRuling] = []
    for path in discover_ruling_files(root):
        ruling, diags = parse_ruling_file(root, path)
        diagnostics.extend(diags)
        if ruling is not None:
            rulings.append(ruling)

    by_id: Dict[str, List[ParsedRuling]] = {}
    for ruling in rulings:
        by_id.setdefault(ruling.id, []).append(ruling)
    duplicate_ids = {rid for rid, group in by_id.items() if len(group) > 1}
    for rid in sorted(duplicate_ids):
        group = by_id[rid]
        files = ", ".join(sorted(r.rel_path for r in group))
        diagnostics.append(
            Tier2Diagnostic("FAIL", files, 1, f"duplicate ruling id '{rid}' shared by {len(group)} files")
        )
    valid = [r for r in rulings if r.id not in duplicate_ids]
    id_set = {r.id for r in valid}
    by_id_valid = {r.id: r for r in valid}

    # Rule 1: no self-loops or dangling supersedes targets.
    for ruling in valid:
        for target in ruling.supersedes:
            if target == ruling.id:
                diagnostics.append(
                    Tier2Diagnostic("FAIL", ruling.rel_path, 1, f"self-loop: ruling '{ruling.id}' supersedes itself")
                )
            elif target not in id_set:
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL", ruling.rel_path, 1, f"supersedes target '{target}' does not exist in _gm-materials/rulings/"
                    )
                )

    # Rule 2: DAG acyclicity via 3-colour DFS over supersedes edges.
    supersedes_map = {
        r.id: [t for t in r.supersedes if t in id_set and t != r.id] for r in valid
    }
    colour: Dict[str, int] = {rid: 0 for rid in id_set}  # 0=white, 1=gray, 2=black

    def dfs(node: str, stack: List[str]) -> None:
        colour[node] = 1
        stack.append(node)
        for nxt in supersedes_map.get(node, []):
            if colour[nxt] == 1:
                cycle = stack[stack.index(nxt):] + [nxt]
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL",
                        by_id_valid[nxt].rel_path,
                        1,
                        "supersession cycle detected: " + " -> ".join(cycle),
                    )
                )
            elif colour[nxt] == 0:
                dfs(nxt, stack)
        stack.pop()
        colour[node] = 2

    for rid in sorted(id_set):
        if colour[rid] == 0:
            dfs(rid, [])

    # Rule 3: target status alignment and orphaned superseded rulings.
    targeted = {t for r in valid for t in r.supersedes}
    for ruling in valid:
        for target in ruling.supersedes:
            if target in id_set:
                target_status = by_id_valid[target].status
                if target_status != "superseded":
                    diagnostics.append(
                        Tier2Diagnostic(
                            "FAIL",
                            ruling.rel_path,
                            1,
                            f"supersedes target '{target}' has status '{target_status}'; "
                            "only 'superseded' rulings may be superseded",
                        )
                    )
    for ruling in valid:
        if ruling.status == "superseded" and ruling.id not in targeted:
            diagnostics.append(
                Tier2Diagnostic(
                    "FAIL",
                    ruling.rel_path,
                    1,
                    f"status is 'superseded' but no other ruling lists '{ruling.id}' in 'supersedes'",
                )
            )

    # Rule 4: status-to-partner-field matrix.
    include_paths = _load_include_paths(root)
    for ruling in valid:
        if ruling.status in ("active", "superseded"):
            if ruling.promoted_to is not None:
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL", ruling.rel_path, 1, f"status '{ruling.status}' must not set 'promoted_to'"
                    )
                )
            if ruling.retraction_reason is not None:
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL", ruling.rel_path, 1, f"status '{ruling.status}' must not set 'retraction_reason'"
                    )
                )
        elif ruling.status == "promoted":
            if ruling.retraction_reason is not None:
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL", ruling.rel_path, 1, "status 'promoted' must not set 'retraction_reason'"
                    )
                )
            if not ruling.promoted_to:
                diagnostics.append(
                    Tier2Diagnostic("FAIL", ruling.rel_path, 1, "status 'promoted' requires a non-empty 'promoted_to'")
                )
            else:
                problem = _check_promoted_to(root, ruling.rel_path, ruling.promoted_to, include_paths)
                if problem:
                    diagnostics.append(Tier2Diagnostic("FAIL", ruling.rel_path, 1, problem))
        elif ruling.status == "retracted":
            if not ruling.retraction_reason:
                diagnostics.append(
                    Tier2Diagnostic("FAIL", ruling.rel_path, 1, "status 'retracted' requires a non-empty 'retraction_reason'")
                )
            if ruling.promoted_to is not None:
                diagnostics.append(
                    Tier2Diagnostic("FAIL", ruling.rel_path, 1, "status 'retracted' must not set 'promoted_to'")
                )
            if ruling.supersedes:
                diagnostics.append(
                    Tier2Diagnostic(
                        "FAIL", ruling.rel_path, 1, "status 'retracted' must have an empty 'supersedes' list"
                    )
                )

    # Rule 5: single active successor per superseded target.
    active_superseding: Dict[str, List[str]] = {}
    for ruling in valid:
        if ruling.status == "active":
            for target in ruling.supersedes:
                active_superseding.setdefault(target, []).append(ruling.id)
    for target, ids in sorted(active_superseding.items()):
        if len(ids) > 1:
            files = ", ".join(sorted(by_id_valid[rid].rel_path for rid in ids))
            diagnostics.append(
                Tier2Diagnostic(
                    "FAIL",
                    files,
                    1,
                    f"multiple active rulings supersede '{target}': {', '.join(sorted(ids))} "
                    "(single active successor required)",
                )
            )

    # Inverse derivation: superseded_by (sorted IDs per ruling).
    superseded_by: Dict[str, List[str]] = {r.id: [] for r in valid}
    for ruling in valid:
        for target in ruling.supersedes:
            if target in superseded_by:
                superseded_by[target].append(ruling.id)
    superseded_by = {rid: sorted(ids) for rid, ids in superseded_by.items()}

    # Compile-time left-join of entities/actors against catalog.json ids.
    resolved: Dict[str, Dict[str, Optional[str]]] = {}
    for ruling in valid:
        ruling_resolved: Dict[str, Optional[str]] = {}
        for slug in sorted(set(ruling.entities) | set(ruling.actors)):
            value = catalog_ids.get(slug)
            ruling_resolved[slug] = value
            if value is None:
                diagnostics.append(
                    Tier2Diagnostic(
                        "WARN",
                        ruling.rel_path,
                        1,
                        f"unresolved slug '{slug}' (no Tier 1 note carries id '{slug}' in catalog.json)",
                    )
                )
        resolved[ruling.id] = ruling_resolved

    return rulings, superseded_by, resolved, diagnostics


def find_active_entity_overlaps(rulings: List[ParsedRuling]) -> Dict[str, List[ParsedRuling]]:
    """Group active rulings by each entity slug; return slugs shared by 2+ active rulings."""
    overlaps: Dict[str, List[ParsedRuling]] = {}
    for ruling in rulings:
        if ruling.status != "active":
            continue
        for slug in set(ruling.entities):
            overlaps.setdefault(slug, []).append(ruling)
    return {slug: group for slug, group in overlaps.items() if len(group) >= 2}


def compile_tier2_index(
    root: Path, write: bool = True
) -> Tuple[Optional[Dict[str, Any]], List[Tier2Diagnostic], Dict[str, List[ParsedRuling]]]:
    """Validate and compile the entries-only tier2.json index; optionally write it atomically.

    Returns (payload-or-None-on-FAIL, diagnostics, active-entity overlaps). When
    write=True and validation is clean, the cache is written atomically via a
    temp file + os.replace(), skipping the write when only `generated` differs.
    """
    catalog_ids, catalog_sha = load_catalog_state(root)
    rulings, superseded_by, resolved, diagnostics = validate_rulings(root, catalog_ids)
    overlaps = find_active_entity_overlaps(rulings)
    if any(d.severity == "FAIL" for d in diagnostics):
        return None, diagnostics, {}

    entries = []
    for ruling in sorted(rulings, key=lambda r: r.id):
        entries.append(
            {
                "id": ruling.id,
                "title": ruling.title,
                "date": ruling.date,
                "in_world_date": ruling.in_world_date,
                "kind": ruling.kind,
                "status": ruling.status,
                "fact": ruling.fact,
                "entities": list(ruling.entities),
                "actors": list(ruling.actors),
                "resolved_entities": resolved.get(ruling.id, {}),
                "supersedes": list(ruling.supersedes),
                "superseded_by": superseded_by.get(ruling.id, []),
                "promoted_to": ruling.promoted_to,
                "retraction_reason": ruling.retraction_reason,
                "path": ruling.rel_path,
                "sha": ruling.sha,
            }
        )
    payload: Dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "catalog_sha": catalog_sha,
        "entries": entries,
    }

    if write:
        cache_path = root / CACHE_REL_PATH
        if cache_path.is_file():
            try:
                existing = json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                existing = None
            if isinstance(existing, dict):
                existing_cmp = {k: v for k, v in existing.items() if k != "generated"}
                payload_cmp = {k: v for k, v in payload.items() if k != "generated"}
                if existing_cmp == payload_cmp:
                    return payload, diagnostics, overlaps  # idempotent: skip rewrite
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = cache_path.with_name(cache_path.name + ".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp_path, cache_path)

    return payload, diagnostics, overlaps


def load_active_rulings_text(repo_root: Path) -> str:
    """Return formatted `- **<id> — <title>:** <fact>` lines for all active rulings.

    When `_gm-materials/rulings/` exists, rulings are validated directly from
    disk (never via the derived cache, so a stale tier2.json can never inject
    outdated canon); any FAIL diagnostic raises ValueError after printing all
    FAILs to stderr. When the rulings directory is absent, falls back
    read-only to legacy `.agents/context/decisions.md` when present.
    """
    rulings_dir = repo_root / RULINGS_REL_DIR
    if rulings_dir.is_dir():
        rulings, _, _, diagnostics = validate_rulings(repo_root)
        fails = [d for d in diagnostics if d.severity == "FAIL"]
        if fails:
            for d in fails:
                print(f"[FAIL] {d.file}:{d.line}: {d.message}", file=sys.stderr)
            raise ValueError(
                f"invalid rulings under {RULINGS_REL_DIR.as_posix()}: {len(fails)} FAIL diagnostic(s); "
                "run `oude tier2` or `oude lint-wiki` for details"
            )
        active = sorted((r for r in rulings if r.status == "active"), key=lambda r: r.id)
        if len(active) > ACTIVE_RULINGS_WARN_THRESHOLD:
            print(
                f"[WARN] {len(active)} active rulings exceed the advisory threshold "
                f"({ACTIVE_RULINGS_WARN_THRESHOLD}); consider promoting or consolidating them",
                file=sys.stderr,
            )
        return "\n".join(f"- **{r.id} — {r.title}:** {r.fact}" for r in active)
    legacy = repo_root / LEGACY_DECISIONS_REL_PATH
    if legacy.is_file():
        return legacy.read_text(encoding="utf-8").strip()
    return ""


def main(argv: Optional[List[str]] = None) -> int:
    """Compile and validate Tier 2 rulings into _gm-materials/.cache/tier2.json."""
    parser = argparse.ArgumentParser(
        prog="tier2",
        description=(
            "Compile and validate Tier 2 rulings (_gm-materials/rulings/*.md) into the derived "
            "index _gm-materials/.cache/tier2.json."
        ),
    )
    parser.add_argument(
        "--root",
        default=".",
        help="Campaign vault root (default: current directory).",
    )
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"Error: root '{root}' is not a directory", file=sys.stderr)
        return 2

    if not discover_ruling_files(root):
        print(f"No rulings found under {RULINGS_REL_DIR.as_posix()}/ — nothing to compile.")
        return 0

    payload, diagnostics, overlaps = compile_tier2_index(root, write=True)
    for d in diagnostics:
        stream = sys.stderr if d.severity == "FAIL" else sys.stdout
        print(f"[{d.severity}] {d.file}:{d.line}: {d.message}", file=stream)
    if payload is None:
        print(
            "Compilation aborted: fix the FAIL diagnostics above; "
            f"{CACHE_REL_PATH.as_posix()} was not written.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Compiled {len(payload['entries'])} ruling(s) into {CACHE_REL_PATH.as_posix()} "
        f"(schema_version {SCHEMA_VERSION}, catalog_sha {payload['catalog_sha']})."
    )
    for slug, group in sorted(overlaps.items()):
        desc = ", ".join(f"{r.id} ({r.title})" for r in sorted(group, key=lambda r: r.id))
        print(f"[WARN] active-entity overlap on '{slug}': {desc} — evaluate whether one supersedes the other")
    return 0


if __name__ == "__main__":
    sys.exit(main())
