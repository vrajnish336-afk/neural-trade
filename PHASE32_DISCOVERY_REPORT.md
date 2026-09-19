# PHASE 32 DISCOVERY REPORT: EVIDENCE-BASED RESEARCH DECISION INTELLIGENCE & RESEARCH PLANNER

## 1. Existing Architecture & Evidence Sources
Based on existing project structures:
- **Phase 14**: `ResearchIdentity` provides stable deterministic keys.
- **Phase 17**: Consolidates gaps and conflicts (`research_evidence_gaps`, `research_conflicts`).
- **Phase 28**: Provides Experiment Intelligence (evidence profiles, walk-forward, robustness).
- **Phase 29**: Handles controlled evolution (`research_evolution_proposals`).
- **Phase 30**: Continuous Research Orchestrator logic.
- **Phase 31**: Evidence Graph (`EvidenceNode`, `EvidenceEdge`) tracks relationships (e.g. `CONTRADICTS`, `SUPPORTS`).

## 2. Identified Data and Capabilities
Existing authoritative data that will be reused:
- **Research Questions & Gaps**: Detected by Phase 17 and stored as `EVIDENCE_GAP` nodes in Phase 31.
- **Hypotheses & Identities**: Tracked via `identity_hash` across systems.
- **Evidence Relationships**: `SUPPORTS`, `CONTRADICTS` handled by `EvidenceEdge`.
- **Conflicts**: Extracted via `CONTRADICTS` edges from Phase 31.
- **Saturation**: Measurable by counting `EXPERIMENT` nodes connected to an identity.

## 3. Minimal Additions Proposed
I will enhance `app/research/planner`:
- `models.py`: Expand `ResearchQuestionCandidate` and `ResearchDecision` to include all requested fields.
- `repository.py`: Update schema and SQLite storage for persistence.
- `scoring.py`: Enhance `ScoringEngine` to be a deterministic algorithm that maps gaps, uncertainty, conflicts, and evidence density into a `priority_score` and `priority_breakdown` using `EXPECTED_INFORMATION_VALUE_HEURISTIC`.
- `planner.py`: Expand `ResearchDecisionPlanner` to rank gaps, prepare questions, and interact with the graph.

## 4. Reusing Existing Lineage
- Identity: `identity_hash` is reused to prevent duplicate question candidates.
- Lineage: The planner traces through `EvidenceGraph`. No duplicate identity system built.
- Safety: Explicit human approval gate. Live trading remains completely disabled.
