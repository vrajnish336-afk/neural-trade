import streamlit as st

def render_positions_tab(positions: list = None):
    st.markdown("### ACTIVE POSITIONS / FOCUS VIEW")
    
    if not positions:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 40px; color: #8b949e;">
            <h4 style="margin:0;">NO ACTIVE PAPER POSITIONS</h4>
            <p style="margin: 10px 0 0 0;">There are currently no open positions in the paper-trading portfolio.</p>
        </div>
        """, unsafe_allow_html=True)
        return
        
    for pos in positions:
        pnl = pos.get('unrealized_pnl', 0)
        pnl_class = "metric-positive" if pnl >= 0 else "metric-negative"
        st.markdown(f"""
        <div class="panel" style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <div style="font-weight: bold; font-size: 1.1em; color: #fff;">{pos.get('symbol', 'N/A')}</div>
                <div style="font-size: 0.9em; color: #8b949e;">{pos.get('direction', 'N/A')} | {pos.get('strategy', 'N/A')}</div>
            </div>
            <div style="text-align: right;">
                <div class="metric-label">Unrealized PnL</div>
                <div class="metric-value {pnl_class}">{pnl:.2f}%</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
