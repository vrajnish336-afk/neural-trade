import copy
from typing import Dict, Any, Callable, List
from app.core.models import MarketBar
from app.backtesting.models import CostConfig
from app.backtesting.engine import BacktestEngine
from app.diagnostics.telemetry import telemetry

def run_filter_ablation(
    bars: List[MarketBar],
    engine_factory: Callable[[CostConfig, bool, bool, bool], BacktestEngine],
    base_cost: CostConfig
) -> Dict[str, Dict[str, Any]]:
    """
    Evaluates pipeline dropping different filters.
    Requires engine_factory to accept flags for (use_news, use_anomaly, use_fakeout).
    """
    results = {}
    
    # We turn on diagnostics for ablation
    telemetry.enabled = True
    
    conditions = {
        "BASELINE": (False, False, False),
        "BASELINE + NEWS": (True, False, False),
        "BASELINE + ANOMALY": (False, True, False),
        "BASELINE + FAKEOUT": (False, False, True),
        "BASELINE + ALL FILTERS": (True, True, True)
    }
    
    for name, (news, anomaly, fakeout) in conditions.items():
        telemetry.reset()
        telemetry.enabled = True
        
        engine = engine_factory(base_cost, news, anomaly, fakeout)
        res = engine.run(bars)
        
        results[name] = {
            "total_trades": res.number_of_trades,
            "return_pct": res.total_return_pct,
            "market_bars": telemetry.stage_counts.get("MARKET_BARS", 0),
            "strategy_signals": telemetry.stage_counts.get("STRATEGY_SIGNALS", 0),
            "ensemble_signals": telemetry.stage_counts.get("ENSEMBLE_SIGNALS", 0),
            "risk_approved": telemetry.stage_counts.get("RISK_APPROVED", 0)
        }
        
    return results

def run_strategy_ablation(
    bars: List[MarketBar],
    engine_factory: Callable[[str], BacktestEngine]
) -> Dict[str, Dict[str, Any]]:
    """
    Evaluates individual strategies vs Ensemble.
    engine_factory takes a string: "TrendFollowing", "Breakout", "MeanReversion", "Ensemble"
    """
    results = {}
    
    for st_name in ["TrendFollowing", "Breakout", "MeanReversion", "Ensemble"]:
        telemetry.reset()
        telemetry.enabled = True
        
        engine = engine_factory(st_name)
        res = engine.run(bars)
        
        results[st_name] = {
            "total_trades": res.number_of_trades,
            "return_pct": res.total_return_pct,
            "win_rate": res.win_rate,
            "profit_factor": res.profit_factor,
            "market_bars": telemetry.stage_counts.get("MARKET_BARS", 0),
            "strategy_signals": telemetry.stage_counts.get("STRATEGY_SIGNALS", 0)
        }
        
    return results
