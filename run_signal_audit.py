import logging
import json
from app.database.schema import init_db
from app.backtesting.engine import BacktestEngine
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.config import config
from app.backtesting.models import CostConfig
from app.research.dataset import generate_synthetic_data
from app.diagnostics.telemetry import telemetry
from app.diagnostics.ablation import run_filter_ablation, run_strategy_ablation

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")

# For intelligence filtering ablation, we can use a mock/modified IntelligenceService 
# or simply toggle its usage in the engine factory.
class DummyIntelligenceService:
    def __init__(self, news, anomaly, fakeout):
        self.news = news
        self.anomaly = anomaly
        self.fakeout = fakeout
        self.real_service = IntelligenceService(FixtureNewsProvider(), config)
        
    def generate_intelligence(self, symbol, timestamp, bars, signal):
        intel = self.real_service.generate_intelligence(symbol, timestamp, bars, signal)
        if not self.news:
            from app.core.models import SentimentResult
            intel.sentiment = SentimentResult(
                label="NEUTRAL", 
                score=0.5, 
                confidence=1.0, 
                source_count=0, 
                timestamp=timestamp, 
                raw_news=[]
            )
        if not self.anomaly:
            intel.anomaly_status = []
        if not self.fakeout:
            intel.fakeout_risk = "NORMAL"
        return intel

def filter_ablation_factory(cost_config: CostConfig, use_news: bool, use_anomaly: bool, use_fakeout: bool) -> BacktestEngine:
    strategies = [TrendFollowingStrategy(), BreakoutStrategy(), MeanReversionStrategy()]
    ensemble = StrategyEnsemble(strategies, min_score=0.0)
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
    
    intel_service = DummyIntelligenceService(use_news, use_anomaly, use_fakeout)
    
    return BacktestEngine(
        ensemble=ensemble, 
        risk_engine=risk_engine,
        intelligence_service=intel_service,
        initial_capital=10000.0, 
        cost_config=cost_config
    )

def strategy_ablation_factory(st_name: str) -> BacktestEngine:
    if st_name == "TrendFollowing":
        strategies = [TrendFollowingStrategy()]
    elif st_name == "Breakout":
        strategies = [BreakoutStrategy()]
    elif st_name == "MeanReversion":
        strategies = [MeanReversionStrategy()]
    else:
        strategies = [TrendFollowingStrategy(), BreakoutStrategy(), MeanReversionStrategy()]
        
    ensemble = StrategyEnsemble(strategies, min_score=0.0)
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
    intel_service = IntelligenceService(FixtureNewsProvider(), config)
    
    return BacktestEngine(
        ensemble=ensemble, 
        risk_engine=risk_engine,
        intelligence_service=intel_service,
        initial_capital=10000.0, 
        cost_config=CostConfig()
    )

if __name__ == "__main__":
    init_db()
    print("==============================================")
    print(" SIGNAL PIPELINE AUDIT & DIAGNOSTICS (PHASE 8)")
    print("==============================================")
    
    config.DIAGNOSTIC_MODE = True
    telemetry.enabled = True
    telemetry.reset()
    
    bars = generate_synthetic_data(["SYNC_BTC"], num_bars=2000, seed=101)["SYNC_BTC"]
    
    print("\n1. FULL DIAGNOSTIC RUN (Ensemble + All Filters)")
    engine = filter_ablation_factory(CostConfig(), True, True, True)
    res = engine.run(bars)
    
    print("\n--- SIGNAL FUNNEL ---")
    print(f"MARKET_BARS Evaluated:  {telemetry.stage_counts.get('MARKET_BARS', 0)}")
    print(f"STRATEGY_SIGNALS Generated: {telemetry.stage_counts.get('STRATEGY_SIGNALS', 0)}")
    print(f"ENSEMBLE_SIGNALS Approved:  {telemetry.stage_counts.get('ENSEMBLE_SIGNALS', 0)}")
    print(f"RISK_APPROVED:          {telemetry.stage_counts.get('RISK_APPROVED', 0)}")
    print(f"FINAL PAPER TRADES:     {telemetry.stage_counts.get('PAPER_TRADES', 0)}")
    
    print("\n--- REJECTION BREAKDOWN ---")
    for reason, count in telemetry.rejection_counts.items():
        if count > 0:
            print(f"{reason.value:25s} : {count}")
            
    print("\n--- REGIME DIAGNOSTICS ---")
    for regime, count in telemetry.regime_counts.items():
        print(f"{regime:20s} : {count}")
        
    print("\n--- STRATEGY DIAGNOSTICS ---")
    for s_name in telemetry.strategy_evaluations:
        evals = telemetry.strategy_evaluations[s_name]
        l_sigs = telemetry.strategy_signals_long.get(s_name, 0)
        s_sigs = telemetry.strategy_signals_short.get(s_name, 0)
        print(f"{s_name:20s} Evaluated: {evals} | Long: {l_sigs} | Short: {s_sigs}")
    
    print("\n2. FILTER ABLATION RESEARCH")
    filter_res = run_filter_ablation(bars, filter_ablation_factory, CostConfig())
    for name, r in filter_res.items():
        print(f"{name:25s} -> Trades: {r['total_trades']}, Return: {r['return_pct']:.2f}% | Risk_Approved: {r['risk_approved']}")
        
    print("\n3. STRATEGY ABLATION RESEARCH")
    strat_res = run_strategy_ablation(bars, strategy_ablation_factory)
    for name, r in strat_res.items():
        print(f"{name:20s} -> Trades: {r['total_trades']}, Return: {r['return_pct']:.2f}% | Strat Signals: {r['strategy_signals']}")
        
    # Write report
    with open("reports/phase8_signal_audit.json", "w") as f:
        json.dump({
            "funnel": telemetry.stage_counts,
            "rejections": {k.value: v for k, v in telemetry.rejection_counts.items()},
            "regimes": telemetry.regime_counts,
            "filter_ablation": filter_res,
            "strategy_ablation": strat_res
        }, f, indent=4)
        
    print("\nDetailed diagnostics persisted to reports/phase8_signal_audit.json")
