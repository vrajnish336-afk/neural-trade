import streamlit as st

def render_death_mode_banner(
    current_equity: float,
    initial_equity: float,
    survival_budget_pct: float = 0.50,
    is_active: bool = False,
    buffer_pct: float = 0.15
) -> bool:
    """
    Renders a prominent, blinking/red Neon UI banner in the Streamlit dashboard
    if Death Mode is active or equity is near the death threshold.

    Parameters:
        current_equity: Current portfolio dynamic equity.
        initial_equity: Initial portfolio equity.
        survival_budget_pct: Percentage of initial equity defining the death threshold (default 0.50).
        is_active: Explicit boolean override if Death Mode is already latched in engine.
        buffer_pct: Proximity buffer percentage to trigger 'near threshold' warning (default 0.15 -> within 15% above floor).

    Returns:
        bool: True if a banner was rendered, False otherwise.
    """
    if initial_equity <= 0:
        return False

    survival_threshold = initial_equity * survival_budget_pct
    near_threshold = survival_threshold * (1.0 + buffer_pct)

    if is_active or current_equity <= survival_threshold:
        st.markdown(f"""
        <style>
        @keyframes neon-death-blink {{
            0%, 100% {{
                opacity: 1;
                box-shadow: 0 0 25px #ff0033, inset 0 0 15px #ff0033;
                border-color: #ff0033;
            }}
            50% {{
                opacity: 0.35;
                box-shadow: 0 0 5px #ff0033;
                border-color: rgba(255, 0, 51, 0.4);
            }}
        }}
        .neon-death-banner {{
            background: rgba(255, 0, 51, 0.18);
            border: 3px solid #ff0033;
            border-radius: 10px;
            padding: 18px 24px;
            margin: 15px 0 25px 0;
            text-align: center;
            animation: neon-death-blink 1.2s infinite ease-in-out;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .neon-death-title {{
            color: #ff0033;
            font-size: 1.55rem;
            font-weight: 900;
            letter-spacing: 2px;
            text-shadow: 0 0 10px #ff0033, 0 0 20px #ff0033, 0 0 35px #ff0033;
            margin: 0 0 8px 0;
            text-transform: uppercase;
        }}
        .neon-death-body {{
            color: #ffffff;
            font-size: 1.05rem;
            font-weight: 600;
            text-shadow: 0 0 6px rgba(255, 255, 255, 0.8);
            margin: 0 0 6px 0;
        }}
        .neon-death-metrics {{
            color: #ffcccc;
            font-size: 0.92rem;
            font-weight: 500;
        }}
        </style>
        <div class="neon-death-banner">
            <div class="neon-death-title">💀 CRITICAL ALERT: DEATH MODE ACTIVE — SURVIVAL BUDGET BREACHED 💀</div>
            <div class="neon-death-body">
                SYSTEM PERMANENTLY HALTED. ALL TRADING SIGNALS AND OPERATIONS REJECTED TO SAFEGUARD REMAINING CAPITAL.
            </div>
            <div class="neon-death-metrics">
                Current Equity: <strong>${current_equity:,.2f}</strong> &le; Survival Floor: <strong>${survival_threshold:,.2f}</strong> ({survival_budget_pct * 100:.0f}% of Initial ${initial_equity:,.2f})
            </div>
        </div>
        """, unsafe_allow_html=True)
        return True

    elif current_equity <= near_threshold:
        st.markdown(f"""
        <style>
        @keyframes neon-warn-pulse {{
            0%, 100% {{
                box-shadow: 0 0 20px #ffaa00;
                border-color: #ffaa00;
            }}
            50% {{
                box-shadow: 0 0 8px #ffaa00;
                border-color: rgba(255, 170, 0, 0.5);
            }}
        }}
        .neon-warn-banner {{
            background: rgba(255, 170, 0, 0.14);
            border: 2px solid #ffaa00;
            border-radius: 8px;
            padding: 14px 20px;
            margin: 15px 0 20px 0;
            text-align: center;
            animation: neon-warn-pulse 2s infinite ease-in-out;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}
        .neon-warn-title {{
            color: #ffaa00;
            font-size: 1.3rem;
            font-weight: 800;
            letter-spacing: 1.5px;
            text-shadow: 0 0 10px #ffaa00;
            margin: 0 0 6px 0;
            text-transform: uppercase;
        }}
        .neon-warn-body {{
            color: #ffffff;
            font-size: 0.95rem;
            font-weight: 500;
            margin: 0;
        }}
        </style>
        <div class="neon-warn-banner">
            <div class="neon-warn-title">⚠️ WARNING: EQUITY NEAR DEATH MODE SURVIVAL THRESHOLD ⚠️</div>
            <div class="neon-warn-body">
                Current Dynamic Equity: <strong>${current_equity:,.2f}</strong> is within buffer of Death Threshold: <strong>${survival_threshold:,.2f}</strong> ({survival_budget_pct * 100:.0f}% floor). Trading halt imminent if losses continue.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return True

    return False
