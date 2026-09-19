# PHASE 37 DISCOVERY REPORT: RESEARCH EVIDENCE CONSENSUS & CONFLICT RESOLUTION ENGINE

## 1. Existing Architecture & Integration Points
The project maintains a rigorous multi-layer research validation hierarchy:
- **Phase 31 (Evidence Graph)**: The root source of truth. Contains `EvidenceNode` and `EvidenceEdge`. Edge relationships (`SUPPORTS`, `CONTRADICTS`) form the foundation of our consensus map.
- **Phase 32 (Research Planner)**: Generates and prioritizes explicit research questions. Phase 37 will send `ResearchEvidenceGap` outputs here if there are unresolved conflicts.
- **Phase 33 (Knowledge Synthesis)**: Maintains overarching `KnowledgeState`. Phase 37 will map Consensus statuses (e.g. `CONSENSUS_SUPPORTED`, `CONFLICTED`) back to these knowledge states without bypassing the authoritative pipeline.
- **Phase 34 (Hypothesis Validation)**: Yields `HypothesisValidationResult` and authoritative `FalsificationState`. Phase 37 strictly honors `TRIGGERED` falsifications.
- **Phase 35 (Replication & Evidence Strength)**: Yields `ResearchReplicationResult`. Phase 37 utilizes `total_independent_units` vs `same_dataset_units` to prevent fake multiple-testing consensus.
- **Phase 36 (Decay & Drift)**: Yields `RevalidationAssessment` flags (`STALE`, `REGIME_SHIFT`, `METHODOLOGY_DRIFT`). Phase 37 uses this to identify *why* conflicts may exist.

## 2. Discovered Reusable Components
- `app.research.evidence_graph.repository`: Fetches raw nodes and edges.
- `app.research.hypothesis_validation.models`: Provides baseline falsification contexts.
- `app.research.synthesis.models.KnowledgeState`: The existing knowledge taxonomy we map to.
- `app.research.replication.models.EvidenceStrengthLevel`: Reused for annotating the strength of a consensus.

## 3. Planned Phase 37 Implementation
- **Location**: `app/research/consensus/`
- **Models**: `ConsensusState` (CONSENSUS_SUPPORTED, PARTIAL_CONSENSUS, CONDITIONAL_CONSENSUS, CONFLICTED, UNRESOLVED, INSUFFICIENT_EVIDENCE), `ConflictType`, `ConflictSeverity`, `ResolutionState`.
- **Normalization Engine**: Consolidates edge metadata into an `EvidenceConsensusUnit`.
- **Consensus Engine**: Counts independent supportive vs contradictory nodes. Determines conditional consensus (e.g., supported in regime A, contradicted in regime B).
- **Conflict Resolver Engine**: Analyzes identified contradictions to classify them into specific structural conflicts (`REGIME_CONFLICT`, `METHODOLOGY_CONFLICT`, `COST_CONFLICT`). If older conflicting evidence is entirely stale, flags `RESOLVED_BY_FRESHER_EVIDENCE`.

## 4. Boundaries and Safety Measures
- **No Averaging / No Majority Rules**: Conflicts are preserved unless deterministically resolved by metadata boundaries.
- **Time Strictness**: `as_of` epoch filtering must perfectly mirror Phases 34-36.
- **Safety**: Fully disconnected from broker APIs. Emits only structured JSON gaps for human review via the Planner.
