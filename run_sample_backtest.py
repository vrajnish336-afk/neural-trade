import logging
from datetime import datetime, timezone
from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider
from app.strategies.breakout import BreakoutStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.database.schema import init_db
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.analytics.engine import generate_analytics_report
from app.database.repositories import BacktestRepository, AnalyticsRepository
from reports.generate_report import generate_markdown_report

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def run():
    print("==============================================")
    print(" AI TRADING BOT - PHASE 6 SAMPLE BACKTEST")
    print("==============================================")
    
    # 0. Initialize DB
    init_db()
    
    # 1. Load Data
    provider = CsvHistoricalDataProvider(data_dir="data/sample")
    bars = provider.get_historical_bars(
        symbol="synthetic_test_data",
        timeframe="1D",
        start_time=datetime(2023, 1, 1, tzinfo=timezone.utc)
    )
    
    if not bars:
        print("No historical data found. Please ensure data/sample/synthetic_test_data_1D.csv exists.")
        return
        
    print(f"Loaded {len(bars)} synthetic market bars.")
    
    # 2. Setup strategy & ensemble
    strategy = BreakoutStrategy(lookback_period=10, volume_period=10)
    ensemble = StrategyEnsemble([strategy], min_score=0.0) # Bypass regime veto for basic test
    
    # 3. Setup risk engine
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05) # 5% risk per trade
    
    # 4. Setup Market Intelligence
    news_provider = FixtureNewsProvider() # Empty mock
    intelligence_service = IntelligenceService(news_provider=news_provider, config=config)
    
    # 5. Setup backtest engine with realistic costs
    cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.001) # 0.1% each
    engine = BacktestEngine(
        ensemble=ensemble, 
        risk_engine=risk_engine,
        intelligence_service=intelligence_service,
        initial_capital=10000.0, 
        cost_config=cost_config
    )
    
    # 6. Run
    result = engine.run(bars)
    
    # 7. Persist Backtest
    repo = BacktestRepository()
    run_id = repo.save(result)
    
    # 8. Run Analytics & Persist
    print("\nRunning Advanced Analytics...")
    analytics_report = generate_analytics_report(run_id, result)
    analytics_repo = AnalyticsRepository()
    analytics_repo.save_report(analytics_report)
    
    # 9. Export Markdown Report
    report_path = generate_markdown_report(analytics_report)
    
    print("\n--- BACKTEST RESULTS ---")
    print(f"Run ID:          {run_id}")
    print(f"Initial Capital: ${result.initial_capital:,.2f}")
    print(f"Final Equity:    ${result.final_equity:,.2f}")
    print(f"Total Return:    {result.total_return_pct:.2f}%")
    print(f"Max Drawdown:    {result.max_drawdown_pct:.2f}%")
    print(f"Total Trades:    {result.number_of_trades}")
    print(f"Win Rate:        {result.win_rate:.2f}%")
    print(f"Profit Factor:   {result.profit_factor:.2f}")
    
    print(f"\nPhase 6 Analytics Report generated at: {report_path}")

if __name__ == "__main__":
    run()
