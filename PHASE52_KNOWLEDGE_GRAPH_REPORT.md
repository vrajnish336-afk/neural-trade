# PHASE 52 KNOWLEDGE GRAPH REPORT

## 1. Graph Architecture
The Knowledge Relationship Graph operates as a deterministic overlay on top of the Phase 31 `EvidenceGraphRepository`. Instead of maintaining a disconnected semantic database (like Neo4j or a Vector DB), we directly extended the `NodeType` and `EdgeRelationship` Enums in Phase 31 to support Knowledge-level connections.

## 2. Phase 31 and Phase 51 Reuse
- **Phase 31 (Evidence Graph):** `save_node()`, `save_edge()`, `get_nodes()`, and `get_edges_for_node()` provide the full traversal architecture. 
- **Phase 51 (Knowledge Intelligence):** `ResearchKnowledgeClaim`, `KnowledgePattern`, and `KnowledgeGap` are the fundamental inputs that map to Phase 31 `KNOWLEDGE_CLAIM`, `KNOWLEDGE_PATTERN`, and `RESEARCH_GAP` nodes.

## 3. Node Model
Reused `EvidenceNode`. New allowable types:
- `KNOWLEDGE_CLAIM`
- `KNOWLEDGE_PATTERN`
- `RESEARCH_GAP`
- `REGIME`, `TIMEFRAME`, `DATASET`, `METHODOLOGY` (Scope limits)

## 4. Edge Model
Reused `EvidenceEdge`. New allowable types:
- `CONDITIONED_ON` (Scope limitations)
- `SHARES_FAILURE_MODE` (Recurring Discrepancy Patterns)
- `EXPOSES_GAP` (Unresolved intelligence paths)
- `CONTRADICTS` (Opposing evidence resolution)

## 5. Temporal Handling (As-Of)
All queries (`get_historical_graph_summary`, `get_related_claims`, `get_failure_clusters`) require a strict `as_of` boundary. The DAG enforces `created_at` and `as_of` limits explicitly before node ingestion and during DFS traversal. Future leakage is impossible.

## 6. Traversal Bounds
`get_related_claims` enforces `max_depth` (default 3) and `max_nodes` (default 100). The DFS strictly stops at these constraints to prevent cyclic exhaustion or memory explosions.

## 7. Discrepancy & Isolation Integration
If Phase 48 identifies a dataset fragility, Phase 51 constructs a `KnowledgePattern`. Phase 52 maps this into the Graph as a `KNOWLEDGE_PATTERN` node connected via `SHARES_FAILURE_MODE` edges, explicitly preserving the Phase 49 `PARTIAL_ISOLATION` structure.

## 8. Idempotency & Immutability
`KnowledgeGraphBuilder._save_edge_idempotent` dynamically checks the Phase 31 SQLite datastore for existing outbound edges. Rerunning `knowledge-graph-build` produces exactly 0 duplicated edges or nodes. Revisions trigger Phase 46 `GovernanceService` audits.

## 9. Security & Scientific Audit
- **No Profitability Logic:** The graph does not contain numerical predictions.
- **No Optimization:** AI cannot "trade" the graph. 
- **Causality Constraint:** "CONDITIONED ON" replaces "CAUSES".

**PAPER / RESEARCH ONLY — LIVE TRADING DISABLED**
