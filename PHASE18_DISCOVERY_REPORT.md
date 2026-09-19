# PHASE 18 DISCOVERY REPORT: FORWARD PAPER VALIDATION ENGINE

## 1. Current Historical Backtest Flow
Currently, the `ResearchJobOrchestrator` generates a `ResearchJob` from an opportunity, loads data (defaulting to the last 365 days), instantiates a `BacktestEngine` with default `CostConfig`, and runs the backtest. The result is wrapped in a `ResearchExperiment` and passed to the `ResearchEvidenceEvaluator`.

## 2. Existing Chronological & OOS Logic
- **Chronological Split**: Currently, there is no formal chronological split between "train" and "forward validation" in the automated AI pipeline. The Phase 7 framework introduced train/test splits for manual scripts, but the automated Phase 15 Orchestrator tests the entire fetched dataset as a single block.
- **OOS Logic**: Missing in the AI pipeline.
- **Walk-Forward**: The Phase 7 abstractions exist but are not integrated into the automated AI loop.

## 3. Existing Abstractions
- **Cost/Slippage**: `CostConfig` applies deterministic commission and slippage inside `BacktestEngine._enter_position` and `_close_position`.
- **Lineage**: `ResearchExperiment` stores dataset bounds (`dataset_identity`), symbols, strategy, and configuration.
- **Analytics**: `generate_analytics_report` produces a highly detailed JSON report from a `BacktestResult`.
- **Knowledge Layer**: Phase 17 explicitly tracks `EvidenceGap`s such as `MISSING_WALK_FORWARD`.

## 4. Architectural Gaps
- There is no automated concept of a "Frozen Specification" that locks in a strategy, risk parameters, and cost assumptions for a forward run.
- There is no table to track forward validation runs separately from standard exploratory backtests.
- There is no deterministic Drift/Degradation analyzer comparing a historical experiment to a forward experiment.

## 5. Proposed Forward Validation Architecture
We will introduce a `ForwardValidationService` and `forward_validation_runs` table.
- **Data Flow**:
  1. User/Orchestrator identifies a `ResearchConclusion` with `NextResearchAction.VALIDATE_WALK_FORWARD`.
  2. Extracts the `provenance_experiment_id` and "freezes" its configuration (strategy, symbols, cost, risk, historical bounds).
  3. Creates a `ForwardValidationRun`.
  4. The engine loads ONLY data where `timestamp > historical_end`.
  5. Runs the `BacktestEngine`.
  6. Compares the resulting `BacktestResult` to the historical result using a new `PerformanceDriftAnalyzer`.
  7. Wraps it in a new `ResearchExperiment` and emits a new Evidence Summary.
- **State Model**: `CREATED`, `RUNNING`, `COMPLETED`, `FAILED`, `INSUFFICIENT_DATA`.
- **Persistence**: SQLite table `forward_validation_runs`.
- **Restart/Recovery**: Enforced via state machine, similar to Phase 15.

## 6. Scientific Validity Risks
- **Data Leakage**: The `BacktestEngine` naturally iterates chronologically, protecting against lookahead. We must ensure the dataset loader strictly filters out historical rows before passing to the engine.
- **Parameter Mutation**: We will enforce that the strategy parameters passed to the engine are identical to the frozen specification. No optimization loops will be added.

## 7. Expected File Changes
**Created**:
- `app/research/forward_validation_models.py`
- `app/research/forward_validation_service.py`
- `app/research/drift_analyzer.py`
- `app/cli/commands/forward_validation.py`
- `tests/test_ai_forward_validation.py`

**Modified**:
- `app/database/schema.py`
- `app/cli/main.py`
- `app/dashboard/components/research.py`
- `app/research/knowledge_service.py` (to integrate drift/evidence outcomes)
