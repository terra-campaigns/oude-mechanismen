# Route Graph Audit — Issue #29

## Question

Is `.agents/context/route_graph.json` a legacy artefact redundant with `catalog.json` / progressive retrieval, or does it serve a unique purpose?

## Findings

- **Engine usage**: only `scripts/audit_coverage.py` reads it — `load_route_graph()` (line 88) optionally loads `.agents/context/route_graph.json` and feeds the *Geographic Proximity & Destination Gaps* section of `oude audit` (`build_adjacency`, `calculate_proximity_gaps`, `get_directory_status`, `audit_untapped_factions`). When absent, the audit degrades gracefully (`route_graph_available: false`, section skipped) — verified against the `hostile` vault, which has no graph.
- **Vault usage**: `charged` maintains a populated graph and its `oude audit` reports `Matched Station` plus proximity gaps; `hostile` has none and audits clean without it.
- **Scaffolding**: `oude init` still copies `templates/route_graph.json.template` → `.agents/context/route_graph.json` (`src/oude_mechanismen/cli.py:52`).
- **No overlap with `catalog.json`**: the catalogue indexes note metadata and links; the route graph encodes station topology (stations, aliases, connections, `station_lore`) used for hop-distance analysis. Different data, different consumer.

## Verdict

**Not redundant — keep.** It serves a unique purpose (proximity/gap analysis in `oude audit`) with a live consumer (`charged`). Maintenance is justified: one optional loader, graceful degradation when absent.

## Actions taken

- Purpose documented in `AGENTS.md` (Canon & Context Architecture).
- Regression test added for the proximity logic (`tests/test_audit_coverage.py`).
