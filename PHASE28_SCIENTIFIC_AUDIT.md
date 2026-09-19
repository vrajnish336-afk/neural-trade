# PHASE 28 SCIENTIFIC AUDIT: EXPERIMENT INTELLIGENCE

## 1. No PnL-Only Ranking
- **Status:** PASS
- **Verification:** The `ExperimentComparisonService` evaluates sample size coverage alongside raw return percentage. An experiment with high PnL but fewer than 30 trades is downgraded to `INSUFFICIENT`, preventing low-sample-size overfitting from taking precedence over robust statistics.

## 2. No Look-Ahead or Future Data
- **Status:** PASS
- **Verification:** The comparison engine strictly consumes statically persisted `ResearchSandboxExperiment` records and generates an `ExperimentComparison`. Since the Sandbox already prevents look-ahead (see Phase 27), and this module is read-only, no future contamination occurs.

## 3. Compatibility Checks
- **Status:** PASS
- **Verification:** `_check_compatibility` enforces dataset mapping. If two experiments use different datasets, it sets `NOT_COMPARABLE`.

## 4. Honest Methodology Versioning
- **Status:** PASS
- **Verification:** The `ExperimentComparison` object enforces a `methodology_version` (e.g. `v1`). Future modifications to the comparison heuristic will require bumping this version, preserving the integrity of historical assessments.

## 5. No Guaranteed Profitability
- **Status:** PASS
- **Verification:** All final evidence strength assessments explicitly output language like `"Experiment A has stronger evidence coverage under the evaluated conditions."` No `"BUY"` or `"SELL"` predictions are made.
