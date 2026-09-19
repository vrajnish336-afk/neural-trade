import streamlit as st
import pandas as pd
from app.config import config
from app.learning.paper_evolution_engine import SAFE_PARAMETERS

def render_system_config_tab():
    st.markdown("## SYSTEM CONFIGURATION & HEALTH")
    st.warning("READ-ONLY VIEW. PAPER TRADING ONLY. LIVE TRADING DISABLED.")
    
    st.markdown("### Global Safety & Risk Limits")
    
    risk_data = [
        {"Parameter": "PAPER_TRADING", "Value": str(getattr(config, "PAPER_TRADING", "Unavailable"))},
        {"Parameter": "LIVE_TRADING", "Value": str(getattr(config, "LIVE_TRADING", "Unavailable"))},
        {"Parameter": "MAX_POSITION_SIZE", "Value": str(getattr(config, "MAX_POSITION_SIZE", "Unavailable"))},
        {"Parameter": "RISK_PER_TRADE", "Value": str(getattr(config, "RISK_PER_TRADE", "Unavailable"))},
        {"Parameter": "DAILY_LOSS_LIMIT", "Value": str(getattr(config, "DAILY_LOSS_LIMIT", "Unavailable"))},
        {"Parameter": "LOSS_STREAK_THRESHOLD", "Value": str(getattr(config, "LOSS_STREAK_THRESHOLD", "Unavailable"))},
        {"Parameter": "MAX_POSITIONS", "Value": str(getattr(config, "MAX_POSITIONS", "Unavailable"))}
    ]
    
    st.dataframe(pd.DataFrame(risk_data), use_container_width=True)
    
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
        
        repo = PaperEvolutionRepository()
        
        # 1. From lessons
        for l in repo.get_lessons():
            if getattr(l, 'confidence_status', '') in ("VALIDATED", LessonState.VALIDATED) and getattr(l, 'strategy', 'UNKNOWN') != "UNKNOWN":
                verified_strats.add(l.strategy)
                
        # 2. From proposals
        for p in repo.get_proposals():
            if p.affected_parameter and p.affected_parameter.endswith("_MIN_SCORE"):
                strat = p.affected_parameter.replace("_MIN_SCORE", "")
                verified_strats.add(strat)
                
    except Exception as e:
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
                
    st.dataframe(pd.DataFrame(strategy_data), use_container_width=True)
    
    st.markdown("### Evolution Allowlist")
    allowlist_data = [{"Allowed Mutable Parameter": p} for p in SAFE_PARAMETERS]
    allowlist_data.append({"Allowed Mutable Parameter": "*_MIN_SCORE (Dynamic Strategy Thresholds)"})
    st.dataframe(pd.DataFrame(allowlist_data), use_container_width=True)
