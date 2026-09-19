# PHASE 19 DISCOVERY REPORT: LONG-TERM PAPER TRACK RECORD

## 1. Current Baseline
- **Baseline Test Count**: 193 tests
- **Existing Architecture**: 
  - `ForwardValidationRun` (Phase 18) correctly tests a frozen specification chronologically.
  - `PerformanceDriftAnalyzer` computes drift on a *single* forward validation run compared to its historical anchor.
  - `ResearchMemory` tracks canonical research hypotheses.
  - Existing `BacktestResult` and `generate_analytics_report` compute all necessary financial metrics (win rate, PF, drawdown).

## 2. Architectural Gaps for Long-Term Tracking
- **No Cumulative Tracking**: If a strategy is validated sequentially over 5 different periods (e.g., Jan-Mar, Apr-Jun, etc.), each run is isolated. There is no cumulative PnL or cumulative drawdown calculation linking them.
- **No Global Strategy Health**: `ForwardDriftState` only analyzes a single observation. We lack a rolling mechanism to detect long-term deterioration (e.g. `HEALTHY` -> `WATCH` -> `DEGRADED`).
- **No Duplicate Protection at Observation Level**: While `ForwardValidationRun` prevents concurrent runs, we need a formalized `PaperObservation` to safely append immutable history.

## 3. Proposed Phase 19 Architecture
**New Models:**
1. `PaperTrackRecord`: Aggregates all paper observations for a specific `(identity_hash, frozen_specification_hash)`. Tracks cumulative PnL, current paper equity, and max drawdown.
2. `PaperObservation`: An immutable wrapper around a completed `ForwardValidationRun`, extracting exactly the metrics needed for cumulative tracking.
3. `StrategyHealthSnapshot`: Computed dynamically (or persisted). States: `INSUFFICIENT_HISTORY`, `HEALTHY`, `WATCH`, `DEGRADED`, `CRITICAL`, `DATA_QUALITY_ISSUE`.

**New Service:**
`PaperTrackRecordService`:
- Reads completed `ForwardValidationRun`s.
- Appends new `PaperObservation`s sequentially.
- Validates chronological ordering (no overlap allowed unless explicitly tracked as a separate record).
- Re-calculates cumulative equity and drawdown.
- Emits `StrategyHealthSnapshot` updates.
- Creates `ResearchOpportunity` (Phase 14) if health drops to `DEGRADED`.

**Persistence Extensions (Schema):**
- `paper_track_records`
- `paper_observations`
- `paper_health_history`

## 4. Scientific Integrity & Data Safety
- **Immutability**: Once a `PaperObservation` is appended, it is read-only.
- **Chronological Rule**: The system will explicitly reject appending an observation where `start_time < previous_observation.end_time`.
- **No Live Overlap**: This is explicitly named `paper_track_records`.

## 5. Expected Files
- `app/research/track_record_models.py`
- `app/research/track_record_service.py`
- `app/research/health_analyzer.py`
- `app/cli/commands/track_record.py`
- `tests/test_ai_track_record.py`
- `PHASE19_IMPLEMENTATION_REPORT.md`
