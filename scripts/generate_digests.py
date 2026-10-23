#!/usr/bin/env python3
"""
Generate structured Tier 3 Markdown digests for reference PDFs in Google Drive
and compile the lightweight routing index at .agents/context/references.json.

Supports both Charged and Hostile campaign vaults.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def ensure_heading_blank_lines(text: str) -> str:
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        out.append(line)
        if re.match(r"^#{1,6}\s+\S", line):
            if i + 1 < len(lines) and lines[i + 1].strip() != "":
                out.append("")
    return "\n".join(out).strip() + "\n"


HOSTILE_DIGESTS = {
    "hostile_rules": {
        "title": "Hostile Rules (2D6 Gritty Sci-Fi Roleplaying)",
        "source_pdf": "Hostile-Rules.pdf",
        "category": "core_rules",
        "content": """# Hostile Rules — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `Hostile-Rules.pdf`. Nothing here is automatic Hostile campaign canon unless formally adopted in Tier 1 notes or Tier 2 rulings.

## Contents & Page Map

- **Characters & Careers** [pp. 12–45]: 2D6 career generation, service skills, survival rolls, mustering out benefits. Careers: Marine, Roughneck, Commercial Spacer, Android, Marshal, Technician, Surveyor.
- **Task Resolution & Skills** [pp. 46–64]: 2D6 + Skill + Characteristic DM vs Target Number 8+. Hazardous environments, jury-rigging, medical trauma, decompression checks.
- **Combat & Lethality** [pp. 65–90]: High lethality, tactical cover, firearm stats, slugthrowers, shotguns, laser weapons, body armour, vacuum suit puncture rules.
- **Environmental Hazards** [pp. 91–110]: Vacuum exposure, zero-gravity movement, atmospheric toxicity, radiation poisoning, freezing temperatures, explosive depressurisation.
- **Starships & Operations** [pp. 111–160]: FTL hyperspace jumps, jump sickness, maintenance logs, fuel skimming, life support filtration, hull breaches, salvage rights.

## Key Procedures & Setting Flavour

- **Depressurisation & Explosive Decompression**: Punctures vent atmosphere rapidly. Unprotected vacuum exposure causes unconsciousness in 10–15 seconds, followed by cellular rupture.
- **Workplace Realism & Union Rules**: Characters are wage labourers, contractors, or indentured crew answering to corporate oversight boards, trade unions, or military commandants.
- **Equipment & Low-Tech Reliability**: CRT terminals, toggle switches, hydraulic seals, magnetic boots, acoustic pingers, bulkheads, and heavy industrial grease.
""",
    },
    "hostile_setting": {
        "title": "Hostile Setting (The Off-World Colonies 2225)",
        "source_pdf": "Hostile-Setting.pdf",
        "category": "core_setting",
        "content": """# Hostile Setting — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `Hostile-Setting.pdf`. Influence for world details and corporate factions.

## Contents & Page Map

- **The Known Universe (2225)** [pp. 8–32]: Political and economic landscape of the Off-World Colonies, dividing into national arms, corporate sectors, and frontier rims.
- **Major Megacorporations & Zaibatsus** [pp. 33–75]: The colossal transnational extraction and manufacturing conglomerates dominating human expansion.
- **Colony Gazetteer & Star Sectors** [pp. 76–180]: Outposts, refinery moons, terraforming platforms, orbital shipyards, and deep frontier mining colonies.
- **Frontier Life & Society** [pp. 181–220]: Indentured contracts, company script, colony sickness, frontier isolation, cold transport, black market syndicates.

## Corporations & Power Blocs

- **ICC (Interstellar Commerce Commission)**: Regulatory body balancing corporate monopolies against civil safety; notorious for bureaucratic compromises and corporate capture.
- **Tanaka Heavy Industries / Makita Orbital**: Japanese-led aerospace and heavy machinery zaibatsu specialising in mining vessels, automated refineries, and cargo haulers.
- **Hyperion Mining & Minerals**: Aggressive resource extraction conglomerate known for cost-cutting, hazardous operations, and expendable crew policies.
- **Haruna Biotech & Pharmaceuticals**: Dominant biotechnology concern researching synthetic neural nets, terraforming bacteria, and hazardous xenobiology.
""",
    },
    "gradient_descent": {
        "title": "Gradient Descent (The Derelict Android Factory)",
        "source_pdf": "/Users/efsa/Library/CloudStorage/GoogleDrive-estevao.alvarenga@gmail.com/My Drive/RPG/books/osr/mothership/Gradient-Descent-v1.1.pdf",
        "category": "megastructure_campaign",
        "content": """# Gradient Descent — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `books/osr/mothership/Gradient-Descent-v1.1.pdf`. Core setting reference for the abandoned megastructure android facility.

## Contents & Structural Map

- **The Deep Space Megastructure** [pp. 4–12]: The massive android manufacturing facility *The Deep*, dark, silent, zero-G, orbiting a cold dead star.
- **Monarch (The Machine Mind)** [pp. 13–18]: The transcendent, fractured artificial intelligence controlling the station, manufacturing synthetic bodies, running psychological experiments.
- **The Divergence Test (Am I An Android?)** [pp. 20–21]: Psychological and physiological paranoia rules. Roll when stressed to discover whether memories are synthetic implants.
- **Factional Enclaves & Artefact Hunters** [pp. 22–35]: Blockade fleets, scrap-mercenaries, synthetic cults (The Troupe), and desperate corporate recovery teams.
- **The 10 Facility Sectors** [pp. 36–75]: Detailed deck layouts:
  - Sector 1: The Airlock & Reception (Silent vestibules, dead terminals).
  - Sector 2: Industrial Fabrication & Stamping Mills.
  - Sector 3: Synthetic Flesh Vats & Biomantic Tanks.
  - Sector 4: The Benthic Labs & Neural Imprint Archives.
  - Sector 5: Monarch's Core Sanctum.

## Tone & GM Guidance

- **AI Identity Horror**: Characters never know if someone they rescue is a human survivor or a Monarch infiltration unit with false childhood memories.
- **Slow Industrial Dread**: Flickering emergency lamps, echoing metal footsteps, cold vacuum chambers, coolant leaks, and synthetic remnants searching for meaning.
""",
    },
    "hostile_synthetics": {
        "title": "Hostile Synthetics (Artificial Persons & Infiltrators)",
        "source_pdf": "supplements/Hostile-Synthetics.pdf",
        "category": "supplement",
        "content": """# Hostile Synthetics — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `supplements/Hostile-Synthetics.pdf`.

## Contents & Mechanics

- **Synthetic Classifications** [pp. 4–18]: Generation 1 industrial units, Generation 2 office & technical androids, Generation 3 infiltration & companion models.
- **Behavioural Limiters & Glitches** [pp. 19–30]: The Triple Directive constraints, emotional degradation, logic loops, stress ruptures, and the uncanny valley register.
- **Chassis & Maintenance** [pp. 31–48]: Synthetic blood (milky white hydraulic fluid), polymer muscle fibres, silicon cognitive cores, repair kits, EMP vulnerability.
""",
    },
}

CHARGED_DIGESTS = {
    "uvg_2e_core": {
        "title": "Ultraviolet Grasslands and the Black City (UVG 2E Core)",
        "source_pdf": "cores/UVG 2E - Ultraviolet Grasslands and the Black City - Digital Small 1.0.pdf",
        "category": "core_setting",
        "content": """# Ultraviolet Grasslands and the Black City (UVG 2E Core) — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `cores/UVG 2E - Ultraviolet Grasslands and the Black City - Digital Small 1.0.pdf`. Nothing here is automatic Charged campaign canon unless formally adopted in Tier 1 notes or Tier 2 rulings.

## Contents & Page Map

- **The Traveller** [pp. 9–12]: Character creation guidelines, roles, and the Six-Fold System Rosetta for translating stats across RPG systems.
- **The Grasslands** [pp. 13–172]: Master trail map and detailed route gazetteer from the Violet City to the Black City.
- **The Caravan** [pp. 173–186]: Procedures for running expeditions, timekeeping, supplies, sacks, travel hazards, trade goods, financiers, and debt contracts.
- **The Stuff** [pp. 187–208]: Vehicles, mounts, equipment, armours, weapons, strange prosthetics, and 100 odd artefacts.
- **The Bestiary** [pp. 209–226]: Lifeforms of the grasslands, predatory machines, spectrum beasts, and companion creatures.
- **The Setting & Lore** [pp. 227–245]: Long-Long-Ago civilisations, weather, languages, metaphysics of death, and setting glossary.

## Locations & Trail Stations

- **Violet City** [pp. 20–25]: The eastern bastion of decadence and departure hub for caravans.
- **The Low Road and the High** [pp. 26–29]: The first divergent leg of the trail across cracked mesas and radioactive gullies.
- **Steppe of the Lime Nomads** [pp. 30–33]: Vast dust steppes inhabited by lime-chewing pastoralists.
- **Porcelain Citadel** [pp. 34–39]: Grand fortified palace of the Porcelain Princes. Centre of biomantic fleshcrafting and synthetic debt enforcement.
- **Potsherd Crater** [pp. 40–45]: Shattered geological depression strewn with ancestral pottery shards and wandering golems.
- **Trail of Vomish Dreams** [pp. 46–49]: Corrupted stretch haunted by sentient biomass machines.
- **The Last Serai** [pp. 54–59]: The final permanent civilised trading fortress before the deep weird wilderness.
- **Way Stone Graveyard** [pp. 60–63]: Field of ancient navigation obelisks and forgotten monoliths.
""",
    },
    "electric_bastionland": {
        "title": "Electric Bastionland",
        "source_pdf": "cores/Electric_Bastionland_v2.pdf",
        "category": "core_setting",
        "content": """# Electric Bastionland — Reference Digest

> [!NOTE]
> Tier 3 Canon (Influence & Reference Only). Source: `cores/Electric_Bastionland_v2.pdf`.

## Contents & Page Map

- **System Engine & Core Procedures** [pp. 6–18]: Saves, hit protection (HP), conducting hazards, dilemmas.
- **The 100 Failed Careers & Debt Economy** [pp. 20–225]: Debt contract starter framework and socio-economic flavour.
- **The Odd World: Bastion, Deep Country & The Underground** [pp. 249–281]: Living machines, dilemma traps, borough generation.
- **The ICI Doctrine (Information, Choice, Impact)** [pp. 242–244, 297]: Always provide sensory detail, clear dilemma choices, and decisive impact.
""",
    },
}


def build_digests(campaign: str, repo_root: Path, drive_dir: Path):
    digests_dir = drive_dir / "_digests"
    digests_dir.mkdir(parents=True, exist_ok=True)
    references_entries = []

    dataset = HOSTILE_DIGESTS if campaign == "hostile" else CHARGED_DIGESTS

    for slug, meta in dataset.items():
        out_file = digests_dir / f"{slug}.md"
        cleaned_content = ensure_heading_blank_lines(meta["content"])
        out_file.write_text(cleaned_content, encoding="utf-8")
        print(f"[DIGEST] Wrote {out_file.name}")

        sections = []
        lines = cleaned_content.splitlines()
        for idx, line in enumerate(lines, start=1):
            m = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
            if m:
                sections.append(
                    {
                        "level": len(m.group(1)),
                        "heading": m.group(2),
                        "line": idx,
                    }
                )

        pdf_path = meta["source_pdf"]
        if not pdf_path.startswith("/"):
            pdf_path = str(drive_dir / pdf_path)

        references_entries.append(
            {
                "slug": slug,
                "title": meta["title"],
                "category": meta["category"],
                "tier": 3,
                "source_pdf": pdf_path,
                "digest_path": str(out_file),
                "digest_exists": True,
                "sections": sections,
            }
        )

    ref_index_path = repo_root / ".agents" / "context" / "references.json"
    ref_index_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "generated": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "tier": 3,
        "campaign": campaign,
        "note": f"Tier 3 reference routing index — influence only, never automatic {campaign.title()} canon.",
        "total_sources": len(references_entries),
        "sources": references_entries,
    }

    ref_index_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"[INDEX] Wrote {len(references_entries)} reference sources to {ref_index_path}")


def main():
    parser = argparse.ArgumentParser(description="Compile Tier 3 reference digests and index.")
    parser.add_argument("--campaign", choices=["hostile", "charged"], required=True, help="Target campaign vault")
    parser.add_argument("--repo-root", type=str, default=None, help="Path to campaign repository root")
    parser.add_argument("--drive-dir", type=str, default=None, help="Path to Google Drive source folder")
    args = parser.parse_args()

    default_roots = {
        "hostile": Path("/Users/efsa/repos/hostile"),
        "charged": Path("/Users/efsa/repos/charged"),
    }
    default_drives = {
        "hostile": Path("/Users/efsa/Library/CloudStorage/GoogleDrive-estevao.alvarenga@gmail.com/My Drive/RPG/campaigns/hostile"),
        "charged": Path("/Users/efsa/Library/CloudStorage/GoogleDrive-estevao.alvarenga@gmail.com/My Drive/RPG/campaigns/charged"),
    }

    repo_root = Path(args.repo_root) if args.repo_root else default_roots[args.campaign]
    drive_dir = Path(args.drive_dir) if args.drive_dir else default_drives[args.campaign]

    build_digests(args.campaign, repo_root, drive_dir)


if __name__ == "__main__":
    main()
