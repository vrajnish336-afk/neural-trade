# PHASE 39 DISCOVERY REPORT: RESEARCH CAUSAL EXPERIMENT DESIGN & CONTROLLED VALIDATION ENGINE

## 1. Existing Infrastructure Analysis
- **Phase 38 (Causality Engine)**: Generates `CausalAssessment` with `confounders` (overlap on variables like regime/cost) and `research_gaps`. Phase 39 will consume these gaps to formulate targeted historical experiments.
- **Phase 32 (Research Planner)**: Prioritizes gaps. Phase 39 experiment designs fulfill these planner gaps.
- **Phase 27 (Research Sandbox)**: The `AISandboxStrategyWrapper` and `ASTSecurityValidator` provide safe, restricted execution environments. Phase 39 will interface with this execution boundary to run the designed historical tests.
- **Phase 34-37 (Validation, Replication, Drift, Consensus)**: Provide downstream metrics that evaluate the result of the Phase 39 experiment once it produces a new `EvidenceNode`.

## 2. Integration Points
- **Input**: A `CausalAssessment` gap mapping to multiple confounders (e.g., Regime=TREND and Volatility=HIGH).
- **Design Process**: The engine designs an `CausalExperimentDesign` holding all metadata bounds constant EXCEPT the `focal_variable` (e.g., Volatility). 
- **Approval Gate**: Human `status` check (`DRAFT` -> `REVIEW_REQUIRED` -> `APPROVED_FOR_RESEARCH`).
- **Output**: After execution in the Phase 27 sandbox, an `ExperimentResult` is generated which loops back to Phase 38 to verify if the structural causality was resolved (by separating the confounding risk).

## 3. Duplicate Prevention & Resource Constraints
- By hashing the `hypothesis_id`, `focal_variable`, and `control_variables`, we guarantee duplicate equivalent experiments are immediately rejected with `ALREADY_DESIGNED`.
- Parameter bounding is strictly enforced (no generic grid search; specific `delta` values only).

## 4. Phase 39 Scope
Phase 39 does NOT manufacture new execution pathways. It organizes a rigorous scientific control layout (treatment vs. control) for historical dataset querying via the existing experiment orchestrators, preserving strict `as_of` epoch rules to stop data snooping.
