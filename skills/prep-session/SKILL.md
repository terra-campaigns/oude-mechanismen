---
name: prep-session
description: Guided session preparation procedure walking the GM through 8 structured steps (0-NOW to 7-MAP), combining campaign lore, character threads, and random spark tables.
argument-hint: none or upcoming session number/focus
---

# Session Prep

A structured, interactive procedure to prepare the next session of a campaign. The process walks the GM step-by-step through 8 distinct preparation phases, integrating canon lore, character threads, and random spark tables into a table-ready briefing.

## Guiding Principles

- **Iterative and Conversational**: Do not dump all steps in a single monolithic response. Guide the GM through each step one at a time, presenting options, incorporating their steer, and refining before advancing to the next step.
- **Canon Grounding**: Draw consistently from Tier 1 published notes (`campaigns/`, `directory/`), Tier 2 active rulings (`.agents/context/decisions.md`), and Tier 3 reference digests in `_digests/`.
- **Setting Flavour**: Align tone, hazards, naming conventions, and aesthetics with the `## Campaign Specification` in `.agents/AGENTS.md`.

## Step-by-Step Procedure

### Step 0 — NOW: Define Current Date & Location

- Establish the current campaign date based on the latest published session log front matter (`nav_order` in `campaigns/<Campaign>/ep_XXX.md` or `<NNN>.md`).
- Confirm the current physical location of the party (station sector, campsite, district, or landmark).
- Note ambient conditions, party morale, and immediate time-sensitive countdowns or resting requirements.
- Prompt the GM to confirm or advance the calendar date and verify the campsite or anchor point.
- **Monthly Faction Turn Trigger**:
  - Compare the newly advanced session date with the previous session date.
  - Whenever the new date starts or crosses into a new in-world calendar month (e.g. month rollover or new monthly cycle), prompt and guide the GM to run a **Faction Turn**:
    1. Identify active regional factions, corporate cartels, rival expeditions, patrons, and dominant powers from `directory/` and Tier 1 notes.
    2. Adjudicate their off-screen goals, asset movements, supply hoarding, territorial shifts, or escalating conflicts.
    3. Document and report the faction turn results directly into **Tier 2 lore** (`.agents/context/decisions.md` under `## Active Rulings` as `- **YYYY-MM-DD — Faction Turn (<Month Year>):** <summary of moves, asset shifts, and emerging consequences>`).
    4. Feed the resulting faction developments directly into character pressures (Step 1), uncommon encounters (Step 4), and local rumours (Step 6).

### Step 1 — PCS: Review Characters & Elevate Lore

- Review the roster of player characters attending the upcoming session.
- Check their character notes in `directory/` and past session appearances.
- Apply `weave-threads` logic:
  - Identify open debt contracts, employer or corporate pressures, guild obligations, or indenture terms.
  - Elevate physical conditions, traumas, injuries, cybernetics, or mutations.
  - Surface personal agendas, background secrets, and active commercial or factional interests intersecting the current location.
- Present tailored narrative hooks and stakes for each attending PC to engage them directly.

### Step 2 — IMR: In-Media-Res First Scene

- Design a punchy, atmospheric opening scene that thrusts the party immediately into the middle of action, tension, or dilemma.
- Elevate recently documented or discovered lore from recent session logs and local directory entries rather than starting in passive downtime.
- Craft the scene using sensory anchors (smells, tactile grit, acoustics, atmospheric pressure) and immediate stakes demanding a decision or reaction from the players.

### Step 3 — MIS: Regional Hazards & Misfortune Table

- Construct a tailored table of local hazards and travel misfortunes specific to the current location.
- **Expedition / Trail Mode**: Weather peculiarities, route hazards, toxic dusts, animal stampedes, equipment fatigue.
- **Station / Facility Mode**: Environmental malfunctions (depressurisation, radiation leaks, electrical arcs, bulkheads locking, toxic coolant leaks, airlock failures).
- Ensure each entry has concrete consequences suited to the game system: ability hindrances, gear damage, supply loss, temporal delays, or escalating danger.

### Step 4 — ENC: d6 Encounters Table (Small Tables Framework)

- Build a focused d6 encounter table employing the Small Tables framework.
- **Interactive Guidance Rule**: Never generate the entire table at once. Guide the GM interactively tier-by-tier:
  - **1: Rare** — an exceptional oddity, apex predator/threat, reality-distorting anomaly, or singular wandering eccentric. Present 2–3 evocative seeds from reference digests; let the GM select or refine before advancing.
  - **2–3: Uncommon** — distinct regional factions, corporate squads, rival haulers, or local enclaves. If a Monthly Faction Turn was triggered in Step 0, directly integrate active faction manoeuvres and territorial shifts into these encounters. Inquire whether the GM wants two contrasting factions or two distinct aspects/squads of a single faction.
  - **4–6: Common (Forward Levers)** — environmental baseline and local life. Preferentially structure these as active **propulsive levers** pulling the party toward further locations, stations, or sectors (e.g. distress calls, delivery contracts, or competing salvage teams).
- **Dynamic Weave-Threads Integration**: If faction motivations or economic reasons for movement are underspecified, offer to run `weave-threads` midway through prep to unearth latent lore before locking in the encounters.
- Format each entry with two clear components:
  1. **Who/What is it?** (Sensory appearance, strange physical or biological trait).
  2. **What are they doing right now?** (Current activity, urgent motivation, or active predicament).

### Step 5 — ALR: Artefact, Landmarks & Routes (1-2-3)

Prepare a tripartite discovery dossier for the location:

1. **1 Artefact**: An ancient relic, machine component, synthetic prototype, or oldtech curiosity available through salvage, trade, or discovery. Follow any setting naming protocol declared in `AGENTS.md` (e.g. Gene Wolfe four-phase naming protocol, or industrial serial numbers).
2. **2 Landmarks**: Two evocative local landmarks, architectural ruins, derelict chambers, or natural curiosities drawn from reference text or the local directory to serve as navigational beacons or exploration targets.
3. **3 Routes & In-Location Movement Helper**:
   - **In-Location Movement Helper**: A generic, modular environmental helper for navigating within the camp, station, or settlement during local hazards (visibility limits, hazard mechanics, security checks), strictly excluding encounters so they remain managed by the encounter table.
   - **3 Outward Routes**: Three distinct routes, corridors, or transit paths leading out of the location, specifying travel time, terrain or hazard ratings, resource demands, and potential rewards.

### Step 6 — INF: d6 Table of Information & Rumours

- Construct a d6 table of actionable clues, overheard rumours, intercepted comms, maintenance logs, market tips, and warnings to feed to the players across the session.
- Weave together:
  - Recent campaign developments and faction schemes (including off-screen developments established during the monthly faction turn).
  - Arbitrage intelligence, corporate directives, or salvage tips.
  - Unexplored sector hazards or mythic destination hints.
  - Half-truths, eerie warnings, and merchant exaggerations.

### Step 7 — MAP: Map Updates & Cartography

- Guide the GM through verifying and updating the campaign maps and spatial records:
  - Check party markers and route progress on VTT maps (e.g. Owlbear Rodeo room or sector schematics).
  - Verify directory backlinks and location links between the current position, visited landmarks, and prospective routes.
  - Create or update any required stub notes in `directory/` for newly established landmarks or waypoints.

## Session Prep Artifact

Once all steps are agreed with the GM, compile the complete briefing into a clean Markdown artifact or note (e.g. `campaigns/<Campaign>/prep_ep_XXX.md`) formatted for quick reference behind the GM screen during play.
