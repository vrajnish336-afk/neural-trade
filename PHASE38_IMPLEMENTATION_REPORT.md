# PHASE 38 IMPLEMENTATION REPORT: RESEARCH CAUSALITY & MECHANISM VALIDATION ENGINE

## 1. Discovery Summary
Discovery located the requisite temporal metrics (`observed_at` vs `created_at` mapped to `val_as_of`) on the `EvidenceNode` objects. It confirmed Phase 37 outputs structured conflicts seamlessly. Phase 38 extends this by converting consensus logic into rigorous scientific causality mapping—specifically checking if identical metadata overlaps uniformly across multiple independent tests, effectively masking confounding variables (e.g., separating "regime" from "cost"). 

## 2. Architecture Changes
- Created package `app/research/causality/`.
- Built `CausalValidator` to scan node graphs mapping to focal hypotheses.
- Implemented confounding logic: If supporting evidence perfectly overlaps on metadata bounds (like Regime = TREND + Cost = HIGH), it downgrades from causal attribution to `CAUSAL_IDENTIFICATION_LIMITED` and emits alternative explanations.
- Temporal checking evaluates whether causal constraints logically preceded validation outcomes chronologically.
- Appended "Causality & Mechanism Lab" explicitly beneath the "Consensus Lab" in Streamlit Tab 17.
- Added `ntrade causality` CLI endpoint.

## 3. Files Created/Modified
- `app/research/causality/models.py` (Created)
- `app/research/causality/repository.py` (Created)
- `app/research/causality/validator.py` (Created)
- `app/research/causality/service.py` (Created)
- `app/research/causality/__init__.py` (Created)
- `app/cli/commands/causality.py` (Created)
- `app/cli/main.py` (Updated)
- `app/dashboard/components/synthesis.py` (Updated)
- `tests/test_research_causality.py` (Created)
- `GSD_PLAN.md` (Updated)
- `PHASE38_DISCOVERY_REPORT.md` (Created)

## 4. Existing Components Reused
- Phase 34 Falsification states directly lock causality evaluation paths.
- Phase 35/37 independent unit counting determines `REPEATED_STRUCTURAL_SUPPORT` thresholds.

## 5. Relationship Methodology
Operates deterministically on observation metadata bounds. Transitions correlation to `TEMPORAL_ASSOCIATION` strictly by comparing UTC ISO timestamps.

## 6. Confounding Methodology
Identifies when a group of supposedly supporting independent tests all share identical bounds across non-targeted variables (e.g., all supporting evidence occurred only under HIGH_VOLATILITY, yet volatility wasn't the focal variable).

## 7. Causal Evidence Hierarchy
Strictly structured:
- `NO_RELATIONSHIP_EVIDENCE`
- `CORRELATIONAL`
- `TEMPORAL_ASSOCIATION`
- `CONDITIONAL_ASSOCIATION`
- `REPEATED_STRUCTURAL_SUPPORT`
- `CAUSAL_EVIDENCE_SUPPORTED`

## 8. Exact Focused Test Count
4 tests specifically validating temporal lockout, falsification propagation, identical-dataset confounding risk, and future-data blockage.

## 9. Exact Full Pytest Count
319 passed, 0 failures.

## 10. Compileall Result
Clean. 0 errors.

## 11. NULL-byte Result
Clean. 0 instances.

## 12. Security/Secret Result
Passed. Analyzes strictly local SQLite state without dynamic execution hooks. 

## 13. Scientific Audit Result
Passed. Enforces absolute scientific conservatism: "Research evidence supports the proposed mechanism under the tested conditions; this does not establish universal causality." Prevents blind probability/PnL averaging.

## 14. Phase 31–37 Integration
Directly inherits identical schema structures. Validates temporal alignment across Phase 34 validation and Phase 37 consensus.

## 15. Final Safety Status
PAPER / RESEARCH ONLY.
LIVE TRADING DISABLED.
NO BROKER EXECUTION.
NO AUTOMATIC STRATEGY DEPLOYMENT.
NO AUTOMATIC PARAMETER MUTATION.
