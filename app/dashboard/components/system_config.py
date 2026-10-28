import streamlit as st
import pandas as pd
from app.config import config
from app.learning.paper_evolution_engine import SAFE_PARAMETERS
from app.risk.limits import PortfolioRiskLimits
from app.execution.paper_repository import PaperRepository
from app.dashboard.components.death_mode_banner import render_death_mode_banner

def render_system_config_tab():
    st.markdown("## SYSTEM CONFIGURATION & HEALTH")
    st.warning("READ-ONLY VIEW. PAPER TRADING ONLY. LIVE TRADING DISABLED.")
    
    # 1. Instantiate PortfolioRiskLimits reflecting actual runtime risk parameters
    try:
        repo = PaperRepository()
        portfolio = repo.get_or_create_portfolio("default_paper")
        initial_equity = float(portfolio['initial_equity']) if portfolio and 'initial_equity' in portfolio.keys() else 10000.0
        current_equity = float(portfolio['current_equity']) if portfolio and 'current_equity' in portfolio.keys() else initial_equity
        closed_positions = repo.get_closed_positions("default_paper", limit=1000)
    except Exception:
        initial_equity = 10000.0
        current_equity = 10000.0
        closed_positions = []

    # Runtime parameters
    max_pos = int(getattr(config, "MAX_POSITIONS", 5)) if hasattr(config, "MAX_POSITIONS") else 5
    max_exp = float(getattr(config, "MAX_EXPOSURE_PCT", 1.0)) if hasattr(config, "MAX_EXPOSURE_PCT") else 1.0
    daily_limit = float(getattr(config, "DAILY_LOSS_LIMIT_PCT", 0.05)) if hasattr(config, "DAILY_LOSS_LIMIT_PCT") else 0.05
    streak_thresh = int(getattr(config, "LOSS_STREAK_THRESHOLD", 3)) if hasattr(config, "LOSS_STREAK_THRESHOLD") else 3
    cooldown = int(getattr(config, "COOLDOWN_BARS", 5)) if hasattr(config, "COOLDOWN_BARS") else 5
    dd_halt = float(getattr(config, "MAX_DRAWDOWN_HALT_PCT", 20.0)) if hasattr(config, "MAX_DRAWDOWN_HALT_PCT") else 20.0
    survival_pct = float(getattr(config, "SURVIVAL_BUDGET_PCT", 0.50)) if hasattr(config, "SURVIVAL_BUDGET_PCT") else 0.50

    limits = PortfolioRiskLimits(
        initial_equity=initial_equity,
        max_positions=max_pos,
        max_exposure_pct=max_exp,
        daily_loss_limit_pct=daily_limit,
        loss_streak_threshold=streak_thresh,
        cooldown_bars=cooldown,
        max_drawdown_halt_pct=dd_halt,
        survival_budget_pct=survival_pct
    )
    if closed_positions:
        limits.rehydrate_from_paper_ledger(closed_positions)

    # Prominent Blinking Neon Banner if Death Mode Active or Near Threshold
    render_death_mode_banner(
        current_equity=current_equity,
        initial_equity=initial_equity,
        survival_budget_pct=survival_pct
    )

    # 2. Display Live Instantiated PortfolioRiskLimits using Styled Neon Metric Cards
    st.markdown("### 🛡️ Live Risk Engine Barrier Parameters (`PortfolioRiskLimits`)")
    st.markdown("""
    <div style="font-size: 0.85em; color: #00f0ff; margin-bottom: 15px; letter-spacing: 0.5px; text-shadow: 0 0 5px rgba(0, 240, 255, 0.4);">
        ⚡ DIRECT TELEMETRY FROM INSTANTIATED RISK LIMITS ENFORCED BY THE EXECUTION GATEWAY
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Max Positions", limits.max_positions)
    with col2:
        st.metric("Max Exposure", f"{limits.max_exposure_pct * 100:.1f}%")
    with col3:
        st.metric("Daily Loss Barrier", f"{limits.daily_loss_limit_pct * 100:.1f}%")
    with col4:
        st.metric("Max Drawdown Halt", f"{limits.max_drawdown_halt_pct:.1f}%")

    col5, col6, col7, col8 = st.columns(4)
    with col5:
        st.metric("Loss Streak Limit", f"{limits.loss_streak_threshold} losses")
    with col6:
        st.metric("Cooldown Duration", f"{limits.cooldown_bars} bars")
    with col7:
        st.metric("Active Loss Streak", limits.loss_streak)
    with col8:
        st.metric("24h Rolling Loss", f"${limits.daily_loss:,.2f}")

    # 3. Global Safety & Config Table
    st.markdown("### Global Safety & Risk Configuration")
    
    risk_data = [
        {"Parameter": "PAPER_TRADING", "Value": str(getattr(config, "PAPER_TRADING", "Unavailable"))},
        {"Parameter": "LIVE_TRADING", "Value": str(getattr(config, "LIVE_TRADING", "Unavailable"))},
        {"Parameter": "KRONOS_STRONG_VETO_ENABLED", "Value": str(getattr(config, "KRONOS_STRONG_VETO_ENABLED", "Unavailable"))},
        {"Parameter": "MAX_POSITION_SIZE", "Value": str(getattr(config, "MAX_POSITION_SIZE", "Unavailable"))},
        {"Parameter": "RISK_PER_TRADE", "Value": str(getattr(config, "RISK_PER_TRADE", "Unavailable"))},
        {"Parameter": "DAILY_LOSS_LIMIT", "Value": str(getattr(config, "DAILY_LOSS_LIMIT", "Unavailable"))},
        {"Parameter": "LOSS_STREAK_THRESHOLD", "Value": str(getattr(config, "LOSS_STREAK_THRESHOLD", "Unavailable"))},
        {"Parameter": "MAX_POSITIONS", "Value": str(getattr(config, "MAX_POSITIONS", "Unavailable"))},
        {"Parameter": "SURVIVAL_BUDGET_PCT", "Value": str(getattr(config, "SURVIVAL_BUDGET_PCT", "Unavailable"))}
    ]
    
    st.table(pd.DataFrame(risk_data))
    
    st.markdown("### Signal Thresholds & Strategy Configurations")
    
    # Base fallback
    strategy_data = [
        {"Parameter": "Global MIN_SIGNAL_SCORE", "Value": str(getattr(config, "MIN_SIGNAL_SCORE", "Unavailable"))}
    ]
    
    # Seed with base strategies known to the system to guarantee they always render
    verified_strats = {"BreakoutStrategy", "TrendFollowingStrategy", "MeanReversionStrategy"}
    import os
    
    # Discover verified strategies robustly from DB/Env
    try:
        from app.learning.paper_evolution_repository import PaperEvolutionRepository
        from app.learning.paper_evolution_models import LessonState
        
        repo_evo = PaperEvolutionRepository()
        
        # 1. From lessons
        for l in repo_evo.get_lessons():
            if getattr(l, 'confidence_status', '') in ("VALIDATED", LessonState.VALIDATED) and getattr(l, 'strategy', 'UNKNOWN') != "UNKNOWN":
                verified_strats.add(l.strategy)
                
        # 2. From proposals
        for p in repo_evo.get_proposals():
            if p.affected_parameter and p.affected_parameter.endswith("_MIN_SCORE"):
                strat = p.affected_parameter.replace("_MIN_SCORE", "")
                verified_strats.add(strat)
                
    except Exception:
        pass # Ignore DB errors, continue with base strats and config
        
    # 3. From os.environ (in case injected via .env)
    for key in os.environ.keys():
        if key.endswith("_MIN_SCORE") and not key.startswith("__"):
            strat = key.replace("_MIN_SCORE", "")
            verified_strats.add(strat)
            
    # 4. From config attributes (including class attributes, properties)
    for key in dir(config):
        if key.endswith("_MIN_SCORE") and not key.startswith("__"):
            strat = key.replace("_MIN_SCORE", "")
            verified_strats.add(strat)
    
    for strat in sorted(verified_strats):
        # Resolve actual runtime value. config.get_strategy_min_score uses fallback.
        val = config.get_strategy_min_score(strat)
        if val == config.MIN_SIGNAL_SCORE:
            # If it fell back, check if os.environ explicitly overrides it for display purposes
            env_val = os.environ.get(f"{strat}_MIN_SCORE")
            if env_val is not None:
                try:
                    val = float(env_val)
                except ValueError:
                    pass
        strategy_data.append({"Parameter": f"Strategy: {strat}", "Value": str(val)})
                
    st.table(pd.DataFrame(strategy_data))
    
    st.markdown("### Evolution Allowlist")
    allowlist_data = [{"Allowed Mutable Parameter": p} for p in SAFE_PARAMETERS]
    allowlist_data.append({"Allowed Mutable Parameter": "*_MIN_SCORE (Dynamic Strategy Thresholds)"})
    st.table(pd.DataFrame(allowlist_data))
