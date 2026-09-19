# PHASE 31 DISCOVERY REPORT: EVIDENCE GRAPH

## 1. Existing Architecture & Evidence Sources
Phase 1-30 created a vast array of interconnected SQLite tables tracking research state:
- **Phase 13 (Loop):** `research_experiments`, `ai_research_requests`
- **Phase 14 (Memory):** `research_memory`, `research_opportunities`
- **Phase 15 (Orchestrator):** `research_jobs`
- **Phase 16 (Decision):** `research_conclusions`, `research_conflicts`
- **Phase 17 (Knowledge):** `research_knowledge_changes`, `research_evidence_gaps`
- **Phase 18 (Forward Val):** `forward_validation_runs`
- **Phase 21 (Portfolio):** `paper_track_records`
- **Phase 23 (Lessons):** `research_lessons`, `evolution_proposals`
- **Phase 24 (Forecasting):** `forecast_runs`
- **Phase 25 (World Intel):** `world_observations`
- **Phase 27 (Sandbox):** `research_code_proposals`, `research_sandbox_experiments`
- **Phase 28 (Intelligence):** `experiment_comparisons`
- **Phase 29 (Evolution):** `research_evolution_proposals`
- **Phase 30 (Continuous):** `research_cycles`

## 2. Existing Lineage
Currently, tables are linked via foreign keys or shared attributes:
- `identity_hash` connects Memory, Opportunities, Knowledge Changes, Gaps, and Forward Validations.
- `experiment_id` traces Backtest outputs to Forward Validation results.
- `proposal_id` links Sandbox logic to continuous cycles.
- JSON payload arrays (e.g., `provenance_experiment_ids`, `source_lesson_ids`) house 1-to-N relationships natively.

## 3. Minimal Additions Proposed
The goal is NOT to recreate these objects. Instead, the `Evidence Graph` will be an informational overlay:
- `research_evidence_nodes`: Stores stable IDs, node type, observed timestamps, and source object references (e.g. `source_id = 'exp_123', source_type = 'EXPERIMENT'`).
- `research_evidence_edges`: Stores deterministic edges (e.g. `SUPPORTS`, `DERIVED_FROM`, `CONTRADICTS`) extracted strictly from the foreign keys and metadata fields in the source tables.

## 4. Why Necessary
Currently, answering "Why was this parameter proposed?" requires joining `research_cycles`, `research_evolution_proposals`, `research_evidence_gaps`, and `research_sandbox_experiments` with custom logic. An Evidence Graph materializes these causal and temporal chains natively into a queriable graph structure honoring `as_of` bounds.

## 5. Security
- Deterministic extraction: The `GraphBuilder` will read SQLite rows and emit Nodes/Edges. AI prompt injection cannot force an edge to be created because the builder only parses rigid database relational integrity bounds.
