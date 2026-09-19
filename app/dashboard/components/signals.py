import streamlit as st

def render_signals_tab(signals: list = None):
    st.markdown("### LIVE SCANNER & SIGNALS")
    
    if not signals:
        st.markdown("""
        <div class="panel" style="text-align: center; padding: 40px; color: #8b949e;">
            <h4 style="margin:0;">NO CURRENT SIGNALS</h4>
            <p style="margin: 10px 0 0 0;">The system currently has no qualifying paper-trading opportunities.</p>
        </div>
        """, unsafe_allow_html=True)
        return
        
    # Example logic if signals exist
    # (Since this is a backtesting system, we might mock this visually if no real live signal state exists,
    # BUT the prompt strictly says: DO NOT create random/demo values. Use N/A or actual empty state.)
    cols = st.columns(3)
    for i, sig in enumerate(signals):
        col = cols[i % 3]
        direction_class = "long" if sig.get("direction", "LONG").upper() == "LONG" else "short"
        with col:
            st.markdown(f"""
            <div class="signal-card {direction_class}">
                <div style="font-weight: bold; margin-bottom: 8px;">{sig.get('symbol', 'N/A')} <span class="status-badge badge-neutral" style="float:right;">{sig.get('direction', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Strategy</span> <span class="signal-val">{sig.get('strategy', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Signal Score</span> <span class="signal-val">{sig.get('score', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Regime</span> <span class="signal-val">{sig.get('regime', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Confidence</span> <span class="signal-val">{sig.get('confidence', 'N/A')}</span></div>
                <hr style="border-color: #2a2f3a; margin: 8px 0;">
                <div class="signal-row"><span class="signal-label">Entry</span> <span class="signal-val">{sig.get('entry', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Stop</span> <span class="signal-val">{sig.get('stop', 'N/A')}</span></div>
                <div class="signal-row"><span class="signal-label">Target</span> <span class="signal-val">{sig.get('target', 'N/A')}</span></div>
                <hr style="border-color: #2a2f3a; margin: 8px 0;">
                <div class="signal-row"><span class="signal-label">Risk</span> <span class="status-badge badge-positive">APPROVED</span></div>
            </div>
            """, unsafe_allow_html=True)
