# PHASE 28 DISCOVERY REPORT

## 1. Existing Systems
- **Phase 10 (Robustness)**: Contains `RobustnessScorecard` which handles individual experiment scoring (seed stability, cost resilience, Monte Carlo stability, walk-forward consistency, etc.).
- **Phase 18 (Forward Validation)**: Captures drift and out-of-sample forward observations.
- **Phase 21 (Candidate Portfolio)**: Ranks forward-running candidate snapshot performance via `ResearchEvidenceScore`.
- **Phase 27 (Sandbox)**: Generates `ResearchSandboxExperiment` dynamically.

## 2. Phase 28 Requirements
The goal is to build an `ExperimentComparisonService` that compares *two or more* experiments (e.g. from the sandbox or normal backtests) directly. It must calculate compatibility, normalize their evidence across 6 dimensions (Performance, Robustness, Generalization, Coverage, Reproducibility, Research Quality), and synthesize a final *comparison* assessment.

## 3. Data Representation
- We need an `ExperimentEvidenceProfile` model that flattens out existing results (BacktestResult, RobustnessScorecard, ForwardValidation) into a consistent schema for comparison.
- We need an `ExperimentComparison` model that points to two experiments and highlights their specific differences, strengths, and conflicts.

## 4. Architecture Location
- Create `app/research/intelligence/` or `app/research/comparison.py` (Wait, we have `app/research/comparator.py` from Phase 21 for Candidate tracking... let's create `app/research/experiment_intelligence.py`).
- I will create `app/sandbox/comparison.py` or `app/research/experiment_comparison/`. Actually, Phase 28 is "Research Experiment Intelligence", so `app/research/experiment_intelligence/` is fitting.

## 5. Safety
- Completely read-only.
- Does not modify or activate any strategy.
- Uses `as_of` boundaries implicitly via the persisted experiments which already respect chronology.
