# PHASE 48 DISCOVERY REPORT: RESEARCH REPRODUCTION DISCREPANCY INTELLIGENCE

## 1. Phase 47 Reproduction Architecture
Phase 47 currently provides `IndependentVerificationResult`, which calculates if outputs matched structurally or numerically, generating a list of `ReproductionDiscrepancy` objects (e.g. `NUMERICAL_DRIFT`).

## 2. Existing Phase 46 Change Detection
Phase 46 `ResearchChangeDetector` returns `ChangeCategory` like `DATA_CHANGED` or `CODE_CHANGED`. This is the perfect input for deterministic root-cause attribution.

## 3. What Discrepancy Causes Can Actually Be Proven
If Phase 46 signals `DATA_CHANGED` and Phase 47 signals `STRUCTURAL_DIFFERENCE`, we can **confirm** the dataset change as a root cause. However, if BOTH `DATA_CHANGED` and `CODE_CHANGED` occurred, we **cannot prove** which one caused the output change without running a controlled 1-factor check. We must limit causal attribution.

## 4. What Cannot Be Proven
- Exact source code diff attribution (we only have fingerprint level).
- Causal fraction (e.g., 80% due to data, 20% due to code). We must declare `MULTIPLE_CONTRIBUTING_FACTORS`.
- Automatic repair logic.

## 5. Exactly what Phase 48 adds
Phase 48 acts as a translator between Phase 46 (Input Change) and Phase 47 (Output Change). It creates a `ReproductionDiscrepancyAnalysis` with `RootCauseAttribution` objects and an explicit `DiscrepancyImpactAssessment`. This provides actionable, evidence-backed explanations that feed safely into Phase 32 (Planner).
