import streamlit as st

def apply_terminal_theme():
    """
    Applies an ultra-modern Neon Cyberpunk dark theme with high-contrast text,
    neon cyan/magenta/green glowing accents, glassmorphic panels, and animated feedback.
    """
    st.markdown("""
        <style>
            /* Global Cyberpunk Dark Theme */
            .stApp {
                background-color: #07090e !important;
                background-image: 
                    radial-gradient(circle at 15% 15%, rgba(0, 240, 255, 0.04) 0%, transparent 40%),
                    radial-gradient(circle at 85% 85%, rgba(255, 0, 127, 0.04) 0%, transparent 40%),
                    linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
                    linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px) !important;
                background-size: 100% 100%, 100% 100%, 30px 30px, 30px 30px !important;
                color: #e0e6ed !important;
                font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', 'Courier New', monospace !important;
            }

            /* Neon Typography */
            h1, h2, h3, h4 {
                font-family: 'JetBrains Mono', 'Consolas', monospace !important;
                color: #ffffff !important;
                letter-spacing: 0.5px;
            }
            h1, h2 {
                text-shadow: 0 0 10px rgba(0, 240, 255, 0.6), 0 0 20px rgba(0, 240, 255, 0.2);
            }
            h3, h4 {
                color: #00f0ff !important;
                text-shadow: 0 0 8px rgba(0, 240, 255, 0.4);
            }
            
            /* Professional Cyberpunk Header */
            .terminal-header {
                padding: 14px 20px;
                background: linear-gradient(135deg, rgba(12, 16, 29, 0.95) 0%, rgba(20, 14, 30, 0.95) 100%);
                border: 1px solid rgba(0, 240, 255, 0.4);
                border-bottom: 2px solid #00f0ff;
                border-radius: 8px;
                box-shadow: 0 0 18px rgba(0, 240, 255, 0.2), inset 0 0 15px rgba(0, 240, 255, 0.05);
                margin-bottom: 20px;
                display: flex;
                justify-content: space-between;
                align-items: center;
                font-size: 1.1em;
            }
            .header-title {
                font-weight: 800;
                color: #ffffff;
                letter-spacing: 1.5px;
                text-shadow: 0 0 12px #00f0ff, 0 0 25px rgba(0, 240, 255, 0.4);
            }
            
            /* Neon Status Badges */
            .status-badge {
                padding: 4px 10px;
                border-radius: 4px;
                font-size: 0.85em;
                font-weight: 700;
                text-transform: uppercase;
                display: inline-block;
                letter-spacing: 0.8px;
            }
            .badge-neutral { 
                background-color: rgba(42, 47, 58, 0.6); 
                color: #c9d1d9; 
                border: 1px solid #2a2f3a; 
            }
            .badge-positive { 
                background: rgba(0, 255, 157, 0.15); 
                color: #00ff9d; 
                border: 1px solid #00ff9d; 
                box-shadow: 0 0 10px rgba(0, 255, 157, 0.35); 
            }
            .badge-negative { 
                background: rgba(255, 0, 127, 0.15); 
                color: #ff007f; 
                border: 1px solid #ff007f; 
                box-shadow: 0 0 10px rgba(255, 0, 127, 0.35); 
            }
            .badge-warning { 
                background: rgba(255, 184, 0, 0.15); 
                color: #ffb800; 
                border: 1px solid #ffb800; 
                box-shadow: 0 0 10px rgba(255, 184, 0, 0.35); 
            }
            
            /* Panels and Cards */
            .panel {
                background: linear-gradient(135deg, rgba(12, 16, 29, 0.85) 0%, rgba(18, 14, 30, 0.85) 100%);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 8px;
                padding: 18px;
                margin-bottom: 18px;
                box-shadow: 0 0 15px rgba(0, 240, 255, 0.1), inset 0 0 15px rgba(0, 240, 255, 0.03);
                backdrop-filter: blur(8px);
                transition: all 0.3s ease;
            }
            .panel:hover {
                border-color: rgba(0, 240, 255, 0.6);
                box-shadow: 0 0 25px rgba(0, 240, 255, 0.25), inset 0 0 20px rgba(0, 240, 255, 0.06);
            }
            
            /* Custom Metric Cards */
            .metric-card {
                background: linear-gradient(135deg, rgba(12, 16, 29, 0.9) 0%, rgba(20, 12, 30, 0.9) 100%);
                border: 1px solid rgba(0, 240, 255, 0.35);
                border-radius: 8px;
                padding: 16px;
                text-align: center;
                margin-bottom: 15px;
                box-shadow: 0 0 14px rgba(0, 240, 255, 0.15), inset 0 0 12px rgba(0, 240, 255, 0.04);
                transition: all 0.25s ease-in-out;
            }
            .metric-card:hover {
                border-color: #00f0ff;
                box-shadow: 0 0 22px rgba(0, 240, 255, 0.4), inset 0 0 15px rgba(0, 240, 255, 0.08);
                transform: translateY(-2px);
            }
            .metric-label {
                font-size: 0.8em;
                color: #00f0ff;
                text-transform: uppercase;
                margin-bottom: 6px;
                font-weight: 700;
                letter-spacing: 1px;
                text-shadow: 0 0 6px rgba(0, 240, 255, 0.5);
            }
            .metric-value {
                font-size: 1.5em;
                font-weight: 800;
                color: #ffffff;
                text-shadow: 0 0 10px rgba(255, 255, 255, 0.5);
                font-family: 'JetBrains Mono', 'Consolas', monospace;
            }
            .metric-positive { 
                color: #00ff9d !important; 
                text-shadow: 0 0 12px rgba(0, 255, 157, 0.6) !important; 
            }
            .metric-negative { 
                color: #ff007f !important; 
                text-shadow: 0 0 12px rgba(255, 0, 127, 0.6) !important; 
            }
            
            /* Streamlit Native st.metric Glowing Cards */
            [data-testid="stMetric"] {
                background: linear-gradient(135deg, rgba(10, 15, 30, 0.9) 0%, rgba(18, 12, 30, 0.9) 100%) !important;
                border: 1px solid rgba(0, 240, 255, 0.35) !important;
                border-radius: 8px !important;
                padding: 12px 16px !important;
                box-shadow: 0 0 12px rgba(0, 240, 255, 0.15), inset 0 0 10px rgba(0, 240, 255, 0.05) !important;
                transition: all 0.3s ease-in-out !important;
            }
            [data-testid="stMetric"]:hover {
                border-color: #00f0ff !important;
                box-shadow: 0 0 20px rgba(0, 240, 255, 0.4), inset 0 0 15px rgba(0, 240, 255, 0.1) !important;
                transform: translateY(-2px) !important;
            }
            [data-testid="stMetricLabel"] {
                color: #00f0ff !important;
                font-size: 0.8em !important;
                font-weight: 700 !important;
                letter-spacing: 1px !important;
                text-transform: uppercase !important;
                text-shadow: 0 0 5px rgba(0, 240, 255, 0.5) !important;
            }
            [data-testid="stMetricValue"] {
                color: #ffffff !important;
                font-size: 1.4em !important;
                font-weight: 800 !important;
                text-shadow: 0 0 10px rgba(255, 255, 255, 0.6) !important;
                font-family: 'JetBrains Mono', 'Consolas', monospace !important;
            }
            
            /* Signal Card */
            .signal-card {
                background: linear-gradient(135deg, rgba(12, 16, 29, 0.9) 0%, rgba(20, 12, 30, 0.9) 100%);
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-left: 5px solid #00f0ff;
                border-radius: 6px;
                padding: 14px;
                margin-bottom: 12px;
                box-shadow: 0 0 12px rgba(0, 240, 255, 0.15);
            }
            .signal-card.long { 
                border-left-color: #00ff9d; 
                box-shadow: 0 0 15px rgba(0, 255, 157, 0.2); 
            }
            .signal-card.short { 
                border-left-color: #ff007f; 
                box-shadow: 0 0 15px rgba(255, 0, 127, 0.2); 
            }
            .signal-row {
                display: flex;
                justify-content: space-between;
                margin-bottom: 5px;
            }
            .signal-label { color: #8b949e; font-size: 0.9em; }
            .signal-val { color: #ffffff; font-weight: bold; font-size: 0.9em; }
            
            /* Neon Interactive Buttons */
            .stButton > button {
                background: linear-gradient(135deg, rgba(0, 240, 255, 0.15) 0%, rgba(255, 0, 127, 0.15) 100%) !important;
                border: 1px solid #00f0ff !important;
                color: #00f0ff !important;
                font-weight: 700 !important;
                letter-spacing: 1.2px !important;
                text-transform: uppercase !important;
                border-radius: 6px !important;
                box-shadow: 0 0 14px rgba(0, 240, 255, 0.35) !important;
                transition: all 0.25s ease-in-out !important;
                font-family: 'JetBrains Mono', 'Consolas', monospace !important;
            }
            .stButton > button:hover {
                background: linear-gradient(135deg, rgba(0, 240, 255, 0.3) 0%, rgba(255, 0, 127, 0.3) 100%) !important;
                border-color: #ff007f !important;
                color: #ffffff !important;
                box-shadow: 0 0 25px rgba(255, 0, 127, 0.65), 0 0 10px #00f0ff !important;
                transform: scale(1.02) !important;
            }
            
            /* Cyberpunk Tabs */
            button[data-baseweb="tab"] {
                background-color: transparent !important;
                color: #7d8b99 !important;
                font-family: 'JetBrains Mono', 'Consolas', monospace !important;
                font-size: 0.85em !important;
                font-weight: 600 !important;
                border-bottom: 2px solid transparent !important;
                transition: all 0.2s ease !important;
                padding-top: 8px !important;
                padding-bottom: 8px !important;
            }
            button[data-baseweb="tab"]:hover {
                color: #00f0ff !important;
                text-shadow: 0 0 8px rgba(0, 240, 255, 0.6) !important;
            }
            button[data-baseweb="tab"][aria-selected="true"] {
                color: #00f0ff !important;
                border-bottom: 2px solid #00f0ff !important;
                text-shadow: 0 0 12px #00f0ff !important;
            }
            
            /* Status Indicators & Alerts */
            .stAlert {
                background-color: rgba(12, 16, 29, 0.9) !important;
                border-radius: 8px !important;
                box-shadow: 0 0 15px rgba(0, 240, 255, 0.2) !important;
            }
            [data-testid="stStatusWidget"], .stStatus {
                background: linear-gradient(135deg, rgba(12, 16, 29, 0.95) 0%, rgba(18, 12, 30, 0.95) 100%) !important;
                border: 1px solid #00f0ff !important;
                border-radius: 8px !important;
                box-shadow: 0 0 18px rgba(0, 240, 255, 0.3) !important;
            }
            
            /* Log Panel */
            .log-panel {
                background-color: #05070c;
                border: 1px solid rgba(0, 240, 255, 0.3);
                border-radius: 6px;
                padding: 12px;
                font-family: 'JetBrains Mono', 'Consolas', monospace;
                font-size: 0.85em;
                height: 400px;
                overflow-y: auto;
                white-space: pre-wrap;
                box-shadow: inset 0 0 20px rgba(0, 0, 0, 0.8);
            }
            .log-info { color: #00f0ff; text-shadow: 0 0 5px rgba(0, 240, 255, 0.4); }
            .log-success { color: #00ff9d; text-shadow: 0 0 5px rgba(0, 255, 157, 0.4); }
            .log-warning { color: #ffb800; text-shadow: 0 0 5px rgba(255, 184, 0, 0.4); }
            .log-error { color: #ff007f; text-shadow: 0 0 5px rgba(255, 0, 127, 0.4); }
            .log-meta { color: #7d8b99; }
            
            /* Tables */
            div[data-testid="stTable"] table {
                background-color: #0a0d17 !important;
                border: 1px solid rgba(0, 240, 255, 0.25) !important;
                border-radius: 6px !important;
                color: #e0e6ed !important;
            }
            div[data-testid="stTable"] th {
                background-color: #101525 !important;
                color: #00f0ff !important;
                border-bottom: 2px solid #00f0ff !important;
                text-transform: uppercase !important;
                letter-spacing: 0.8px !important;
            }
            div[data-testid="stTable"] tr:nth-child(even) {
                background-color: rgba(255, 255, 255, 0.02) !important;
            }

            /* Hide Streamlit default elements that clutter UI */
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
        </style>
    """, unsafe_allow_html=True)

# Alias for explicit calls
apply_neon_theme = apply_terminal_theme
