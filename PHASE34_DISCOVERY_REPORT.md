# PHASE 34 DISCOVERY REPORT: RESEARCH HYPOTHESIS VALIDATION & FALSIFICATION ENGINE

## 1. Existing Architecture Analysis
- **Phase 33 (Knowledge Synthesis & Hypothesis Generation)**: Defines `ResearchHypothesis` containing `falsification_condition`, `expected_observation`, and specific bounds. Uses states like `TESTABLE`.
- **Phase 31 (Evidence Graph)**: Contains the authoritative `EvidenceNode` and `EvidenceEdge` lineage structures used to trace hypotheses back to experiments.
- **Phase 32 (Research Planner)**: Plans research decisions. Validated hypotheses can provide robust input here.
- **Phase 28/29 (Robustness/Evolution)**: Used to assess parameter stability and multi-seed robustness.
- **Phase 18 (Forward Validation)**: Supplies walk-forward / out-of-sample experiment results.

## 2. Identified Synergies & Required Additions
- We have the hypotheses, and we have the raw graph. Phase 34 will bridge them by introducing a `HypothesisValidator` that traverses the EvidenceGraph for nodes matching the hypothesis's identity and bounds, evaluating their alignment with `expected_observation` and explicitly checking the `falsification_condition` through a `FalsificationEngine`.
- Need explicit deterministic tracking for validation limits. The validator will aggregate `CONTRADICTS` vs `SUPPORTS` edges linking to a hypothesis.
- Strict `as_of` temporal evaluation is needed to ensure zero future-leakage. We must check `node.as_of <= validation.as_of` before accepting any node into the falsification check.

## 3. Storage Additions
- Table: `research_hypothesis_validations`
- Contains: `validation_id`, `hypothesis_id`, `as_of`, `validation_state`, `falsification_state`, `lineage_hash`.

## 4. Integration Points
- **Falsification Engine**: Operates natively on EvidenceGraph contradictions.
- **Planner Output**: Converts a validated state into an update on the original `ResearchHypothesis` (e.g., setting it to `SUPPORTED`, `REJECTED`, or `WEAKENED`).

## 5. Security & Safety
- **PAPER/RESEARCH ONLY**: Validations generate structured explanations and evidence aggregates, absolutely zero capability to initiate live trades or automatic new experiments.
- **Immutable Boundaries**: Hypotheses once validated cannot have their `falsification_condition` or `expected_observation` modified.
