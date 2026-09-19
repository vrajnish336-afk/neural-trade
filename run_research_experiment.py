import logging
from app.database.schema import init_db
from app.database.repositories import ResearchRepository
from app.backtesting.engine import BacktestEngine
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.config import config
from app.backtesting.models import CostConfig
from app.research.experiments import run_governed_experiment
from app.research.registry import run_reproducibility_check
from reports.generate_report import generate_research_markdown_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")

    print(" AI TRADING BOT - PHASE 7 RESEARCH RUN")
    print("==============================================")
    
    init_db()
    
    base_cost = CostConfig(commission_rate=0.001, slippage_rate=0.001)
    
    print("Starting Research Experiment (Multi-Symbol, Out-Of-Sample, Stress Tested)...")
    experiment = run_experiment(
        symbols=["SYNC_BTC", "SYNC_ETH"],
        seed=101,
        engine_factory=engine_factory,
        base_cost=base_cost,
        strategy_name="MeanReversion"
    )
    
    print(f"Experiment Status: {experiment.status}")
    
    if experiment.status == "COMPLETED":
        repo = ResearchRepository()
        repo.save_experiment(experiment)
        
        report_path = generate_research_markdown_report(experiment)
        print(f"\nResearch Report generated at: {report_path}")
        
        oos = experiment.out_of_sample_report
        print("\n--- OUT-OF-SAMPLE RESULTS (Test Split) ---")
        print(f"Total Trades: {oos.trade_metrics.total_trades}")
        print(f"Win Rate:     {oos.trade_metrics.win_rate:.2f}%")
        print(f"Total Return: {oos.equity_metrics.total_return_pct:.2f}%")
        print(f"Max Drawdown: {oos.equity_metrics.max_drawdown_pct:.2f}%")
        
        for st in experiment.stress_test_results:
            print(f"\n--- STRESS TEST: {st.condition_name} ---")
            print(f"Baseline Return: {st.baseline_return:.2f}%")
            print(f"Stress Return:   {st.stress_return:.2f}%")
            print(f"Degradation:     {st.degradation_pct:.2f}%")
