# PHASE 38 DISCOVERY REPORT: RESEARCH CAUSALITY & MECHANISM VALIDATION ENGINE

## 1. Discovered Architecture & Integration Points
The project maintains a strict layered research intelligence architecture:
- **Phase 31 (Evidence Graph)**: Contains `EvidenceNode` and `EvidenceEdge`. Edge directions and `created_at`/`as_of`/`observed_at` metadata will support temporal ordering detection.
- **Phase 34 (Hypothesis Validation)**: Provides authoritative falsification states (`FalsificationState`). If falsified, causality cannot exist.
- **Phase 35 (Replication / Generalization)**: Differentiates identical-dataset replays from distinct unseen evidence. Crucial for confirming repeated structural support.
- **Phase 36 (Decay / Drift)**: Provides staleness and drift metrics (`DecayState`, `RevalidationReason`).
- **Phase 37 (Consensus & Conflict)**: Normalizes evidence into `ConsensusAssessment` with `ConsensusState` and conditional resolutions. Phase 38 builds directly on top of Phase 37 consensus.

## 2. Reusable Causal / Evidence Infrastructure
- `ConsensusAssessment`: Provides the base level of structural agreement vs conflict. If there's no consensus, there's unlikely to be strong causal evidence.
- `EvidenceGraphRepository`: Allows for traversal of observed variables and specific metadata (e.g., `regime`, `cost_scenario`) across connected nodes.
- `KnowledgeState`: Used in Phase 33 to map our causal limitations back to global intelligence without mutating raw nodes.

## 3. Metadata for Mechanism Analysis
- The `EvidenceNode` `metadata` dict contains variables like `regime`, `volatility`, `cost_scenario`, and parameters. 
- Phase 38 will use co-occurring variables (e.g., `regime` and `cost_scenario` shifting identically) to flag `CONFOUNDING_RISK`.
- Causal analysis will heavily rely on detecting `TEMPORAL_ASSOCIATION` by checking if mechanism variables were logically observed prior to outcome measurement.

## 4. Duplicate Avoidance
- Do NOT rewrite consensus logic. Call Phase 37 outputs.
- Do NOT rewrite evidence strength. Consume Phase 35.
- Do NOT write an AI LLM prompt to "guess" causality. Keep deterministic checks on metadata overlap and temporal constraints.

## 5. Limitations & Planned Causal Engine
The engine will classify the state into: `CORRELATIONAL`, `TEMPORAL_ASSOCIATION`, `CONDITIONAL_ASSOCIATION`, `STRUCTURALLY_SUPPORTED`, `MECHANISTICALLY_PLAUSIBLE`, `CAUSAL_EVIDENCE_SUPPORTED`, `CAUSAL_EVIDENCE_INSUFFICIENT`. 
It will aggressively default to `CAUSAL_EVIDENCE_INSUFFICIENT` if alternative explanations or confounders (like identical datasets) cannot be ruled out.

## 6. Integration Boundaries
The causal engine will output a `CausalAssessment` with identified `AlternativeExplanation` and `ResearchEvidenceGap` objects, which are passed to the Phase 32 Research Planner to explicitly test confounders. It will never output "guaranteed profit."
