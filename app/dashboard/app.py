import os
import sys

# Add project root to sys.path to resolve 'app' correctly and avoid shadowing
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
script_dir = os.path.dirname(os.path.abspath(__file__))

if project_root in sys.path:
    sys.path.remove(project_root)
sys.path.insert(0, project_root)

if script_dir in sys.path:
    sys.path.remove(script_dir)

import streamlit as st
import pandas as pd
import sqlite3
import json
from app.config import config
from app.dashboard.styles import apply_terminal_theme
from app.dashboard.components.header import render_header
from app.dashboard.components.metrics import render_metrics_bar
from app.dashboard.components.signals import render_signals_tab
from app.dashboard.components.positions import render_positions_tab
from app.dashboard.components.charts import render_charts_tab
from app.dashboard.components.logs import render_logs_tab
from app.dashboard.components.research import render_research_tab
from app.dashboard.components.observability import render_observability_tab

# Initialize Streamlit Page Config
st.set_page_config(page_title="AI Trading Bot (RESEARCH)", layout="wide", initial_sidebar_state="expanded")

# Apply custom dark terminal theme
apply_terminal_theme()

def get_conn():
    return sqlite3.connect(config.DB_PATH)

# Fetch Data
try:
    with get_conn() as conn:
        backtests = pd.read_sql("SELECT * FROM backtests ORDER BY timestamp DESC", conn)
        analytics_runs = pd.read_sql("SELECT * FROM analytics_runs ORDER BY timestamp DESC", conn)
        try:
            research_experiments = pd.read_sql("SELECT * FROM research_experiments ORDER BY timestamp DESC", conn)
        except Exception:
            research_experiments = pd.DataFrame()
            
        # Get active metrics if available from latest backtest or experiment
        latest_metrics = {
            'active_pnl': 'N/A',
            'win_rate': 'N/A',
            'active_trades': 'N/A',
            'max_drawdown': 'N/A'
        }
        dataset_id = "N/A"
        
        if not research_experiments.empty:
            exp_row = research_experiments.iloc[0]
            exp_json = json.loads(exp_row['experiment_json'])
            dataset_id = exp_json.get('dataset_id', 'N/A')
            oos = exp_json.get('out_of_sample_report')
            if oos:
                tm = oos.get('trade_metrics', {})
                em = oos.get('equity_metrics', {})
                latest_metrics['active_pnl'] = f"{em.get('total_return_pct', 0):+.2f}%"
                latest_metrics['win_rate'] = f"{tm.get('win_rate', 0):.2f}%"
                latest_metrics['active_trades'] = str(tm.get('total_trades', 0))
                latest_metrics['max_drawdown'] = f"{em.get('max_drawdown_pct', 0):.2f}%"

except Exception as e:
    backtests = pd.DataFrame()
    analytics_runs = pd.DataFrame()
    research_experiments = pd.DataFrame()
    dataset_id = "N/A"
    latest_metrics = {'active_pnl': 'N/A', 'win_rate': 'N/A', 'active_trades': 'N/A', 'max_drawdown': 'N/A'}
    st.error(f"Failed to load data: {e}")

# Render Sidebar
st.sidebar.markdown("""
<div class="panel" style="margin-bottom: 20px;">
    <div style="font-weight: bold; margin-bottom: 10px; color: #fff;">SYSTEM STATUS</div>
    <div style="margin-bottom: 5px;">PAPER TRADING: <span class="status-badge badge-positive" style="float:right;">ENABLED</span></div>
    <div>LIVE TRADING: <span class="status-badge badge-negative" style="float:right;">DISABLED</span></div>
</div>
""", unsafe_allow_html=True)
st.sidebar.info("This system is permanently firewalled against live execution.")

st.sidebar.markdown("### Dashboard Filters")
st.sidebar.markdown("<small style='color:#8b949e'>These filters only affect data visualization.</small>", unsafe_allow_html=True)
st.sidebar.selectbox("Symbol", ["ALL", "BTC/USD", "ETH/USD", "SOL/USD"])
st.sidebar.selectbox("Strategy", ["ALL", "TrendFollowing", "MeanReversion"])
st.sidebar.selectbox("Regime", ["ALL", "TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY"])

# Render Header and Metrics
render_header(dataset_identity=dataset_id)
render_metrics_bar(latest_metrics)

# Render Tabs
st.markdown("<br>", unsafe_allow_html=True)
tab0, tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11, tab12, tab13, tab14, tab15, tab16, tab17, tab18, tab19 = st.tabs([
    "0. TRADER DECISION",
    "1. LIVE SCANNER & SIGNALS",
    "2. ACTIVE POSITIONS / FOCUS VIEW",
    "3. ANALYTICS & PNL",
    "4. SYSTEM TERMINAL LOGS",
    "5. RESEARCH & VALIDATION",
    "6. OBSERVABILITY",
    "7. LESSONS & EVOLUTION",
    "8. PRICE TRAJECTORY LAB",
    "9. WORLD INTELLIGENCE",
    "10. AI COPILOT",
    "11. AI RESEARCH SANDBOX",
    "12. EXPERIMENT INTELLIGENCE",
    "13. SELF-EVOLUTION LAB",
    "14. CONTINUOUS RESEARCH",
    "15. EVIDENCE GRAPH",
    "16. RESEARCH DECISION CENTER",
    "17. KNOWLEDGE SYNTHESIS & HYPOTHESIS LAB",
    "18. PHASE 60 PAPER EVOLUTION",
    "19. SYSTEM CONFIGURATION"
])


with tab0:
    from app.dashboard.components.trader_decision import render_trader_decision_tab
    render_trader_decision_tab()

with tab1:
    render_signals_tab(signals=None)

with tab2:
    render_positions_tab(positions=None)

with tab3:
    with get_conn() as connection:
        render_charts_tab(backtests, connection)

with tab4:
    render_logs_tab()

with tab5:
    with get_conn() as connection:
        render_research_tab(backtests, analytics_runs, research_experiments, connection)

with tab6:
    with get_conn() as connection:
        render_observability_tab(analytics_runs, connection)

with tab7:
    with get_conn() as connection:
        from app.dashboard.components.learning import render_learning_tab
        render_learning_tab(connection)

with tab8:
    with get_conn() as connection:
        from app.dashboard.components.forecasting import render_forecasting_tab
        render_forecasting_tab(connection)

with tab9:
    with get_conn() as connection:
        from app.dashboard.components.intelligence import render_intelligence_tab
        render_intelligence_tab(connection)

with tab10:
    with get_conn() as connection:
        from app.dashboard.components.copilot import render_copilot_tab
        render_copilot_tab(connection)

with tab11:
    with get_conn() as connection:
        from app.dashboard.components.sandbox import render_sandbox_tab
        render_sandbox_tab(connection)

with tab12:
    with get_conn() as connection:
        from app.dashboard.components.experiment_intelligence import render_experiment_intelligence_tab
        render_experiment_intelligence_tab(connection)

with tab13:
    with get_conn() as connection:
        from app.dashboard.components.evolution import render_evolution_tab
        render_evolution_tab(connection)

with tab14:
    with get_conn() as connection:
        from app.dashboard.components.continuous import render_continuous_tab
        render_continuous_tab(connection)

with tab15:
    with get_conn() as connection:
        from app.dashboard.components.evidence_graph import render_evidence_graph_tab
        render_evidence_graph_tab(connection)

with tab16:
    with get_conn() as connection:
        from app.dashboard.components.planner import render_planner_tab
        render_planner_tab(connection)

with tab17:
    with get_conn() as connection:
        from app.dashboard.components.synthesis import render_synthesis_tab
        render_synthesis_tab(connection)

with tab18:
    with get_conn() as connection:
        from app.dashboard.components.phase60_evolution import render_phase60_evolution_tab
        render_phase60_evolution_tab(connection)

with tab19:
    from app.dashboard.components.system_config import render_system_config_tab
    render_system_config_tab()
