import streamlit as st

def apply_terminal_theme():
    st.markdown("""
        <style>
            /* Global Dark Terminal Theme */
            .stApp {
                background-color: #0e1117 !important;
                color: #c9d1d9 !important;
                font-family: 'Consolas', 'Courier New', monospace;
            }
            
            /* Professional Header */
            .terminal-header {
                padding: 10px 15px;
                background-color: #151922;
                border-bottom: 2px solid #2a2f3a;
                border-radius: 5px;
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 1.1em;
            }
            .header-title {
                font-weight: bold;
                color: #ffffff;
                letter-spacing: 1px;
            }
            
            /* Reusable Status Badges */
            .status-badge {
                padding: 2px 8px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: 600;
                text-transform: uppercase;
                display: inline-block;
            }
            .badge-neutral { background-color: #2a2f3a; color: #c9d1d9; }
            .badge-positive { background-color: rgba(0, 200, 83, 0.15); color: #00c853; border: 1px solid #00c853; }
            .badge-negative { background-color: rgba(255, 77, 79, 0.15); color: #ff4d4f; border: 1px solid #ff4d4f; }
            .badge-warning { background-color: rgba(255, 176, 32, 0.15); color: #ffb020; border: 1px solid #ffb020; }
            
            /* Panels and Cards */
            .panel {
                background-color: #151922;
                border: 1px solid #2a2f3a;
                border-radius: 6px;
                padding: 15px;
                margin-bottom: 15px;
            }
            
            /* Metric Cards */
            .metric-card {
                background-color: #151922;
                border: 1px solid #2a2f3a;
                border-radius: 6px;
                padding: 15px;
                text-align: center;
                margin-bottom: 15px;
            }
            .metric-label {
                font-size: 0.8em;
                color: #8b949e;
                text-transform: uppercase;
                margin-bottom: 5px;
                font-weight: 600;
            }
            .metric-value {
                font-size: 1.4em;
                font-weight: bold;
                color: #ffffff;
            }
            .metric-positive { color: #00c853; }
            .metric-negative { color: #ff4d4f; }
            
            /* Signal Card */
            .signal-card {
                background-color: #151922;
                border: 1px solid #2a2f3a;
                border-left: 4px solid #8b949e;
                border-radius: 6px;
                padding: 12px;
                margin-bottom: 10px;
            }
            .signal-card.long { border-left-color: #00c853; }
            .signal-card.short { border-left-color: #ff4d4f; }
            .signal-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 4px;
            }
            .signal-label { color: #8b949e; font-size: 0.9em; }
            .signal-val { color: #c9d1d9; font-weight: bold; font-size: 0.9em; }
            
            /* Log Panel */
            .log-panel {
                background-color: #0d1117;
                border: 1px solid #2a2f3a;
                border-radius: 4px;
                padding: 10px;
                font-family: 'Consolas', monospace;
                font-size: 0.85em;
                height: 400px;
                overflow-y: auto;
                white-space: pre-wrap;
            }
            .log-info { color: #58a6ff; }
            .log-success { color: #3fb950; }
            .log-warning { color: #d29922; }
            .log-error { color: #f85149; }
            .log-meta { color: #8b949e; }
            
            /* Hide Streamlit default elements that clutter UI */
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)
