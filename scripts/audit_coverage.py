#!/usr/bin/env python3
"""
Automated Gap Analysis for Tabletop RPG Campaign Vaults.

Performs a multi-layered campaign audit:
1. Google Drive Sync: Audits raw sourcebooks, PDFs, and Google Sheets against
   the Tier 3 routing index (.agents/context/references.json) and _digests/.
2. Route Topology & Proximity Gaps (optional): When .agents/context/route_graph.json
   is present, maps the trail/star system graph from the latest session log,
   and flags unvisited destinations within N hops (default: 2).
3. Untapped Factions & Lore Hooks: Identifies canon entities, patrons, and hazards
   in current and proximate sectors that have not yet been introduced.
4. Directory Depth: Checks for empty stubs, disconnected NPCs, or missing indexes.

Usage:
  python3 scripts/audit_coverage.py
  python3 scripts/audit_coverage.py --radius 2 --json
  python3 scripts/audit_coverage.py --report-path /path/to/report.md
  python3 scripts/audit_coverage.py --repo-dir /path/to/repo --drive-dir /path/to/drive
"""

import argparse
import json
import os
import re
import sys
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def find_repo_root(custom_dir: Optional[str] = None) -> Path:
    """Detect the campaign repository root directory."""
    if custom_dir:
        p = Path(custom_dir).resolve()
        if p.exists() and p.is_dir():
            return p

    cwd = Path.cwd().resolve()
    for candidate in [cwd, *cwd.parents]:
        if (candidate / "_config.yml").exists() or (candidate / ".agents").is_dir():
            return candidate

    return cwd


def resolve_drive_dir(repo_root: Path, custom_drive: Optional[str] = None) -> Optional[Path]:
    """Resolve the campaign Google Drive directory from tier1_sources.yml or fallback glob."""
    if custom_drive:
        p = Path(custom_drive).resolve()
        if p.exists() and p.is_dir():
            return p

    tier1_path = repo_root / ".agents" / "context" / "tier1_sources.yml"
    if tier1_path.exists():
        try:
            content = tier1_path.read_text(encoding="utf-8")
            m = re.search(r"^drive_dir:\s*['\"]?(.*?)['\"]?\s*$", content, re.MULTILINE)
            if m and m.group(1).strip():
                raw = m.group(1).strip()
                p = Path(os.path.expanduser(raw)).resolve()
                if p.exists():
                    return p
        except Exception:
            pass

    # Generic CloudStorage glob fallback without hardcoded personal accounts
    repo_name = repo_root.name
    try:
        cloud_storage = Path.home() / "Library" / "CloudStorage"
        if cloud_storage.exists():
            matches = list(cloud_storage.glob(f"GoogleDrive-*/My Drive/RPG/campaigns/{repo_name}"))
            if matches and matches[0].exists():
                return matches[0]
    except Exception:
        pass

    return None


def load_route_graph(repo_root: Path) -> Optional[Dict[str, Any]]:
    """Load route graph from .agents/context/route_graph.json if available."""
    graph_path = repo_root / ".agents" / "context" / "route_graph.json"
    if not graph_path.exists():
        return None

    try:
        with open(graph_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data
    except Exception as e:
        print(f"Warning: Failed to parse {graph_path}: {e}", file=sys.stderr)
        return None


def audit_drive_sync(repo_root: Path, drive_dir: Optional[Path]) -> Dict[str, Any]:
    """Audit physical Google Drive files against references.json and _digests/."""
    results: Dict[str, Any] = {
        "drive_accessible": False,
        "indexed_sources": [],
        "unindexed_files": [],
        "missing_digests": [],
        "total_drive_files": 0,
    }

    ref_path = repo_root / ".agents" / "context" / "references.json"
    indexed_map: Dict[str, Dict[str, Any]] = {}
    if ref_path.exists():
        try:
            with open(ref_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for src in data.get("sources", []):
                    indexed_map[src.get("slug")] = src
        except Exception as e:
            results["references_error"] = str(e)

    results["indexed_sources"] = list(indexed_map.keys())

    if not drive_dir or not drive_dir.exists():
        return results

    results["drive_accessible"] = True
    digests_dir = drive_dir / "_digests"

    drive_files: List[Path] = []
    try:
        for root, dirs, files in os.walk(drive_dir):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "_digests"]
            for f in files:
                if not f.startswith(".") and not f.startswith("~"):
                    drive_files.append(Path(root) / f)
    except PermissionError:
        results["drive_permission_denied"] = True
        return results

    results["total_drive_files"] = len(drive_files)

    known_names = {Path(s.get("source_pdf", "")).name for s in indexed_map.values()}

    for fpath in drive_files:
        ext = fpath.suffix.lower()
        if ext in [".pdf", ".gdoc", ".gsheet"]:
            if fpath.name not in known_names:
                action_hint = "Extract digest to `_digests/`"
                if ext == ".gsheet":
                    action_hint = "Spreadsheet ledger or trade table"
                elif ext == ".gdoc":
                    action_hint = "Campaign document or background notes"

                results["unindexed_files"].append({
                    "name": fpath.name,
                    "rel_path": str(fpath.relative_to(drive_dir)),
                    "type": "spreadsheet" if ext == ".gsheet" else ("document" if ext == ".gdoc" else "sourcebook"),
                    "size_bytes": fpath.stat().st_size if fpath.exists() else 0,
                    "action_hint": action_hint,
                })

    for slug, src in indexed_map.items():
        digest_file = Path(src.get("digest_path", digests_dir / f"{slug}.md"))
        if not digest_file.exists():
            results["missing_digests"].append({
                "slug": slug,
                "title": src.get("title", slug),
                "expected_path": str(digest_file),
            })

    return results


def get_current_campaign_location(
    repo_root: Path,
    route_graph: Optional[Dict[str, Any]],
    custom_campaign_subfolder: Optional[str] = None
) -> Dict[str, Any]:
    """Determine the party's current location from the latest session log."""
    info: Dict[str, Any] = {
        "latest_episode": None,
        "raw_region": None,
        "matched_station": None,
        "matched": False,
    }

    target_dir: Optional[Path] = None
    if custom_campaign_subfolder:
        p = (repo_root / custom_campaign_subfolder).resolve()
        if p.is_dir():
            target_dir = p

    if not target_dir:
        # Check AGENTS.md for Default Campaign Subfolder
        agents_md = repo_root / ".agents" / "AGENTS.md"
        if agents_md.exists():
            try:
                txt = agents_md.read_text(encoding="utf-8")
                m = re.search(r"Default Campaign Subfolder:\s*`?([^`\r\n]+)`?", txt)
                if m and m.group(1).strip():
                    cand = (repo_root / m.group(1).strip()).resolve()
                    if cand.is_dir():
                        target_dir = cand
            except Exception:
                pass

    if not target_dir:
        target_dir = repo_root / "campaigns"

    if not target_dir.is_dir():
        return info

    # Find all session logs with type: session (or .md files)
    logs: List[Tuple[Path, str]] = []
    for p in target_dir.rglob("*.md"):
        if p.name == "index.md":
            continue
        try:
            txt = p.read_text(encoding="utf-8")
            if re.search(r"^type:\s*session\b", txt, re.MULTILINE):
                # Extract nav_order or fallback to stem
                order_match = re.search(r"^nav_order:\s*['\"]?(.*?)['\"]?\s*$", txt, re.MULTILINE)
                sort_val = order_match.group(1).strip() if order_match else p.stem
                logs.append((p, sort_val))
        except Exception:
            pass

    if not logs:
        # Fallback to any markdown files in the folder
        for p in target_dir.glob("*.md"):
            if p.name != "index.md":
                logs.append((p, p.stem))

    if not logs:
        return info

    logs.sort(key=lambda item: item[1])
    latest, _ = logs[-1]
    info["latest_episode"] = str(latest.relative_to(repo_root))

    try:
        content = latest.read_text(encoding="utf-8")
        region_match = re.search(r"^(?:region|location):\s*(.+)$", content, re.MULTILINE)
        if region_match:
            raw_reg = region_match.group(1).strip()
            info["raw_region"] = raw_reg
            raw_lower = raw_reg.lower()

            if route_graph and "stations" in route_graph:
                stations = route_graph["stations"]
                for station_name, sdata in stations.items():
                    aliases = [a.lower() for a in sdata.get("aliases", [])]
                    aliases.append(station_name.lower())
                    if any(alias in raw_lower for alias in aliases):
                        info["matched_station"] = station_name
                        info["matched"] = True
                        break
    except Exception as e:
        info["error"] = str(e)

    return info


def build_adjacency(route_graph: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """Build adjacency list for the campaign route network."""
    stations = route_graph.get("stations", {})
    adj: Dict[str, List[Dict[str, Any]]] = {k: [] for k in stations}

    opposite_dir = {
        "West": "East", "East": "West",
        "North": "South", "South": "North",
        "North-West": "South-East", "South-East": "North-West",
        "North-East": "South-West", "South-West": "North-East",
        "Inward": "Outward", "Outward": "Inward",
        "Up": "Down", "Down": "Up",
    }

    for conn in route_graph.get("connections", []):
        orig = conn.get("origin")
        dest = conn.get("destination")
        weeks = conn.get("weeks", 1)
        direction = conn.get("direction", "")
        terrain = conn.get("terrain", "")

        if orig in adj and dest in adj:
            adj[orig].append({
                "station": dest,
                "weeks": weeks,
                "direction": direction,
                "terrain": terrain,
            })
            adj[dest].append({
                "station": orig,
                "weeks": weeks,
                "direction": opposite_dir.get(direction, "Opposite"),
                "terrain": terrain,
            })

    return adj


def get_directory_status(repo_root: Path, route_graph: Optional[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Scan directory/ and catalog.json to identify existing location and entity notes."""
    status: Dict[str, Dict[str, Any]] = {}
    dir_path = repo_root / "directory"

    if not route_graph or "stations" not in route_graph:
        return status

    for station_name, sdata in route_graph["stations"].items():
        folder_name = sdata.get("dir_folder")
        folder_path = dir_path / folder_name if (folder_name and dir_path.exists()) else None

        has_folder = folder_path.is_dir() if folder_path else False
        has_index = (folder_path / "index.md").is_file() if has_folder else False

        child_notes: List[str] = []
        if has_folder and folder_path:
            child_notes = [p.stem for p in folder_path.glob("*.md") if p.name != "index.md"]

        content_lines = 0
        has_trade_table = False
        if has_index and folder_path:
            try:
                txt = (folder_path / "index.md").read_text(encoding="utf-8")
                body = re.sub(r"^---.*?---\s*", "", txt, flags=re.DOTALL)
                content_lines = len([l for l in body.splitlines() if l.strip()])
                has_trade_table = "Most profitable trade" in txt or "Location Price" in txt
            except Exception:
                pass

        note_state = "Untapped"
        if has_index:
            note_state = "Stub" if content_lines < 8 else "Established"

        status[station_name] = {
            "state": note_state,
            "folder": str(folder_path.relative_to(repo_root)) if (has_folder and folder_path) else None,
            "child_entities": child_notes,
            "content_lines": content_lines,
            "has_trade_table": has_trade_table,
        }

    return status


def calculate_proximity_gaps(
    current_station: str,
    route_graph: Dict[str, Any],
    dir_status: Dict[str, Dict[str, Any]],
    max_hops: int = 2
) -> List[Dict[str, Any]]:
    """Calculate reachable locations within max_hops from the current station."""
    adj = build_adjacency(route_graph)
    queue: deque = deque([(current_station, 0, 0, [])])
    visited: Set[str] = {current_station}
    results: List[Dict[str, Any]] = []

    while queue:
        curr, hops, total_weeks, path = queue.popleft()

        if curr != current_station:
            dstate = dir_status.get(curr, {})
            results.append({
                "station": curr,
                "hops": hops,
                "total_weeks": total_weeks,
                "path_from_current": path,
                "state": dstate.get("state", "Untapped"),
                "folder": dstate.get("folder"),
                "child_entities": dstate.get("child_entities", []),
                "has_trade_table": dstate.get("has_trade_table", False),
            })

        if hops < max_hops:
            for edge in adj.get(curr, []):
                neighbour = edge["station"]
                if neighbour not in visited:
                    visited.add(neighbour)
                    desc = f"{edge['direction']} to {neighbour} ({edge['weeks']}w, {edge['terrain']})"
                    queue.append((neighbour, hops + 1, total_weeks + edge["weeks"], path + [desc]))

    results.sort(key=lambda x: (x["hops"], x["total_weeks"]))
    return results


def audit_untapped_factions(
    current_station: str,
    proximate_stations: List[Dict[str, Any]],
    route_graph: Dict[str, Any],
    repo_root: Path,
    dir_status: Dict[str, Dict[str, Any]]
) -> Dict[str, Any]:
    """Cross-reference canon entities with repository notes to surface unintroduced factions & NPCs."""
    catalog_path = repo_root / ".agents" / "context" / "catalog.json"
    catalog_titles: Set[str] = set()

    if catalog_path.exists():
        try:
            with open(catalog_path, "r", encoding="utf-8") as f:
                for entry in json.load(f).get("entries", []):
                    catalog_titles.add(entry.get("title", "").strip().lower())
                    p = Path(entry.get("path", ""))
                    catalog_titles.add(p.stem.lower())
        except Exception:
            pass

    station_lore = route_graph.get("station_lore", {})
    audit: Dict[str, Any] = {
        "current_station": {
            "name": current_station,
            "introduced": [],
            "untapped": [],
            "hazards": station_lore.get(current_station, {}).get("road_hazards", []),
        },
        "proximate_untapped_entities": [],
    }

    curr_lore = station_lore.get(current_station, {}).get("canon_entities", [])
    for ent in curr_lore:
        name_lower = ent["name"].lower()
        is_known = any(name_lower in t or t in name_lower for t in catalog_titles)
        if not is_known and current_station in dir_status:
            is_known = any(name_lower in c.lower() for c in dir_status[current_station].get("child_entities", []))

        if is_known:
            audit["current_station"]["introduced"].append(ent)
        else:
            audit["current_station"]["untapped"].append(ent)

    for prox in proximate_stations:
        st_name = prox["station"]
        st_lore = station_lore.get(st_name, {})
        for ent in st_lore.get("canon_entities", []):
            name_lower = ent["name"].lower()
            is_known = any(name_lower in t or t in name_lower for t in catalog_titles)
            if not is_known:
                audit["proximate_untapped_entities"].append({
                    "station": st_name,
                    "hops": prox["hops"],
                    "entity": ent,
                })

    return audit


def run_gap_analysis(
    repo_root: Path,
    drive_dir: Optional[Path],
    max_hops: int = 2,
    campaign_subfolder: Optional[str] = None
) -> Dict[str, Any]:
    """Execute complete gap analysis and return structured findings."""
    drive_audit = audit_drive_sync(repo_root, drive_dir)
    route_graph = load_route_graph(repo_root)
    location_info = get_current_campaign_location(repo_root, route_graph, campaign_subfolder)

    results: Dict[str, Any] = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "drive_audit": drive_audit,
        "location": location_info,
        "route_graph_available": route_graph is not None,
    }

    if route_graph and location_info.get("matched_station"):
        curr_station = location_info["matched_station"]
        dir_status = get_directory_status(repo_root, route_graph)
        proximity_gaps = calculate_proximity_gaps(curr_station, route_graph, dir_status, max_hops=max_hops)
        faction_audit = audit_untapped_factions(curr_station, proximity_gaps, route_graph, repo_root, dir_status)

        results["proximity_gaps"] = proximity_gaps
        results["factions"] = faction_audit

    return results


def format_markdown_report(report: Dict[str, Any]) -> str:
    """Format structured gap analysis results into a clean markdown document."""
    lines: List[str] = [
        "# Campaign Coverage & Gap Analysis",
        "",
        f"**Generated:** {report.get('timestamp', '')[:10]}",
        f"**Repository:** `{report.get('repo_root')}`",
        "",
        "## Summary",
        "",
    ]

    drive = report.get("drive_audit", {})
    loc = report.get("location", {})
    has_graph = report.get("route_graph_available", False)

    unindexed_count = len(drive.get("unindexed_files", []))
    missing_digests_count = len(drive.get("missing_digests", []))

    lines.append(f"- **Google Drive Access:** {'Accessible' if drive.get('drive_accessible') else 'Offline / Not Found'}")
    lines.append(f"- **Indexed Tier 3 Sources:** {len(drive.get('indexed_sources', []))}")
    lines.append(f"- **Unindexed Drive Files:** {unindexed_count}")
    lines.append(f"- **Missing Digests:** {missing_digests_count}")
    lines.append(f"- **Latest Session:** `{loc.get('latest_episode', 'None')}`")
    lines.append(f"- **Current Location:** {loc.get('raw_region', 'Unknown')}")
    if has_graph:
        lines.append(f"- **Matched Station:** {loc.get('matched_station', 'None')}")
    lines.append("")

    # Section 1: Drive Sync
    lines.append("## Tier 3 Source Material & Drive Sync")
    lines.append("")
    if unindexed_count > 0:
        lines.append("### Unindexed Drive Files")
        lines.append("")
        lines.append("| Filename | Type | Recommended Action |")
        lines.append("|---|---|---|")
        for u in drive["unindexed_files"]:
            lines.append(f"| `{u['name']}` | {u['type']} | {u['action_hint']} |")
        lines.append("")

    if missing_digests_count > 0:
        lines.append("### Missing Digest Files")
        lines.append("")
        for m in drive["missing_digests"]:
            lines.append(f"- `{m['slug']}` ({m['title']}): expected at `{m['expected_path']}`")
        lines.append("")

    if unindexed_count == 0 and missing_digests_count == 0:
        lines.append("All reference materials in Google Drive match the active Tier 3 digest index.")
        lines.append("")

    # Section 2: Proximity Gaps (if route graph available)
    if has_graph and "proximity_gaps" in report:
        lines.append("## Geographic Proximity & Destination Gaps")
        lines.append("")
        prox = report["proximity_gaps"]
        if prox:
            lines.append("| Destination | Hops | Travel Time | Current State | Notes & Deficiencies |")
            lines.append("|---|---|---|---|---|")
            for p in prox:
                folder_desc = f"`{p['folder']}`" if p["folder"] else "*None*"
                notes = []
                if p["state"] == "Untapped":
                    notes.append("No entry in `directory/`.")
                elif p["state"] == "Stub":
                    notes.append("Folder exists but has under 8 lines of body content.")
                else:
                    ent_cnt = len(p.get("child_entities", []))
                    market_info = "; market table present" if p.get("has_trade_table") else ""
                    notes.append(f"{ent_cnt} entities in {folder_desc}{market_info}")
                lines.append(f"| **{p['station']}** | {p['hops']} | {p['total_weeks']} weeks | {p['state']} | {' '.join(notes)} |")
            lines.append("")
        else:
            lines.append("No destination gaps identified within the specified search radius.")
            lines.append("")

        factions = report.get("factions", {})
        curr = factions.get("current_station", {})
        intro_curr = curr.get("introduced", [])
        if intro_curr:
            lines.append(f"### Introduced Entities at {curr.get('name')}")
            lines.append("")
            for ent in intro_curr:
                desc = ent.get("role") or ent.get("summary", "")
                desc_str = f": {desc}" if desc else ""
                lines.append(f"- **{ent['name']}** ({ent.get('type', 'Entity')}){desc_str}")
            lines.append("")

        untapped_curr = curr.get("untapped", [])
        if untapped_curr:
            lines.append(f"### Untapped Lore & Entities at {curr.get('name')}")
            lines.append("")
            for ent in untapped_curr:
                desc = ent.get("role") or ent.get("summary", "")
                desc_str = f": {desc}" if desc else ""
                lines.append(f"- **{ent['name']}** ({ent.get('type', 'Entity')}){desc_str}")
            lines.append("")

        hazards = curr.get("hazards", [])
        if hazards:
            lines.append(f"### Regional Environmental Hazards at {curr.get('name')}")
            lines.append("")
            for haz in hazards:
                lines.append(f"- {haz}")
            lines.append("")

        prox_untapped = factions.get("proximate_untapped_entities", [])
        if prox_untapped:
            lines.append("### Untapped Entities in Proximate Locations")
            lines.append("")
            lines.append("| Destination | Hop | Entity | Role / Summary |")
            lines.append("|---|---|---|---|")
            for pu in prox_untapped:
                ent = pu["entity"]
                desc = ent.get("role") or ent.get("summary", "")
                lines.append(f"| {pu['station']} | {pu['hops']} | **{ent['name']}** ({ent.get('type', 'Entity')}) | {desc} |")
            lines.append("")
    elif not has_graph:
        lines.append("## Geographic Proximity")
        lines.append("")
        lines.append("No route graph (`.agents/context/route_graph.json`) defined for this campaign. Proximity gap analysis was skipped.")
        lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit campaign coverage and gap analysis.")
    parser.add_argument("--repo-dir", "--repo-root", dest="repo_dir", help="Path to campaign repository root.")
    parser.add_argument("--drive-dir", help="Path to campaign Google Drive folder.")
    parser.add_argument("--campaign-dir", help="Subfolder under campaigns/ (e.g. campaigns/UVG24XX).")
    parser.add_argument("--radius", type=int, default=2, help="Proximity search radius in hops (default: 2).")
    parser.add_argument("--json", action="store_true", help="Output results as JSON.")
    parser.add_argument("--report-path", help="Save markdown report to specific file path.")

    args = parser.parse_args()

    repo_root = find_repo_root(args.repo_dir)
    drive_dir = resolve_drive_dir(repo_root, args.drive_dir)

    report = run_gap_analysis(
        repo_root,
        drive_dir,
        max_hops=args.radius,
        campaign_subfolder=args.campaign_dir
    )

    if args.json:
        print(json.dumps(report, indent=2))
        return

    md_output = format_markdown_report(report)

    if args.report_path:
        out_p = Path(args.report_path).resolve()
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(md_output, encoding="utf-8")
        print(f"Report saved to {out_p}")
    else:
        print(md_output)


if __name__ == "__main__":
    main()
