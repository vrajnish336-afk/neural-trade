# PHASE 35 DISCOVERY REPORT: RESEARCH REPLICATION, GENERALIZATION & EVIDENCE STRENGTH ENGINE

## 1. Existing Architecture & Components
- **Phase 34 (Hypothesis Validation)**: Provides `HypothesisValidationResult`, outlining `supporting_evidence_ids` and `contradicting_evidence_ids`, as well as `falsification_triggered` state.
- **Phase 33 (Knowledge Synthesis & Hypothesis Generation)**: Defines `ResearchHypothesis`.
- **Phase 31 (Evidence Graph)**: Holds raw `EvidenceNode` objects. Nodes representing experiments (`node_type = EXPERIMENT`) hold `metadata` which tracks temporal boundaries, seed, regimes, and cost parameters.

## 2. Methodology & New Integrations
Phase 35 sits atop Phase 34. While Phase 34 counts evidence support vs contradiction and tests formal falsification limits, Phase 35 measures the **independence**, **generalization**, and **strength** of that evidence.

- **Independence Engine**: We will retrieve all nodes listed in `supporting_evidence_ids` (and `contradicting_evidence_ids`) and cross-compare their datasets and metadata.
    - If Node A and Node B have the exact same `dataset_id` and `seed`: `SAME_DATASET_REPLAY`.
    - If `seed` differs but dataset is same: `DIFFERENT_SEED_ONLY`.
    - If datasets overlap temporally: `OVERLAPPING_DATA`.
    - Genuinely independent validation sets: `UNSEEN_DATA` or `INDEPENDENT_EXPERIMENT`.

- **Generalization Engine**: Checks if evidence spans multiple regimes, varying cost stresses, or completely different time periods.

- **Evidence Strength**: Constructs a final qualitative label (e.g. `STRONG`, `WEAK`, `FRAGILE`, `CONFLICTED`, `INSUFFICIENT`) and explains *why*. E.g., "WEAK: 5 supporting experiments, but all are SAME_DATASET_REPLAY."

## 3. Storage Additions
- Will create a lightweight mapping in `app/research/replication/models.py`.
- `app/research/replication/repository.py` will persist `ReplicationAssessment`, `GeneralizationAssessment`, and `EvidenceStrengthAssessment` grouped under a `ResearchReplicationResult`.
- Table `research_replication_results`.

## 4. Safety Constraints
- Read-only analysis of persisted evidence. 
- NO backtest execution. NO trading execution.
- Strict `as_of` bounds prevent future-data contamination by relying entirely on the `as_of` passed to the `EvidenceGraph`.
- The sample-size requirement (e.g., `<30 trades => INSUFFICIENT_EVIDENCE`) will be enforced contextually.
- Multiple comparison warnings (cherry-picking defense) will be flagged if there are dozens of iterations over the exact same dataset yielding mixed results.

## 5. UI/CLI Integration
- CLI: `ntrade replication <hypothesis_id>`
- Dashboard: Extend Streamlit Tab 17 ("KNOWLEDGE SYNTHESIS & HYPOTHESIS LAB") with a Replication & Strength breakdown expander.
