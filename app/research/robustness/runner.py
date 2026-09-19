import json
import logging
from typing import Dict, Any, List
from app.backtesting.models import CostConfig
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.research.dataset import generate_synthetic_data, generate_regime_dataset

from app.research.robustness.monte_carlo import run_monte_carlo_robustness
from app.research.robustness.stress_testing import run_cost_stress_test
from app.research.robustness.seed_testing import run_seed_robustness
from app.research.robustness.parameter_sensitivity import run_parameter_sensitivity
from app.research.robustness.walk_forward import run_walk_forward_robustness
from app.research.robustness.scorecard import evaluate_robustness

from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.adaptive import AdaptiveIntelligence
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.config import config
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

def create_engine_factory(use_adaptive: bool = True, breakout_period: int = 20) -> BacktestEngine:
    strategies = [
        TrendFollowingStrategy(), 
        BreakoutStrategy(lookback_period=breakout_period), 
        MeanReversionStrategy()
    ]
    adaptive = AdaptiveIntelligence() if use_adaptive else None
    ensemble = StrategyEnsemble(strategies, min_score=0.0, adaptive_intelligence=adaptive)
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
    intel_service = IntelligenceService(FixtureNewsProvider(), config)
    
    return BacktestEngine(
        ensemble=ensemble, 
        risk_engine=risk_engine,
            portfolio_config=__import__('app.risk.portfolio', fromlist=['PortfolioRiskConfig']).PortfolioRiskConfig(max_symbol_exposure_pct=1.0, max_strategy_exposure_pct=1.0, max_aggregate_stop_risk_pct=0.2),
        intelligence_service=intel_service,
        initial_capital=10000.0, 
        cost_config=CostConfig()
    )

def run_full_robustness_experiment(symbol: str = "SYNC_ROBUST") -> Dict[str, Any]:
    # 1. Base dataset
    bars = generate_synthetic_data([symbol], num_bars=2000, seed=42)[symbol]
    
    # Base Engine run
    telemetry.reset()
    telemetry.enabled = True
    engine = create_engine_factory()
    res = engine.run(bars)
    
    # A. Monte Carlo
    mc_res = run_monte_carlo_robustness(engine.closed_trades, 10000.0, simulations=500, seed=123)
    
    # B. Cost Stress Testing
    def cost_factory(cost_config: CostConfig):
        eng = create_engine_factory()
        eng.cost_config = cost_config
        return eng
    cost_res = run_cost_stress_test(bars, cost_factory)
    
    # C. Seed Robustness
    seed_res = run_seed_robustness(symbol, create_engine_factory, seeds=[101, 202, 303, 404, 505])
    
    # D. Parameter Sensitivity
    def param_factory(val: float):
        return create_engine_factory(breakout_period=int(val))
    param_res = run_parameter_sensitivity(bars, param_factory, "breakout_period", 20, [10, 20, 30, 40])
    
    # E. Walk Forward
    wf_res = run_walk_forward_robustness(bars, create_engine_factory)
    
    # F. Regime Robustness
    regime_results = {}
    for r_type in ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND", "HIGH_VOLATILITY", "LOW_VOLATILITY"]:
        r_bars = generate_regime_dataset(r_type, num_bars=500)
        r_eng = create_engine_factory()
        r_out = r_eng.run(r_bars)
        regime_results[r_type] = {
            "trades": r_out.number_of_trades,
            "return_pct": r_out.total_return_pct,
            "win_rate": r_out.win_rate
        }
        
    # G. Scorecard
    scorecard = evaluate_robustness("EXP-R-01", symbol, seed_res, cost_res, mc_res)
    
    return {
        "experiment_id": scorecard.experiment_id,
        "scorecard": scorecard.model_dump(),
        "monte_carlo": mc_res.model_dump(),
        "cost_stress": [c.model_dump() for c in cost_res],
        "seed_robustness": [s.model_dump() for s in seed_res],
        "parameter_sensitivity": [p.model_dump() for p in param_res],
        "walk_forward": [w.model_dump() for w in wf_res],
        "regimes": regime_results
    }
