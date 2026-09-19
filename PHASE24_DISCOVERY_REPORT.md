# PHASE 24 DISCOVERY REPORT

## 1. OHLCV Data Entry & Representation
- **Source:** Data flows through `CsvHistoricalDataProvider` and synthetic generation.
- **Model:** `app.core.models.MarketBar` models individual candles (symbol, timestamp, open, high, low, close, volume).

## 2. Model Dependencies & Ecosystem
- The environment is fundamentally lightweight (`pandas`, `numpy`, `pydantic`). 
- **CUDA/PyTorch:** Not strictly guaranteed by `requirements.txt`. The implementation must provide a strict fallback.
- **Forecasting Models:** No existing abstractions for time-series forecasting were found in `app/`.

## 3. Chronological Boundaries & Future Leakage
- `ForwardValidationService` handles historical split by strictly filtering `b.timestamp > boundary_time`. We will replicate this strict chronological separation inside our `WindowBuilder`.

## 4. Visualization & State
- **Streamlit:** Uses standard `st.session_state`. Charts are currently built with custom HTML or Altair/Streamlit-native components (we'll see what's in `app.dashboard.components.charts`). I will use a simple Streamlit-native `st.line_chart` for plotting actual vs predicted paths if `plotly` isn't available.

## 5. Lessons Bank Integration
- The output of our forecasting (e.g., error metrics like MAE) can theoretically be analyzed by the same logic built in Phase 23 if grouped by regimes, but Phase 24 specifically focuses on the generation and evaluation of the trajectories themselves.

## 6. Safety Invariants
- The forecasting output MUST be isolated. It must not generate a `TradingSignal` nor interface with `RiskEngine`.
