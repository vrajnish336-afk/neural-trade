# PHASE 31 IMPLEMENTATION REPORT: EVIDENCE GRAPH

## 1. Discovery & Data Flow
Phase 31 built a materialized knowledge graph over the extensive set of Phase 1-30 SQLite research tables. Rather than rebuilding the underlying models, the graph introduces generic `EvidenceNode` and `EvidenceEdge` models that deterministically map the relationships using authoritative, existing foreign keys and metadata parameters.

## 2. Core Mechanics
- **`GraphBuilder` (`app/research/evidence_graph/builder.py`)**: Responsible for extracting nodes/edges idempotently from:
  - `research_sandbox_experiments`
  - `research_evolution_proposals`
  - `research_lessons`
  - `experiment_comparisons`
- **`GraphQueries` (`app/research/evidence_graph/queries.py`)**: Exposes bounded, strictly `as_of` filtered timeline queries such as `get_evidence_chain`, `get_supporting_evidence`, and `get_contradicting_evidence`.

## 3. UI & CLI
- **Streamlit (`app/dashboard/components/evidence_graph.py`)**: Tab 15 added. Allows building the graph and tracing the lineage / support network of a specific node.
- **CLI (`app/cli/commands/evidence_graph.py`)**: `ntrade evidence-graph-build`, `ntrade evidence-graph-validate`, `ntrade evidence-chain`.

## 4. Tests and Security
- Successfully asserted graph query limits, chronological integrity, and deterministic duplicates in `test_ai_evidence_graph.py`.

## 5. FINAL SAFETY STATEMENT
**PAPER / RESEARCH ONLY.**
**CAUSALITY NOT ESTABLISHED UNLESS DETERMINISTICALLY SUPPORTED.**
**AI HAS NO AUTHORITATIVE GRAPH CONTROL.**
**GRAPH IS NOT PROOF OF PROFITABILITY.**
**LIVE TRADING DISABLED.**
