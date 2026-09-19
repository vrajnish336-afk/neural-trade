import streamlit as st
from typing import Dict, Any

def render_metrics_bar(metrics_data: Dict[str, Any]):
    """
    Renders the compact professional metrics bar using Streamlit columns and custom CSS.
    metrics_data is expected to contain:
    - active_pnl
    - win_rate
    - active_trades
    - max_drawdown
    """
    
    active_pnl = metrics_data.get('active_pnl', 'N/A')
    win_rate = metrics_data.get('win_rate', 'N/A')
    active_trades = metrics_data.get('active_trades', 'N/A')
    max_drawdown = metrics_data.get('max_drawdown', 'N/A')
    
    def get_color_class(val):
        if val == 'N/A': return ''
        try:
            f_val = float(str(val).replace('%', '').replace('+', ''))
            if f_val > 0: return 'metric-positive'
            if f_val < 0: return 'metric-negative'
        except:
            pass
        return ''

    cols = st.columns(5)
    
    with cols[0]:
        pnl_class = get_color_class(active_pnl)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">ACTIVE PnL</div>
            <div class="metric-value {pnl_class}">{active_pnl}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">WIN RATE</div>
            <div class="metric-value">{win_rate}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">ACTIVE TRADES</div>
            <div class="metric-value">{active_trades}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with cols[3]:
        dd_class = get_color_class(max_drawdown)
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">MAX DRAWDOWN</div>
            <div class="metric-value {dd_class}">{max_drawdown}</div>
        </div>
        """, unsafe_allow_html=True)
        
    with cols[4]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">SYSTEM MODE</div>
            <div class="metric-value" style="color: #ffb020;">PAPER</div>
        </div>
        """, unsafe_allow_html=True)
