---
name: weave-threads
description: Analyse published campaign content, active rulings, reference lore, and economic or factional anomalies to surface up to 3 actionable tie-ins for future sessions. Discover lore iteratively with the GM. Reads the entire repo context.
argument-hint: none (reads full repo) or optional focus topic / trade good / faction
---

# Weave Threads

Read the full campaign corpus, reference digests, and campaign data to find latent connections, forgotten threads, economic or factional anomalies, and lore opportunities. Produce up to 3 actionable suggestions for future sessions, working iteratively with the GM.

## Before starting: confirm with the user

When invoked, briefly confirm:

> I'll read all campaign content, rulings, and reference digests to find latent tie-ins. This will take a moment. Proceed?

If the user provided a specific topic, faction, trade good, or character, confirm focusing on that area. Then begin.

## Files to read

### Repo context (Tier 1 & Tier 2)

- `.agents/AGENTS.md` — setting rules, tone, canon hierarchy.
- `.agents/context/catalog.json` — inspect all entities, parents, types, and connection graphs (`links_in` / `links_out`).
- `.agents/context/decisions.md` — active Tier 2 rulings.
- If `trading/index.md` exists: read active trade goods, price multipliers, and market conditions (taboos, bubbles, crises, gluts).
- Targeted reads on specific session logs in `campaigns/` and entity notes in `directory/`.

### Reference digests (Tier 3 canon)

- Consult `.agents/context/references.json` to find relevant digest files and sections matching the party's current location, trajectory, and encounters.

## What to produce

### 1. Thread suggestions (up to 3)

Each suggestion should be:

- **Actionable** — something the GM can introduce in the next 1–3 sessions.
- **Grounded** — rooted in content that already exists in published notes, rulings, reference digests, or trade ledgers.
- **Connective** — it ties together two or more things that are currently unlinked or underused. Preference order:
  1. Connections between recent sessions and older published material (e.g. an element from early episodes that could resurface now).
  2. Economic anomalies or factional friction that reveal hidden lore (e.g. sudden markups, desperate resource shortages, corporate embargoes, or contraband restrictions).
  3. Connections between published notes and reference lore (e.g. an upcoming location, facility, or faction that intersects the party's path).
  4. NPCs or locations in the directory with empty `links_in` (no session appearances).
  5. Active PC situations, debt contracts, or unresolved personal stakes.

#### Format for standard narrative suggestions:

- **Title** — a short, evocative name for the thread.
- **The connection** — what existing elements it ties together, with file links.
- **The hook** — how the GM could introduce it at the table (one or two sentences, in-voice).
- **Source** — whether this draws from published notes, reference digests, or a combination.

#### Format for economic / anomaly suggestions:

- **Title** — an evocative name for the commercial, salvage, or resource thread.
- **The anomaly** — item, price multiplier/divergence, corporate blockade, or market condition.
- **The underlying lore** — the narrative reason for the distortion (faction hoarding, technological necessity, cult prohibition, impending catastrophe).
- **The table hook** — how the party encounters this (merchant rumours, salvage orders, customs inspections, desperate buyers).
- **Source** — link to the trade note, faction entry, or reference digest.

### 2. Iterative lore discovery from anomalies

When an identified anomaly (price skew, resource crisis, or sudden military mobilization) exposes an unmapped aspect of the setting, do not lock in canon unilaterally. Instead, run an iterative brainstorm with the GM:

1. **Highlight the anomaly**: Present the resource/trade good, location disparity, and any special condition (`Crisis Demand`, `Market Bubble`, `Taboo`, `Corporate Embargo`).
2. **Offer 2–3 lore hypotheses**: Present distinct, evocative, setting-faithful explanations for why the distortion exists (e.g. Option A: covert requisition by a megacorporation; Option B: sabotage or ecological collapse; Option C: cult ritual or synthetic awakening).
3. **Solicit GM steer**: Ask the GM which hypothesis fits best, or invite them to tweak or combine elements.
4. **Consolidate**: Once agreed, weave the chosen lore into the session threads and record any firm table ruling in `.agents/context/decisions.md` if the GM confirms it.

### 3. Discovered tie-ins (optional)

If you find connections that already exist in the fiction but are not reflected in the file structure (e.g. an NPC mentioned in a session log who lacks a backlink from their directory entry, or two locations that are clearly related but not cross-linked), list them and **add the missing relative links directly to the files**.

Format link additions the same way existing links are formatted in the repo (relative paths with `.md` extensions). Only add links where the connection is clearly established in the text — do not invent connections.

## Procedure

1. Read `.agents/AGENTS.md`.
2. Inspect `.agents/context/catalog.json` and `.agents/context/decisions.md`.
3. Check `trading/index.md` (if present) for price skews or market anomalies.
4. Check recent session logs in `campaigns/` using line ranges for recent developments.
5. Consult Tier 3 digests via `.agents/context/references.json`.
6. Build a mental map of active PCs, unresolved contracts, unvisited directory locations, and NPCs with empty `links_in`.
7. If exploring market or economic anomalies, engage the GM iteratively with 2–3 potential lore explanations before locking in the final thread.
8. Identify the strongest thread candidates (up to 3) and rank by natural fit and depth.
9. Write the output as an artifact (markdown file) and present it to the user.
10. If discovered tie-ins require link additions, edit the relevant files directly for user review.

## Rules

- Never invent new canon unilaterally. Every suggestion must be grounded in existing repo content, reference digests, or confirmed rulings.
- Treat anomaly hypotheses as Tier 3 possibilities until the GM selects or refines them in conversation.
- Do not spoil content the party hasn't encountered yet by writing it into session logs. Suggestions go into the artifact.
- Suggestions should feel like they were always there, waiting to be noticed — not bolted on.
- Keep the artifact concise: 3 suggestions max, each no longer than a short paragraph.
- When adding links to files, follow existing formatting conventions exactly.
