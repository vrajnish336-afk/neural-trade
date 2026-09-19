# PHASE 40 DISCOVERY REPORT: ADVANCED WALK-FORWARD & TEMPORAL GENERALIZATION ENGINE

## 1. Existing Infrastructure Analysis
- **Phase 10 (Robustness Walk-Forward)**: Exists locally inside `app.research.robustness.walk_forward`. It's a localized array/slice loop over `MarketBar` objects designed for parameter robustness, but lacks deep integration into the global evidence graph.
- **Phase 18 (Forward Validation Service)**: Takes a `FrozenSpecification` and rigorously tests it against unseen data bounded by `historical_end`. It strictly blocks future data snooping and produces a downstream `ResearchExperiment` -> Evidence -> Drift.
- **Phase 35/36/37/38 (Generalization, Drift, Consensus, Causality)**: Currently handle individual experiments and evidence comparisons.

## 2. Integration Strategy
Phase 40 will NOT duplicate the Backtest loop or the Phase 18 Forward Validation mechanics. Instead, Phase 40 will sit above them as the **Temporal Generalization Engine**:
- **`WalkForwardWindowBuilder`**: Replaces the basic iteration from Phase 10 with a formal architecture producing `WalkForwardWindow` configurations (Rolling/Expanding).
- **Execution**: The builder generates multiple historical bounds. We can dispatch these slices as historical experiments into the standard BacktestEngine or Sandbox wrapper.
- **Aggregation**: The engine gathers the results for each sequential window and outputs a `TemporalGeneralizationAssessment` (e.g., `STRONG_TEMPORAL_GENERALIZATION` vs `INCONSISTENT`).
- **Knowledge Linkage**: This assessment then generates Gaps (e.g., `TEMPORAL_DRIFT_GAP`) mapped back into the Phase 32 Planner, and Phase 31 EvidenceGraph structural edges (`WINDOW_TESTS_CANDIDATE`).

## 3. Mandatory Safety Rules Enforced
- `TRAIN_END < VALIDATION_START < FORWARD_START`.
- No cherry-picking: Failed windows must be preserved and actively contribute to the dispersion metrics.
- Strategy immutability: Parameters are completely frozen during the FORWARD phase of each window.

## 4. Architecture Plan
- Package: `app/research/temporal_generalization/`
- Files: `models.py`, `builder.py`, `evaluator.py`, `repository.py`, `service.py`, `__init__.py`.
- Integrations: CLI (`ntrade walk-forward`), Dashboard Tab 17 ("Temporal Generalization Lab").
