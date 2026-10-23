---
name: weave-threads
description: Analyse published campaign content, active rulings, reference lore, and economic/factional data to surface up to 3 actionable tie-ins for future sessions. Reads the entire repo context.
argument-hint: none (reads full repo) or optional focus topic / faction
---

# Weave Threads

Read the full campaign corpus, reference digests, and campaign data to find latent connections, forgotten hooks, economic or factional anomalies, and lore opportunities. Produce up to 3 actionable suggestions for future sessions, working iteratively with the GM.

## Before starting: confirm with the user

When invoked, briefly confirm:

> I'll read all campaign content, rulings, and reference digests to find latent tie-ins. This will take a moment. Proceed?

If the user provided a specific topic, faction, or character, confirm focusing on that area. Then begin.

## Files to read

### Repo context

- `.agents/AGENTS.md` — setting rules, tone, canon hierarchy.
- `.agents/context/catalog.json` — inspect all entities, parents, types, and connection graphs (`links_in` / `links_out`).
- `.agents/context/decisions.md` — active Tier 2 rulings.
- `.agents/context/references.json` — Tier 3 reference digests.
- Check if `trading/index.md` exists: if present, read for trade goods and price anomalies.

## What to look for

### 1. Actionable threads (up to 3)

Look for intersections across:
1. Locations visited vs locations documented in `directory/` with zero session appearances.
2. NPCs with empty or low `links_in` in `catalog.json` who share affiliations with active PCs.
3. Faction rivalries or corporate friction that could intersect the party's current location.
4. Active PC contracts, debts, and unresolved personal dilemmas.
5. In trading campaigns: extreme price skews or contraband restrictions.

For standard narrative suggestions, provide:
- **Title** — a short, evocative name for the thread.
- **The connection** — what existing elements it ties together, with file links.
- **The hook** — how the GM could introduce it at the table (one or two sentences, in-voice).
- **Source** — whether this draws from repo notes, reference digests, or a combination.

### 2. Discovered tie-ins (optional)

If you find connections that already exist in the fiction but are not reflected in the file structure (e.g. an NPC mentioned in a session log who lacks a backlink, or two locations that are clearly connected but not linked), list them and add the missing relative links directly to the files.

## Procedure

1. Read `.agents/AGENTS.md`.
2. Inspect `.agents/context/catalog.json` and `.agents/context/decisions.md`.
3. Check recent session logs in `campaigns/` using line ranges for recent developments.
4. Consult Tier 3 digests via `.agents/context/references.json`.
5. Identify the strongest thread candidates (up to 3) and rank by how naturally they emerge from the current situation.
6. Write the output as an artifact (markdown file) and present it to the user.
7. If discovered tie-ins require link additions, edit the relevant files directly.

## Rules

- Never invent new canon unilaterally. Every suggestion must be grounded in existing repo content, reference digests, or confirmed rulings.
- Do not spoil content the party hasn't encountered yet by writing it into session logs. Suggestions go into the artifact.
- Keep the artifact concise: 3 suggestions max.
