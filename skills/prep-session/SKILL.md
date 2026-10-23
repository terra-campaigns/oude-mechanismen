---
name: prep-session
description: Guided session preparation procedure walking the GM through 8 structured steps (0-NOW to 7-MAP), integrating canon lore, character threads, and random spark tables.
argument-hint: none or upcoming session number/focus
---

# Session Prep

A structured, interactive procedure to prepare the next session of a campaign. The process walks the GM step-by-step through 8 distinct preparation phases, integrating canon lore, character threads, and random spark tables into a table-ready briefing.

## Guiding Principles

- **Iterative and Conversational**: Do not dump all steps in a single monolithic response. Guide the GM through each step one at a time, presenting options, incorporating their steer, and refining before advancing to the next step.
- **Canon Grounding**: Draw consistently from Tier 1 published notes (`campaigns/`, `directory/`), Tier 2 active rulings (`.agents/context/decisions.md`), and Tier 3 reference digests in `_digests/`.
- **Setting Flavour**: Align tone, hazards, and aesthetics with the `## Campaign Specification` in `.agents/AGENTS.md`.

## Step-by-Step Procedure

### Step 0 — NOW: Define Current Date & Location

- Establish the current campaign date based on the latest published session log front matter (`nav_order` in `campaigns/<Campaign>/ep_XXX.md`).
- Confirm the current physical location of the party (station sector, camp, settlement, or landmark).
- Note ambient conditions, party morale, and immediate time-sensitive countdowns.
- Prompt the GM to confirm or advance the calendar date and verify the campsite or anchor point.

### Step 1 — PCS: Review Characters & Elevate Lore

- Review the roster of player characters attending the upcoming session.
- Check their character notes in `directory/` and past session appearances.
- Identify open debt contracts, employer pressures, guild/corporate obligations, and personal agendas.
- Surface narrative hooks and stakes for each attending PC to engage them directly.

### Step 2 — IMR: In-Media-Res First Scene

- Design a punchy, atmospheric opening scene that thrusts the party immediately into action, tension, or dilemma.
- Elevate recently documented lore from recent session logs and local directory entries rather than starting in passive downtime.
- Craft the scene using sensory anchors and immediate stakes demanding a decision from the players.

### Step 3 — MIS: Regional Hazards & Misfortune Table

- Construct a tailored table of local hazards and misfortunes specific to the current location.
- **Expedition / Trail Mode**: Weather peculiarities, route hazards, animal stampedes, equipment fatigue.
- **Station / Facility Mode**: Environmental malfunctions (depressurisation, radiation leaks, electrical arcs, bulkheads locking, airlock failures).
- Ensure each entry has concrete consequences: ability hindrances, gear damage, supply loss, or escalating danger.

### Step 4 — ENC: d6 Encounters Table (Small Tables Framework)

- Build a focused d6 encounter table employing the Small Tables framework.
- **Interactive Guidance Rule**: Never generate the entire table at once. Guide the GM interactively tier-by-tier:
  - **1: Rare** — an exceptional oddity, apex threat, reality-distorting anomaly, or singular wandering eccentric. Present 2–3 evocative seeds; let the GM select or refine before advancing.
  - **2–3: Uncommon** — distinct regional factions, corporate squads, or rival groups.
  - **4–6: Common** — environmental baseline, local lifeforms, or workplace hazards.

### Step 5 — SEEDS: 3 Forward Scenario Seeds

- Present 3 distinct, actionable scenario hooks or jobs available at this location.
- Connect each seed to existing NPCs, corporate rivals, or regional mysteries.

### Step 6 — DILEMMA: The Hard Choice

- Formulate a central operational or moral dilemma for the session where every option carries tangible trade-offs (ICI Doctrine: Information, Choice, Impact).

### Step 7 — MAP: Route or Sector Geometry

- Summarise the local spatial layout: adjacent sectors, trail stations, choke points, or salvage opportunities.

## Output

Once all steps are agreed with the GM, compile the complete briefing into a clean Markdown artifact for table use.
