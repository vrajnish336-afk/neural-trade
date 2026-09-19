# PHASE 41 DISCOVERY REPORT: MULTI-TIMEFRAME RESEARCH ENGINE

## 1. Existing Infrastructure Analysis
- **Execution & Models**: `MarketBar` is the standard atomic unit. `BacktestEngine` runs chronologically over a list of `MarketBar` instances. `Strategy.generate_signal` evaluates the historical slice.
- **Timeframes**: Basic `resample_bars` exists in `app.analysis.timeframes.py`. It uses pandas `resample` with `closed='left'`, `label='left'`, which correctly buckets historical values. 
- **Risk & Track Record**: The risk engine handles daily loss limits and exposure limits efficiently. `BacktestEngine` integrates seamlessly with `RiskEngine`.
- **Validation**: `ForwardValidationService` (Phase 18) and `TemporalGeneralizationService` (Phase 40) provide strict out-of-sample forward wrappers.

## 2. Integration Strategy
To preserve existing engines without duplication:
- We will construct the Multi-Timeframe Research Engine as a composite logic layer that acts at the `Strategy` evaluation level (`app/research/multi_timeframe/`).
- **Hierarchy Validation**: We will build a strict validator checking Pandas offset strings (e.g., '1D' > '4H' > '1H' > '15m' > '5m').
- **Context Generation**: We'll build `MultiTimeframeContextBuilder` which dynamically resamples the LTF historical slice into MTF and HTF, ensuring that only *completed* higher-timeframe candles are available to the LTF decision barrier.
- **Strategy Implementation**: A composite `MultiTimeframeStrategy` will sit inside the standard `BacktestEngine`, receiving LTF bars, aggregating to the context, and evaluating HTF context -> MTF setup -> LTF entry.

## 3. Mandatory Safety Rules Enforced
- NO LOOK-AHEAD: A 4H candle's close value cannot be known at 13:05. The system must strictly lock out the in-progress HTF candle, returning only the last *completed* HTF candle for the context.
- NO BROKER EXECUTION: Strictly bounded to the Sandbox and Research Graph.

## 4. Architecture Plan
- Package: `app/research/multi_timeframe/`
- Files: `models.py`, `validator.py`, `builder.py`, `strategy.py`, `evaluator.py`, `service.py`, `__init__.py`.
- Tests: `tests/test_multi_timeframe.py` asserting strict temporal alignment and baseline comparisons.
- UI: "Multi-Timeframe Lab" in Streamlit dashboard (Tab 18 or appended to Tab 17).
