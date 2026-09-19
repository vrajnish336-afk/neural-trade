import streamlit as st
import pandas as pd
import sqlite3

def render_charts_tab(backtests: pd.DataFrame, conn: sqlite3.Connection):
    st.markdown("### ANALYTICS & PNL")
    
    if backtests.empty:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 40px; color: #8b949e;">
            <h4 style="margin:0;">DATA UNAVAILABLE</h4>
            <p style="margin: 10px 0 0 0;">No backtest data available to generate charts.</p>
        </div>
        """, unsafe_allow_html=True)
        return
        
    st.markdown("#### Equity Curve (From Trades)")
    selected_bt = st.selectbox("Select Backtest for Equity", backtests['id'].tolist())
    if selected_bt:
        try:
            trades = pd.read_sql(f"SELECT * FROM trades WHERE backtest_id = '{selected_bt}'", conn)
            if not trades.empty:
                trades['cumulative_pnl'] = trades['realized_pnl'].cumsum()
                st.line_chart(trades['cumulative_pnl'])
            else:
                st.write("No trades found for this backtest.")
        except Exception as e:
            st.error(f"Error loading trades: {e}")
