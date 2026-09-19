import sys
import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider
from app.research.dataset import generate_synthetic_data
from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.news.provider import FixtureNewsProvider
from app.services.intelligence import IntelligenceService
from app.database.schema import init_db
from app.database.repositories import BacktestRepository, AnalyticsRepository
from app.analytics.engine import generate_analytics_report
from app.cli.commands.helpers import get_strategy_class, setup_cli_logging

logger = logging.getLogger(__name__)

def setup_backtest_parser(subparsers):
    parser = subparsers.add_parser("backtest", help="Run a historical backtest")
    parser.add_argument("--strategy", required=True, choices=["breakout", "trend_following", "mean_reversion"], help="Strategy to run")
    parser.add_argument("--dataset", default="synthetic", help="Path to CSV dataset directory, or 'synthetic'")
    parser.add_argument("--symbol", default="synthetic_test_data", help="Symbol to trade")
    parser.add_argument("--timeframe", default="1D", help="Timeframe (e.g. 1D, 1h)")
    parser.add_argument("--capital", type=float, default=10000.0, help="Initial capital")
    parser.add_argument("--risk-pct", type=float, default=0.05, help="Risk per trade percentage")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for synthetic data")
    parser.add_argument("--output-json", help="Path to save output JSON")
    parser.add_argument("--quiet", action="store_true", help="Suppress logging")
    parser.set_defaults(func=run_backtest)

def run_backtest(args: argparse.Namespace) -> int:
    setup_cli_logging(args.quiet)
    init_db()

    try:
        # 1. Load Data
        if args.dataset.lower() == "synthetic":
            datasets = generate_synthetic_data(symbols=[args.symbol], num_bars=2000, seed=args.seed)
            bars = datasets.get(args.symbol, [])
        else:
            provider = CsvHistoricalDataProvider(data_dir=args.dataset)
            bars = provider.get_historical_bars(
                symbol=args.symbol,
                timeframe=args.timeframe,
                start_time=datetime(2000, 1, 1, tzinfo=timezone.utc)
            )
            
        if not bars:
            print(f"Error: No data found for symbol '{args.symbol}' in dataset '{args.dataset}'.")
            return 1
            
        # 2. Setup Strategy
        strat_cls = get_strategy_class(args.strategy)
        strategy = strat_cls()
        ensemble = StrategyEnsemble([strategy], min_score=0.0)
        
        # 3. Setup Risk
        limits = PortfolioRiskLimits(initial_equity=args.capital)
        risk_engine = RiskEngine(limits, risk_per_trade_pct=args.risk_pct)
        
        # 4. Intelligence
        news_provider = FixtureNewsProvider()
        intelligence_service = IntelligenceService(news_provider=news_provider, config=config)
        
        # 5. Engine
        cost_config = CostConfig(
            commission_rate=config.COMMISSION_RATE, 
            slippage_rate=config.SLIPPAGE_RATE
        )
        engine = BacktestEngine(
            ensemble=ensemble, 
            risk_engine=risk_engine,
            intelligence_service=intelligence_service,
            initial_capital=args.capital, 
            cost_config=cost_config
        )
        
        # 6. Run
        result = engine.run(bars)
        
        # 7. Persist
        repo = BacktestRepository()
        run_id = repo.save(result)
        analytics_report = generate_analytics_report(run_id, result)
        analytics_repo = AnalyticsRepository()
        analytics_repo.save_report(analytics_report)
        
        # Output printing
        print("================================================")
        print("NEURAL TRADE — RESEARCH BACKTEST")
        print("================================================")
        print("\nMODE: PAPER / RESEARCH ONLY")
        print("LIVE TRADING: DISABLED\n")
        print(f"Strategy: {args.strategy}")
        print(f"Dataset: {args.dataset}")
        print(f"Symbol: {args.symbol}")
        print(f"Timeframe: {args.timeframe}")
        print(f"Initial Capital: {args.capital:.2f}\n")
        print("---------------- RESULTS ----------------\n")
        print(f"Total Return: {result.total_return_pct:.2f}%")
        print(f"Net PnL: {result.net_profit:.2f}")
        print(f"Win Rate: {result.win_rate:.2f}%")
        print(f"Profit Factor: {result.profit_factor:.2f}")
        print(f"Max Drawdown: {result.max_drawdown_pct:.2f}%")
        print(f"Total Trades: {result.number_of_trades}\n")
        print("Status: COMPLETED")
        print("================================================")
        
        if args.output_json:
            out_data = {
                "run_id": run_id,
                "strategy": args.strategy,
                "symbol": args.symbol,
                "dataset": args.dataset,
                "total_return_pct": result.total_return_pct,
                "net_profit": result.net_profit,
                "win_rate": result.win_rate,
                "profit_factor": result.profit_factor,
                "max_drawdown_pct": result.max_drawdown_pct,
                "number_of_trades": result.number_of_trades
            }
            out_path = Path(args.output_json)
            out_path.parent.mkdir(parents=True, exist_ok=True)
            with open(out_path, "w") as f:
                json.dump(out_data, f, indent=2)
            print(f"Result JSON saved to {out_path.resolve()}")
            
        return 0

    except Exception as e:
        logger.exception("Backtest failed due to an internal error.")
        print(f"Error: {e}")
        return 1
