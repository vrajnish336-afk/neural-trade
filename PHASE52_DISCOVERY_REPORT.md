# PHASE 52 DISCOVERY REPORT

## 1. Existing Graph Architecture (Phase 31)
- `app/research/evidence_graph/models.py` uses `EvidenceNode` and `EvidenceEdge`.
- The repository (`app/research/evidence_graph/repository.py`) relies on SQLite to persist these nodes and edges with deterministic UUIDs (`identity_hash` and `deterministic_key`).
- I have successfully injected the Phase 52 node and edge enums directly into `NodeType` and `EdgeRelationship` inside `models.py`. This ensures we do NOT create a redundant parallel graph engine.

## 2. Existing Canonical Knowledge (Phase 51)
- `app/research/knowledge_intelligence/models.py` provides `ResearchKnowledgeClaim`, `KnowledgePattern`, and `KnowledgeGap`.
- These output strictly scoped canonical statements bounded by dataset, timeframe, and regime.

## 3. Node Mapping Strategy
We will map Phase 51 models to Phase 31 `EvidenceNode` wrappers:
- `KNOWLEDGE_CLAIM` -> `ResearchKnowledgeClaim`
- `KNOWLEDGE_PATTERN` -> `KnowledgePattern`
- `RESEARCH_GAP` -> `KnowledgeGap`
- Scopes will map to `REGIME`, `TIMEFRAME`, `DATASET`, `METHODOLOGY`, `COST_ASSUMPTION` nodes.

## 4. Edge Mapping Strategy
- We will generate deterministic edges representing knowledge relationships.
- e.g. `CLAIM_A` -> `CONDITIONED_ON` -> `REGIME_TRENDING_DOWN`
- e.g. `CLAIM_A` -> `CONTRADICTS` -> `CLAIM_B`

## 5. Scope Mismatches & Causal Protection
- We will enforce checks to prevent `CAUSES` from being hallucinated by ensuring only explicit allowlist edges (`ASSOCIATED_WITH`, `CONDITIONED_ON`, `LIMITED_BY`) are utilized unless Phase 38 causal logic explicitly supplies it.
- We will respect `as_of` bounds across all query logic.

## 6. CLI & UI
- We will add `app/cli/commands/knowledge_graph_cli.py`.
- We will add interactive displays to `app/dashboard/components/synthesis.py` or similar for cross-domain intelligence.

## 7. Next Steps
1. Create `app/research/knowledge_graph/models.py` for relationship query outputs.
2. Create `app/research/knowledge_graph/builder.py` to ingest Phase 51 claims and construct the nodes and edges deterministically into Phase 31.
3. Create `app/research/knowledge_graph/queries.py` to perform bounded searches (e.g. `get_related_claims`, `get_failure_clusters`).
4. Write `test_knowledge_graph.py` testing determinism, idempotency, and future-leakage protection.
