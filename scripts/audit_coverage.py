#!/usr/bin/env python3
"""
Automated Gap Analysis for the Charged Campaign.

Performs a multi-layered campaign audit:
1. Google Drive Sync: Audits raw sourcebooks, PDFs, and Google Sheets against
   the Tier 3 routing index (.agents/context/references.json) and _digests/.
2. Trail Proximity & Untapped Locations: Determines the caravan's active location
   from the latest session log, maps the 23-station Ultraviolet Grasslands trail graph,
   and flags unvisited / unwritten destinations within N hops (default: 2).
3. Untapped Factions & Lore Hooks: Identifies canon entities, patrons, hazards, and
   relics in current and proximate sectors that have not yet been introduced to the PCs.
4. Directory Depth: Checks for empty stubs, disconnected NPCs, or missing market tables.

Usage:
  .agents/venv/bin/python3 .agents/scripts/audit_coverage.py
  .agents/venv/bin/python3 .agents/scripts/audit_coverage.py --radius 2 --json
  .agents/venv/bin/python3 .agents/scripts/audit_coverage.py --report-path /path/to/report.md
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

REPO_ROOT = Path(__file__).resolve().parents[2]
DRIVE_DIR = Path(
    "/Users/efsa/Library/CloudStorage/GoogleDrive-estevao.alvarenga@gmail.com/My Drive/RPG/campaigns/charged"
)
DIGESTS_DIR = DRIVE_DIR / "_digests"
REFERENCES_INDEX_PATH = REPO_ROOT / ".agents" / "context" / "references.json"
CATALOG_PATH = REPO_ROOT / ".agents" / "context" / "catalog.json"
CAMPAIGNS_DIR = REPO_ROOT / "campaigns" / "UVG24XX"
DIRECTORY_DIR = REPO_ROOT / "directory"


# -----------------------------------------------------------------------------
# UVG Trail Graph (Stations, Hops, Travel Times, Directions, and Terrain)
# -----------------------------------------------------------------------------

# Station definitions: canonical name, station number, directory folder name (if known)
TRAIL_STATIONS: Dict[str, Dict[str, Any]] = {
    "Violet City (1)": {
        "num": 1,
        "aliases": ["violet city", "the violet city", "violet city (1)"],
        "dir_folder": "VioletCity",
        "category": "starting_settlement",
    },
    "Low Road and High (2)": {
        "num": 2,
        "aliases": ["low road and high", "the low road and the high", "low road / high road", "low road and high (2)"],
        "dir_folder": "LowRoadHigh",
        "category": "road_corridor",
    },
    "Steppe of Lime Nomads (3)": {
        "num": 3,
        "aliases": ["steppe of lime nomads", "steppe of the lime nomads", "lime nomads", "steppe of lime nomads (3)"],
        "dir_folder": "LimeNomads",
        "category": "steppe_camp",
    },
    "Porcelain Citadel (4)": {
        "num": 4,
        "aliases": ["porcelain citadel", "porcelain citadel (4)"],
        "dir_folder": "PorcelainCitadel",
        "category": "citadel_oasis",
    },
    "Potsherd Crater (5)": {
        "num": 5,
        "aliases": ["potsherd crater", "potsherd crater (5)"],
        "dir_folder": "PotsherdCrater",
        "category": "depression_ruins",
    },
    "Trail of Vomish Dreams (6)": {
        "num": 6,
        "aliases": ["trail of vomish dreams", "vomish dreams", "trail of vomish dreams (6)"],
        "dir_folder": "VomishDreams",
        "category": "biomechanical_trail",
    },
    "Grass Colossus (7)": {
        "num": 7,
        "aliases": ["grass colossus", "the grass colossus", "grass colossus (7)"],
        "dir_folder": "GrassColossus",
        "category": "relic_landmark",
    },
    "The Last Serai (8)": {
        "num": 8,
        "aliases": ["last serai", "the last serai", "the last serai (8)"],
        "dir_folder": "LastSerai",
        "category": "frontier_outpost",
    },
    "Way Stone Graveyard (9)": {
        "num": 9,
        "aliases": ["way stone graveyard", "way stone", "the way stone", "way stone graveyard (9)"],
        "dir_folder": "WayStoneGraveyard",
        "category": "megalith_field",
    },
    "Death-Facing Passage (10)": {
        "num": 10,
        "aliases": ["death-facing passage", "the death-facing passage", "death facing passage", "death-facing passage (10)"],
        "dir_folder": "DeathFacingPassage",
        "category": "mountain_pass",
    },
    "South-Facing Passage (11)": {
        "num": 11,
        "aliases": ["south-facing passage", "the south-facing passage", "south facing passage", "south-facing passage (11)"],
        "dir_folder": "SouthFacingPassage",
        "category": "mountain_pass",
    },
    "Fallen Umber (12)": {
        "num": 12,
        "aliases": ["fallen umber", "fallen umber (12)"],
        "dir_folder": "FallenUmber",
        "category": "desert_ruins",
    },
    "Long Ridge & Behemoth (13)": {
        "num": 13,
        "aliases": ["long ridge", "behemoth shell", "long ridge & behemoth", "long ridge (13)"],
        "dir_folder": "LongRidge",
        "category": "calcified_ridge",
    },
    "Moon-Facing Ford (14)": {
        "num": 14,
        "aliases": ["moon-facing ford", "moon river ford", "moon-facing ford (14)"],
        "dir_folder": "MoonFacingFord",
        "category": "river_crossing",
    },
    "Glass Bridge (15)": {
        "num": 15,
        "aliases": ["glass bridge", "three sticks lake", "glass bridge (15)"],
        "dir_folder": "GlassBridge",
        "category": "megastructure",
    },
    "The Gall Grass (16)": {
        "num": 16,
        "aliases": ["the gall grass", "gall grass", "gall grass (16)"],
        "dir_folder": "GallGrass",
        "category": "psychoactive_steppe",
    },
    "Ribs of the Father (17)": {
        "num": 17,
        "aliases": ["ribs of the father", "the ribs", "ribs of the father (17)"],
        "dir_folder": "RibsOfTheFather",
        "category": "subterranean_machinery",
    },
    "The Iron Road (18)": {
        "num": 18,
        "aliases": ["the iron road", "iron road", "the iron road (18)"],
        "dir_folder": "IronRoad",
        "category": "calcified_railway",
    },
    "The Ivory Plain (19)": {
        "num": 19,
        "aliases": ["the ivory plain", "ivory plain", "the ivory plain (19)"],
        "dir_folder": "IvoryPlain",
        "category": "bleached_flatlands",
    },
    "Dead Bridge (20)": {
        "num": 20,
        "aliases": ["dead bridge", "dead bridge (20)"],
        "dir_folder": "DeadBridge",
        "category": "collapsed_span",
    },
    "Dark Light Passage (21)": {
        "num": 21,
        "aliases": ["dark light passage", "dark light path", "dark light passage (21)"],
        "dir_folder": "DarkLightPassage",
        "category": "chasm_canyon",
    },
    "The Endless Houses (22)": {
        "num": 22,
        "aliases": ["the endless houses", "endless houses", "forest of meat", "the endless houses (22)"],
        "dir_folder": "EndlessHouses",
        "category": "modular_ruinland",
    },
    "The Black City (23)": {
        "num": 23,
        "aliases": ["the black city", "black city", "the black city (23)"],
        "dir_folder": "BlackCity",
        "category": "terminal_metropolis",
    },
}

# Bidirectional network links: (origin, destination, weeks, direction_from_origin, terrain)
TRAIL_CONNECTIONS = [
    # Violet City (1)
    ("Violet City (1)", "Low Road and High (2)", 1, "West", "trail"),
    ("Violet City (1)", "Steppe of Lime Nomads (3)", 2, "West", "steppe"),

    # Low Road and High (2)
    ("Low Road and High (2)", "Steppe of Lime Nomads (3)", 1, "North", "steppe"),
    ("Low Road and High (2)", "Porcelain Citadel (4)", 1, "West", "safe oasis"),
    ("Low Road and High (2)", "Potsherd Crater (5)", 2, "South-West", "steppe"),

    # Steppe of Lime Nomads (3)
    ("Steppe of Lime Nomads (3)", "Porcelain Citadel (4)", 1, "West", "safe oasis"),

    # Porcelain Citadel (4)
    ("Porcelain Citadel (4)", "Potsherd Crater (5)", 1, "South", "prospector trails"),
    ("Porcelain Citadel (4)", "The Last Serai (8)", 1, "South-West", "trail"),
    ("Porcelain Citadel (4)", "Trail of Vomish Dreams (6)", 1, "North-West", "trail"),

    # Potsherd Crater (5)
    ("Potsherd Crater (5)", "The Last Serai (8)", 2, "West", "steppe"),

    # Trail of Vomish Dreams (6)
    ("Trail of Vomish Dreams (6)", "Grass Colossus (7)", 1, "West", "trail"),

    # Grass Colossus (7)
    ("Grass Colossus (7)", "Death-Facing Passage (10)", 2, "South", "rough steppe"),
    ("Grass Colossus (7)", "South-Facing Passage (11)", 2, "South-West", "steppe"),
    ("Grass Colossus (7)", "Long Ridge & Behemoth (13)", 1, "West", "trail"),

    # The Last Serai (8)
    ("The Last Serai (8)", "Way Stone Graveyard (9)", 1, "West", "trail"),
    ("The Last Serai (8)", "Death-Facing Passage (10)", 2, "North-West", "canyons"),

    # Way Stone Graveyard (9)
    ("Way Stone Graveyard (9)", "Death-Facing Passage (10)", 2, "North", "rough steppe"),
    ("Way Stone Graveyard (9)", "South-Facing Passage (11)", 3, "North-West", "rough steppe"),
    ("Way Stone Graveyard (9)", "Fallen Umber (12)", 1, "West", "trail"),

    # Death-Facing Passage (10)
    ("Death-Facing Passage (10)", "South-Facing Passage (11)", 2, "West", "steppe"),

    # South-Facing Passage (11)
    ("South-Facing Passage (11)", "Fallen Umber (12)", 1, "South", "steppe"),
    ("South-Facing Passage (11)", "Long Ridge & Behemoth (13)", 1, "North", "steppe"),

    # Fallen Umber (12)
    ("Fallen Umber (12)", "Moon-Facing Ford (14)", 2, "West", "trail"),

    # Long Ridge & Behemoth (13)
    ("Long Ridge & Behemoth (13)", "Moon-Facing Ford (14)", 2, "West", "steppe"),

    # Moon-Facing Ford (14)
    ("Moon-Facing Ford (14)", "Glass Bridge (15)", 2, "North-West", "steppe"),

    # Glass Bridge (15)
    ("Glass Bridge (15)", "The Gall Grass (16)", 1, "North-West", "old road"),

    # The Gall Grass (16)
    ("The Gall Grass (16)", "Ribs of the Father (17)", 1, "West", "lost road"),

    # Ribs of the Father (17)
    ("Ribs of the Father (17)", "The Iron Road (18)", 1, "West", "clear trail"),

    # The Iron Road (18)
    ("The Iron Road (18)", "The Ivory Plain (19)", 2, "North", "steppe"),
    ("The Iron Road (18)", "Dead Bridge (20)", 1, "West", "clear trail"),

    # The Ivory Plain (19)
    ("The Ivory Plain (19)", "Dark Light Passage (21)", 1, "North-West", "steppe"),
    ("The Ivory Plain (19)", "Dead Bridge (20)", 2, "South-West", "steppe"),

    # Dead Bridge (20)
    ("Dead Bridge (20)", "The Endless Houses (22)", 2, "West", "rubble trail"),

    # Dark Light Passage (21)
    ("Dark Light Passage (21)", "The Endless Houses (22)", 2, "West", "roads"),

    # The Endless Houses (22)
    ("The Endless Houses (22)", "The Black City (23)", 1, "North-West", "decaying boulevards"),
]

# Canonical UVG Entities and Hooks per Station (from UVG 2E Core)
CANON_STATION_LORE: Dict[str, Dict[str, Any]] = {
    "The Last Serai (8)": {
        "canon_entities": [
            {"name": "Angel 22-unity", "type": "character", "role": "High-ranking Porcelain Prince factor"},
            {"name": "Lacquer Stone 4-body", "type": "character", "role": "Dusty porcelain diplomat and courtier"},
            {"name": "Black Helmet 60-plurality", "type": "character", "role": "Aggrieved polybody caravan master and labour unionist"},
            {"name": "Pooki", "type": "character", "role": "Lazy, overpowered cat-lord chief of the Rainbow Serai"},
            {"name": "Iron Pot 6-body", "type": "character", "role": "Porcelain investigator hunted across the serai alleys"},
            {"name": "The Giving Cow", "type": "faction", "role": "Yellow-wood milk bar and quiet meeting place"},
            {"name": "Buried Delicatessen", "type": "location", "role": "Subterranean dining speakeasy serving Long-Long-Ago preserves"},
            {"name": "Deep-Coral Chambers", "type": "location", "role": "Submerged residential vaults beneath the static harmonic rods"},
            {"name": "Chamber of Crystal Rebirth", "type": "location", "role": "Vault housing the dormant Rebuilder (L17 biomancer)"},
        ],
        "road_hazards": ["Porcelain dust storms", "Choking toxic pollen", "Static electrical discharge", "Corporate body snatchers"],
    },
    "Way Stone Graveyard (9)": {
        "canon_entities": [
            {"name": "The Way Stone", "type": "location", "role": "Massive black basalt navigational obelisk emitting radio hums"},
            {"name": "Static Monolith Hermits", "type": "faction", "role": "Solitary ascetics bound to navigational beacons"},
            {"name": "Ghost Signals", "type": "creature", "role": "Sentient radio transmissions mimicking lost travellers"},
        ],
        "road_hazards": ["Violent magnetic shears", "Navigation compass inversion", "Disembodied machine whispers"],
    },
    "Death-Facing Passage (10)": {
        "canon_entities": [
            {"name": "The Face of Death", "type": "location", "role": "Gigantic petrified robotic visage carved into the mountain divide"},
            {"name": "Canyon Outriders", "type": "faction", "role": "Ruthless toll-keepers ambushing narrow gorge traverses"},
            {"name": "Katabatic Spectres", "type": "creature", "role": "Freezing wind elementals flaying exposed flesh"},
        ],
        "road_hazards": ["Lethal rockfalls", "Altitude sickness", "Radiation hotspots in shaded arroyos"],
    },
    "South-Facing Passage (11)": {
        "canon_entities": [
            {"name": "Cedar Grove Hermitage", "type": "location", "role": "Sanctuary of silence in deep cedar valleys"},
            {"name": "Lenticular Worms", "type": "creature", "role": "Endurance-draining parasites infesting mountain springs"},
        ],
        "road_hazards": ["Freezing katabatic night gales", "Parasite infection", "Disorienting mirages"],
    },
    "Potsherd Crater (5)": {
        "canon_entities": [
            {"name": "The Glass House of the Dead Prince", "type": "location", "role": "Intact crystal pavilion containing ancestral kaolin treasures"},
            {"name": "Feral Kaolin Golems", "type": "creature", "role": "Shattered ceramic servitors defending ceramic burial mounds"},
            {"name": "Ceramic Prospectors", "type": "faction", "role": "Dust-bitten scavengers sifting ancestral porcelain rubble"},
        ],
        "road_hazards": ["Razor-sharp ceramic shards", "Collapsing subterranean kiln vaults", "Toxic kaolin dust"],
    },
    "Grass Colossus (7)": {
        "canon_entities": [
            {"name": "The Sleeping Automaton", "type": "location", "role": "Derelict planetary maintenance colossus housing nomadic tent cities"},
            {"name": "Nomad Custodians", "type": "faction", "role": "Keepers of the sacred engine vents and ceremonial oil wells"},
        ],
        "road_hazards": ["Vomish parasite swarms", "Crushing interior piston seizures", "Pilgrim disputes"],
    },
    "Trail of Vomish Dreams (6)": {
        "canon_entities": [
            {"name": "The Riven Biomass", "type": "creature", "role": "Parasitic meat-and-circuit machine hiveminds"},
            {"name": "Signal Spire Sentinels", "type": "creature", "role": "Autonomous biological radar nodes relaying hunter broadcasts"},
        ],
        "road_hazards": ["Biomechanical infection", "Signal fever", "Night predatory vechs"],
    },
    "Fallen Umber (12)": {
        "canon_entities": [
            {"name": "Cerulean Five Oasis", "type": "location", "role": "Deep azure pool surrounded by petrified orange salt cliffs"},
            {"name": "Umber Sub-Bunkers", "type": "location", "role": "Sealed fallout vaults from the Third Age of Rainbow"},
        ],
        "road_hazards": ["Orange salt blindness", "Dehydration", "Vicious dust devils"],
    },
}


# -----------------------------------------------------------------------------
# Core Audit Functions
# -----------------------------------------------------------------------------

def audit_drive_sync() -> Dict[str, Any]:
    """Audit physical Google Drive files against references.json and _digests/."""
    results: Dict[str, Any] = {
        "drive_accessible": False,
        "indexed_sources": [],
        "unindexed_files": [],
        "missing_digests": [],
        "total_drive_files": 0,
    }

    if not DRIVE_DIR.exists():
        return results

    results["drive_accessible"] = True

    # Read active references.json
    indexed_map: Dict[str, Dict[str, Any]] = {}
    if REFERENCES_INDEX_PATH.exists():
        try:
            with open(REFERENCES_INDEX_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                for src in data.get("sources", []):
                    indexed_map[src.get("slug")] = src
        except Exception as e:
            results["references_error"] = str(e)

    results["indexed_sources"] = list(indexed_map.keys())

    # Scan Google Drive folder
    drive_files: List[Path] = []
    try:
        for root, dirs, files in os.walk(DRIVE_DIR):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d != "_digests"]
            for f in files:
                if not f.startswith(".") and not f.startswith("~"):
                    drive_files.append(Path(root) / f)
    except PermissionError:
        results["drive_permission_denied"] = True
        return results

    results["total_drive_files"] = len(drive_files)
    if len(drive_files) == 0 and DRIVE_DIR.exists():
        results["drive_permission_denied"] = True
        return results

    # Check which Drive files are indexed
    known_paths = {Path(s.get("source_pdf", "")) for s in indexed_map.values()}

    for fpath in drive_files:
        ext = fpath.suffix.lower()
        if ext in [".pdf", ".gdoc", ".gsheet"]:
            if fpath not in known_paths and fpath.name not in [p.name for p in known_paths]:
                action_hint = "Extract digest to `_digests/`"
                if fpath.name == "UVG-TradingGoods.gsheet":
                    action_hint = "Synced via `sync_trade.py` to `trading/`"
                elif fpath.name == "UVG-AtlesCaravan.gsheet":
                    action_hint = "Bridge ledger to caravan roster / `directory/Atles/`"

                results["unindexed_files"].append({
                    "name": fpath.name,
                    "rel_path": str(fpath.relative_to(DRIVE_DIR)),
                    "type": "spreadsheet" if ext == ".gsheet" else ("document" if ext == ".gdoc" else "sourcebook"),
                    "size_bytes": fpath.stat().st_size,
                    "action_hint": action_hint,
                })

    # Check which indexed sources are missing a physical digest file
    for slug, src in indexed_map.items():
        digest_file = Path(src.get("digest_path", DIGESTS_DIR / f"{slug}.md"))
        if not digest_file.exists():
            results["missing_digests"].append({
                "slug": slug,
                "title": src.get("title", slug),
                "expected_path": str(digest_file),
            })

    return results


def get_current_campaign_location() -> Dict[str, Any]:
    """Determine the caravan's current location from the latest session log."""
    info: Dict[str, Any] = {
        "latest_episode": None,
        "raw_region": None,
        "matched_station": "The Last Serai (8)",  # Canonical fallback
        "matched": False,
    }

    if not CAMPAIGNS_DIR.exists():
        return info

    episodes = sorted(CAMPAIGNS_DIR.glob("ep_*.md"), key=lambda p: p.name)
    if not episodes:
        return info

    latest = episodes[-1]
    info["latest_episode"] = latest.name

    try:
        content = latest.read_text(encoding="utf-8")
        # Extract region front matter
        region_match = re.search(r"^region:\s*(.+)$", content, re.MULTILINE)
        if region_match:
            raw_reg = region_match.group(1).strip()
            info["raw_region"] = raw_reg
            raw_lower = raw_reg.lower()

            for station_name, sdata in TRAIL_STATIONS.items():
                if any(alias in raw_lower for alias in sdata["aliases"]):
                    info["matched_station"] = station_name
                    info["matched"] = True
                    break
    except Exception as e:
        info["error"] = str(e)

    return info


def build_trail_adjacency() -> Dict[str, List[Dict[str, Any]]]:
    """Build adjacency list for the UVG trail network."""
    adj: Dict[str, List[Dict[str, Any]]] = {k: [] for k in TRAIL_STATIONS}

    # Inverse compass directions
    opposite_dir = {
        "West": "East", "East": "West",
        "North": "South", "South": "North",
        "North-West": "South-East", "South-East": "North-West",
        "North-East": "South-West", "South-West": "North-East",
    }

    for orig, dest, weeks, direction, terrain in TRAIL_CONNECTIONS:
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


def get_directory_status() -> Dict[str, Dict[str, Any]]:
    """Scan directory/ and catalog.json to identify existing location and entity notes."""
    status: Dict[str, Dict[str, Any]] = {}

    catalog_entries: List[Dict[str, Any]] = []
    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                catalog_entries = json.load(f).get("entries", [])
        except Exception:
            pass

    for station_name, sdata in TRAIL_STATIONS.items():
        folder_name = sdata.get("dir_folder")
        folder_path = DIRECTORY_DIR / folder_name if folder_name else None

        has_folder = folder_path.is_dir() if folder_path else False
        has_index = (folder_path / "index.md").is_file() if has_folder else False

        # Gather notes within this location folder
        child_notes: List[str] = []
        if has_folder and folder_path:
            child_notes = [p.stem for p in folder_path.glob("*.md") if p.name != "index.md"]

        # Check line count / content quality if index exists
        content_lines = 0
        has_trade_table = False
        if has_index and folder_path:
            try:
                txt = (folder_path / "index.md").read_text(encoding="utf-8")
                # Remove YAML
                body = re.sub(r"^---.*?---\s*", "", txt, flags=re.DOTALL)
                content_lines = len([l for l in body.splitlines() if l.strip()])
                has_trade_table = "Most profitable trade" in txt or "Location Price" in txt
            except Exception:
                pass

        note_state = "Untapped"
        if has_index:
            if content_lines < 8:
                note_state = "Stub"
            else:
                note_state = "Established"

        status[station_name] = {
            "state": note_state,
            "folder": str(folder_path.relative_to(REPO_ROOT)) if (has_folder and folder_path) else None,
            "child_entities": child_notes,
            "content_lines": content_lines,
            "has_trade_table": has_trade_table,
        }

    return status


def calculate_proximity_gaps(current_station: str, max_hops: int = 2) -> List[Dict[str, Any]]:
    """Calculate stations within max_hops from the current station using BFS."""
    adj = build_trail_adjacency()
    dir_status = get_directory_status()

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
                    new_path = path + [f"{edge['direction']} to {neighbour} ({edge['weeks']}w, {edge['terrain']})"]
                    queue.append((neighbour, hops + 1, total_weeks + edge["weeks"], new_path))

    # Sort results: first by hops, then by total_weeks
    results.sort(key=lambda x: (x["hops"], x["total_weeks"]))
    return results


def audit_untapped_factions(current_station: str, proximate_stations: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cross-reference canon entities with repository notes to surface unintroduced factions & NPCs."""
    dir_status = get_directory_status()
    catalog_titles: Set[str] = set()

    if CATALOG_PATH.exists():
        try:
            with open(CATALOG_PATH, "r", encoding="utf-8") as f:
                for entry in json.load(f).get("entries", []):
                    catalog_titles.add(entry.get("title", "").strip().lower())
                    # Also include base filename without extension
                    p = Path(entry.get("path", ""))
                    catalog_titles.add(p.stem.lower())
        except Exception:
            pass

    audit: Dict[str, Any] = {
        "current_station": {
            "name": current_station,
            "introduced": [],
            "untapped": [],
            "hazards": CANON_STATION_LORE.get(current_station, {}).get("road_hazards", []),
        },
        "proximate_untapped_entities": [],
    }

    # Check entities at current station
    curr_lore = CANON_STATION_LORE.get(current_station, {}).get("canon_entities", [])
    for ent in curr_lore:
        name_lower = ent["name"].lower()
        # Check if present in catalog or child notes
        is_known = any(name_lower in t or t in name_lower for t in catalog_titles)
        if not is_known and current_station in dir_status:
            is_known = any(name_lower in c.lower() for c in dir_status[current_station].get("child_entities", []))

        if is_known:
            audit["current_station"]["introduced"].append(ent)
        else:
            audit["current_station"]["untapped"].append(ent)

    # Check entities at proximate 1-hop and 2-hop stations
    for prox in proximate_stations:
        st_name = prox["station"]
        st_lore = CANON_STATION_LORE.get(st_name, {})
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


def run_gap_analysis(max_hops: int = 2) -> Dict[str, Any]:
    """Execute complete gap analysis and return structured findings."""
    drive_audit = audit_drive_sync()
    location_info = get_current_campaign_location()
    current_station = location_info.get("matched_station", "The Last Serai (8)")
    proximity_gaps = calculate_proximity_gaps(current_station, max_hops=max_hops)
    faction_audit = audit_untapped_factions(current_station, proximity_gaps)

    # Summary metrics
    untapped_locations = [p for p in proximity_gaps if p["state"] == "Untapped"]
    stub_locations = [p for p in proximity_gaps if p["state"] == "Stub"]
    established_locations = [p for p in proximity_gaps if p["state"] == "Established"]

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "current_caravan_location": {
            "station": current_station,
            "episode": location_info.get("latest_episode"),
            "raw_region": location_info.get("raw_region"),
            "is_established": get_directory_status().get(current_station, {}).get("state") == "Established",
        },
        "drive_sync": drive_audit,
        "proximity_analysis": {
            "radius_hops": max_hops,
            "total_proximate_stations": len(proximity_gaps),
            "untapped_count": len(untapped_locations),
            "stub_count": len(stub_locations),
            "established_count": len(established_locations),
            "stations": proximity_gaps,
        },
        "faction_audit": faction_audit,
    }


def format_markdown_report(data: Dict[str, Any]) -> str:
    """Format audit results as a crisp Markdown report in British English with blank lines under headings."""
    curr = data["current_caravan_location"]
    drive = data["drive_sync"]
    prox = data["proximity_analysis"]
    factions = data["faction_audit"]

    lines = [
        "# Campaign Coverage & Gap Analysis Report",
        "",
        f"> [!NOTE]",
        f"> Automated diagnostic audit generated on **{datetime.now().strftime('%d %B %Y at %H:%M')}**.",
        f"> Current caravan locus: **{curr['station']}** (identified from `{curr['episode']}`).",
        "",
        "## 1. Google Drive Sync & Sourcebook Indexing",
        "",
    ]

    if drive.get("drive_permission_denied"):
        lines.extend([
            "> [!WARNING]",
            "> Google Drive folder access was restricted by the environment sandbox during this run.",
            "> Terminal commands accessing CloudStorage require elevated sandbox execution.",
            "",
        ])
    elif not drive.get("drive_accessible"):
        lines.append("Google Drive directory could not be reached at the configured path.\n")
    else:
        unindexed = drive.get("unindexed_files", [])
        if unindexed:
            lines.extend([
                f"> [!IMPORTANT]",
                f"> **{len(unindexed)} unindexed file(s)** detected in Google Drive:",
                "",
                "| File Name | Location | Type | Action Needed |",
                "| :--- | :--- | :--- | :--- |",
            ])
            for u in unindexed:
                action = u.get("action_hint", "Extract digest to `_digests/`")
                lines.append(f"| `{u['name']}` | `{u['rel_path']}` | {u['type'].title()} | {action} |")
            lines.append("")
        else:
            lines.extend([
                "All core PDFs, supplements, and research documents in Google Drive are fully indexed in Tier 3 digests.",
                "",
            ])

        missing_dig = drive.get("missing_digests", [])
        if missing_dig:
            lines.extend([
                "### Missing Digest Files",
                "",
            ])
            for m in missing_dig:
                lines.append(f"- **{m['title']}**: Digest file not found at `{m['expected_path']}`.")
            lines.append("")

    lines.extend([
        "## 2. Trail Proximity & Untapped Locations",
        "",
        f"The caravan is currently anchored at **{curr['station']}**. Below is the status of all trail stations within **{prox['radius_hops']} hops**:",
        "",
        "| Destination | Hops | Travel Time | Directory State | Notes & Deficiencies |",
        "| :--- | :---: | :---: | :---: | :--- |",
    ])

    for st in prox["stations"]:
        badge = "🔴 **Untapped**" if st["state"] == "Untapped" else ("🟡 **Stub**" if st["state"] == "Stub" else "🟢 **Established**")
        notes = []
        if st["state"] == "Untapped":
            notes.append("No entry in `directory/`. Needs creation before expedition departs.")
        elif st["state"] == "Stub":
            notes.append("Folder exists but has under 8 lines of body content.")
        else:
            entity_count = len(st.get("child_entities", []))
            trade_status = "market table present" if st.get("has_trade_table") else "no market table"
            notes.append(f"{entity_count} entities documented; {trade_status}.")

        lines.append(f"| **{st['station']}** | {st['hops']} | {st['total_weeks']} week(s) | {badge} | {' '.join(notes)} |")

    lines.extend([
        "",
        "## 3. Untapped Factions, Patrons & Road Encounters",
        "",
        f"### Current Station: {curr['station']}",
        "",
    ])

    curr_untapped = factions["current_station"]["untapped"]
    curr_intro = factions["current_station"]["introduced"]

    if curr_intro:
        lines.append("**Introduced Entities:**")
        for ent in curr_intro:
            lines.append(f"- **{ent['name']}** ({ent['role']})")
        lines.append("")

    if curr_untapped:
        lines.extend([
            "**Untapped Canon Opportunities at this Station:**",
            "",
        ])
        for ent in curr_untapped:
            lines.append(f"- **{ent['name']}** ({ent['type'].title()}): {ent['role']}.")
        lines.append("")

    hazards = factions["current_station"].get("hazards", [])
    if hazards:
        lines.extend([
            "**Regional Environmental Hazards:**",
            "",
            f"- {', '.join(hazards)}.",
            "",
        ])

    prox_untapped = factions.get("proximate_untapped_entities", [])
    if prox_untapped:
        lines.extend([
            "### Immediate Horizon: Untapped Entities Along Adjacent Routes",
            "",
            "| Destination | Hop | Entity / Hook | Role |",
            "| :--- | :---: | :--- | :--- |",
        ])
        for p in prox_untapped:
            e = p["entity"]
            lines.append(f"| {p['station']} | {p['hops']} | **{e['name']}** ({e['type'].title()}) | {e['role']} |")
        lines.append("")

    lines.extend([
        "## 4. Recommended Next Steps for the GM",
        "",
        "1. **Draft `Way Stone Graveyard (9)`**: As the primary western overland route leading out of The Last Serai, create `directory/WayStoneGraveyard/index.md` with regional static hazard rules and trade pricing.",
        "2. **Introduce a Local Serai Patron**: Bring in **Lacquer Stone 4-body** or **Black Helmet 60-plurality** as a rival or employer in the hunt for Iron Pot's remaining body.",
        "3. **Bridge `UVG-AtlesCaravan.gsheet`**: Connect the party's active ledger and vehicle status to the campaign website.",
        "4. **Leverage Electric Bastionland Spark Tables**: Use the newly indexed Tier 3 digest (`_digests/electric_bastionland.md`) for industrial boroughs, dilemma traps, and living machines.",
        "",
    ])

    return "\n".join(lines).strip() + "\n"


# -----------------------------------------------------------------------------
# Main Entry Point
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Automated Gap Analysis for the Charged Campaign.")
    parser.add_argument("--radius", type=int, default=2, help="Proximity search radius in trail hops (default: 2)")
    parser.add_argument("--json", action="store_true", help="Output raw JSON data to stdout")
    parser.add_argument("--report-path", type=str, default=None, help="Save formatted Markdown report to a specific file")
    args = parser.parse_args()

    data = run_gap_analysis(max_hops=args.radius)

    if args.json:
        print(json.dumps(data, indent=2))
        return

    md_report = format_markdown_report(data)

    if args.report_path:
        out_file = Path(args.report_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(md_report, encoding="utf-8")
        print(f"[REPORT] Saved gap analysis report to {out_file}")
    else:
        print(md_report)


if __name__ == "__main__":
    main()
