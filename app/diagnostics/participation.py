from typing import Dict, Any

def calculate_participation_metrics(
    executed_entries: int,
    down_vetoes: int,
    unknown_vetoes: int,
    dup_blocked: int,
    closed_trades: int,
    open_positions: int,
    realized_pnl: float,
    unrealized_pnl: float,
    max_dd_pct: float
) -> Dict[str, Any]:
    """
    Calculates trade participation metrics safely for paper validation reports.
    """
    eligible_signals = executed_entries + down_vetoes + unknown_vetoes + dup_blocked
    participation_rate = round((executed_entries / eligible_signals * 100.0), 2) if eligible_signals > 0 else 0.0
    zero_exposure = (executed_entries == 0 and open_positions == 0 and closed_trades == 0)
    
    status_flag = "ZERO_EXPOSURE_SUPPRESSION" if zero_exposure else "ACTIVE_PARTICIPATION"
    warning = (
        "WARNING: Zero trade participation. $0.00 PnL and 0.00% DD reflect total market exposure suppression, not outperformance."
        if zero_exposure else None
    )
    
    return {
        "eligible_signals": eligible_signals,
        "executed_entries": executed_entries,
        "down_vetoes": down_vetoes,
        "unknown_vetoes": unknown_vetoes,
        "dup_blocked": dup_blocked,
        "closed_trades": closed_trades,
        "open_positions": open_positions,
        "participation_rate_pct": participation_rate,
        "zero_exposure": zero_exposure,
        "status_flag": status_flag,
        "warning": warning,
        "realized_pnl": round(realized_pnl, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "max_dd_pct": round(max_dd_pct, 2)
    }

def format_counterfactual_disclaimer() -> str:
    """Returns mandatory disclaimer for stateless counterfactual analysis."""
    return (
        "HYPOTHETICAL COUNTERFACTUAL NOTE: Results evaluate stateless single-signal forward traces. "
        "Concurrency limits, position-blocking constraints, and transaction fee/slippage costs are omitted."
    )
