import streamlit as st
import pandas as pd
import json
from datetime import timedelta
from app.forecasting.service import ForecastingService
from app.forecasting.repository import ForecastRepository

def render_forecasting_tab(conn):
    st.markdown("## PHASE 24: PRICE TRAJECTORY LAB")
    st.warning("PAPER / RESEARCH ONLY. FORECAST ≠ TRADING SIGNAL.")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("### Controls")
        symbol = st.text_input("Symbol", "BTC/USD")
        timeframe = st.selectbox("Timeframe", ["1D", "1h", "15m"])
        window = st.number_input("Input Window Size", min_value=10, max_value=1000, value=100)
        horizon = st.number_input("Forecast Horizon", min_value=1, max_value=100, value=10)
        model = st.selectbox("Model", ["baseline", "kronos"])
        
        if st.button("Generate Forecast"):
            svc = ForecastingService()
            if model == "kronos" and not svc.advanced.is_available():
                st.warning("Kronos adapter unavailable. Falling back to Baseline.")
                model = "baseline"
                
            record = svc.generate_forecast(symbol, timeframe, window, horizon, model)
            if record:
                st.session_state["selected_forecast_id"] = record.forecast_id
                st.success("Forecast Generated!")
            else:
                st.error("Failed to generate forecast. Check data availability and bounds.")
                
    with col2:
        st.markdown("### Trajectory Viewer")
        repo = ForecastRepository()
        
        fid = st.session_state.get("selected_forecast_id")
        if fid:
            # We fetch manually instead of using get_records for a single ID to save time, but for now we just filter
            records = [r for r in repo.get_records() if r.forecast_id == fid]
            if records:
                r = records[0]
                st.markdown(f"**Model:** {r.model_name} | **Symbol:** {r.symbol} | **Horizon:** {r.forecast_horizon}")
                st.markdown(f"**Status:** {r.status} | **MAE:** {r.mae or 'N/A'} | **Dir. Acc:** {r.directional_accuracy or 'N/A'}")
                
                # Render chart
                # We need actual history up to input_end
                try:
                    from app.data.csv_provider import CsvHistoricalDataProvider
                    provider = CsvHistoricalDataProvider()
                    bars = provider.get_historical_bars(r.symbol, r.timeframe)
                    history = [b for b in bars if b.timestamp <= r.input_end][-r.window_size:]
                    
                    df_hist = pd.DataFrame([{"timestamp": b.timestamp, "Actual": b.close, "Predicted": None} for b in history])
                    
                    preds = json.loads(r.predicted_values_json)
                    future_data = []
                    last_t = history[-1].timestamp
                    for i, val in enumerate(preds):
                        t = last_t + timedelta(days=i+1) if r.timeframe == "1D" else last_t + timedelta(hours=i+1)
                        future_data.append({"timestamp": t, "Actual": None, "Predicted": val})
                        
                    df_fut = pd.DataFrame(future_data)
                    df_combined = pd.concat([df_hist, df_fut])
                    df_combined.set_index("timestamp", inplace=True)
                    
                    st.line_chart(df_combined)
                    
                except Exception as e:
                    st.error(f"Failed to plot trajectory: {e}")
                    
        else:
            st.info("Select or generate a forecast to view the trajectory.")
            
    st.markdown("### Forecast History")
    records = repo.get_records()
    if records:
        df = pd.DataFrame([{
            "ID": r.forecast_id,
            "Symbol": r.symbol,
            "Model": r.model_name,
            "Horizon": r.forecast_horizon,
            "MAE": f"{r.mae:.4f}" if r.mae else None,
            "Dir. Acc": f"{r.directional_accuracy:.2f}" if r.directional_accuracy else None,
            "Created": r.created_at.isoformat()
        } for r in records[:50]])
        st.dataframe(df)
