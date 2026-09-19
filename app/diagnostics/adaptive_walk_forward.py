import copy
from typing import Dict, Any, Callable, List
from app.core.models import MarketBar
from app.backtesting.models import CostConfig
from app.backtesting.engine import BacktestEngine
from app.diagnostics.telemetry import telemetry
from app.research.splits import split_research_windows
from app.strategies.adaptive import AdaptiveIntelligence
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.config import config

def create_engine(cost: CostConfig, use_adaptive: bool) -> BacktestEngine:
    strategies = [TrendFollowingStrategy(), BreakoutStrategy(), MeanReversionStrategy()]
    adaptive = AdaptiveIntelligence() if use_adaptive else None
    ensemble = StrategyEnsemble(strategies, min_score=0.0, adaptive_intelligence=adaptive)
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
    intel_service = IntelligenceService(FixtureNewsProvider(), config)
    
    return BacktestEngine(
        ensemble=ensemble, 
        risk_engine=risk_engine,
        intelligence_service=intel_service,
        initial_capital=10000.0, 
        cost_config=cost
    )

def run_adaptive_calibration_experiment(bars: List[MarketBar], cost: CostConfig) -> Dict[str, Dict[str, Any]]:
    # Simple full chronological run for comparison
    results = {}
    
    # A. Static Baseline
    telemetry.reset()
    telemetry.enabled = True
    baseline_engine = create_engine(cost, use_adaptive=False)
    res_base = baseline_engine.run(bars)
    
    results["BASELINE"] = {
        "trades": res_base.number_of_trades,
        "return_pct": res_base.total_return_pct,
        "win_rate": res_base.win_rate,
        "profit_factor": res_base.profit_factor
    }
    
    # B. Adaptive Ensemble (Online Learning)
    telemetry.reset()
    telemetry.enabled = True
    adaptive_engine = create_engine(cost, use_adaptive=True)
    res_adapt = adaptive_engine.run(bars)
    
    # Calculate churn (how many times preferred strategy switched)
    switches = 0
    prev_regime_pref = {}
    for dec in telemetry.adaptive_decisions:
        r = dec["regime"]
        w = dec["weights"]
        if w:
            pref = max(w.items(), key=lambda x: x[1])[0]
            if r in prev_regime_pref and prev_regime_pref[r] != pref:
                switches += 1
            prev_regime_pref[r] = pref
            
    # Count confidences
    low_conf = sum(1 for d in telemetry.adaptive_decisions if d["confidence"] == "LOW_CONFIDENCE")
    high_conf = sum(1 for d in telemetry.adaptive_decisions if d["confidence"] == "HIGH_CONFIDENCE")
    insufficient = sum(1 for d in telemetry.adaptive_decisions if d["confidence"] == "INSUFFICIENT_EVIDENCE")
    
    results["ADAPTIVE"] = {
        "trades": res_adapt.number_of_trades,
        "return_pct": res_adapt.total_return_pct,
        "win_rate": res_adapt.win_rate,
        "profit_factor": res_adapt.profit_factor,
        "strategy_switches": switches,
        "decisions_low_conf": low_conf,
        "decisions_high_conf": high_conf,
        "decisions_insufficient": insufficient
    }
    
    return results

