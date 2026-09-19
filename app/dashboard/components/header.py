import streamlit as st
from datetime import datetime

def render_header(dataset_identity: str = "N/A"):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    header_html = f"""
    <div class="terminal-header">
        <div class="header-title">AI TRADING RESEARCH TERMINAL</div>
        <div>
            <span class="status-badge badge-warning">PAPER / RESEARCH</span>
            <span class="status-badge badge-negative" style="margin-left:8px;">LIVE TRADING DISABLED</span>
            <span class="status-badge badge-positive" style="margin-left:8px;">ONLINE</span>
        </div>
        <div style="font-size: 0.85em; color: #8b949e;">
            Dataset: <span style="color:#c9d1d9;">{dataset_identity}</span> | {current_time}
        </div>
    </div>
    """
    st.markdown(header_html, unsafe_allow_html=True)
