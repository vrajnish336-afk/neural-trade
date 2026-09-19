import sys
import logging
from datetime import datetime, timezone, timedelta
import tempfile
import os

from app.data.csv_provider import CsvHistoricalDataProvider
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.breakout import BreakoutStrategy
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.mean_reversion import MeanReversionStrategy
from scripts.paper_simulation_runner import PaperSimulationRunner

from unittest.mock import Mock

def main():
    # Only show critical logs to keep output clean
    logging.basicConfig(level=logging.ERROR)
    
    # 1. Load data
    provider = CsvHistoricalDataProvider("data/sample")
    
    symbol = "synthetic_test_data"
    
    bars = provider.get_historical_bars(
        symbol=symbol,
        timeframe="1D",
        start_time=datetime(2000, 1, 1, tzinfo=timezone.utc),
        end_time=datetime(2030, 1, 1, tzinfo=timezone.utc)
    )
    
    if not bars:
        print("Error: No bars loaded. Check symbol or timeframe.")
        return
        
    # Bounded simulation
    bars = bars[:500]
    
    # 2. Temp DB
    import sqlite3
    from app.database.schema import SCHEMA_SQL
    
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    
    try:
        # 3. Build components
        repo = PaperRepository(db_path=path)
        repo.get_or_create_portfolio("default_paper", 10000.0)
        
        limits = PortfolioRiskLimits(initial_equity=10000.0)
        risk_engine = RiskEngine(limits, 0.02)
        
        from app.backtesting.models import ExecutionAssumptions
        broker = StreamingPaperBroker(repo, risk_engine, cost_config=ExecutionAssumptions.BASELINE)
        
        # Real Strategies
        ensemble = StrategyEnsemble([
            BreakoutStrategy(20, 20),
            TrendFollowingStrategy(10, 30),
            MeanReversionStrategy(20, 2.0)
        ])
        
        orchestrator = DecisionOrchestrator(
            ensemble=ensemble,
            risk_engine=risk_engine,
            intelligence_service=Mock(generate_intelligence=Mock(return_value=None)),
            forecasting_service=Mock(generate_forecast=Mock(return_value=None))
        )
        
        # 4. Run
        runner = PaperSimulationRunner(broker, orchestrator)
        runner.run(symbol, bars)
        
        # 5. Extract results
        closed = repo.get_closed_positions("default_paper", limit=10000)
        open_pos = broker.get_realtime_portfolio().open_positions
        snapshots = repo.get_equity_snapshots("default_paper")
        orders = repo.get_recent_orders("default_paper", limit=10000)
        
        portfolio = repo.get_or_create_portfolio("default_paper")
        final_equity = portfolio['current_equity']
        pnl = sum(r['realized_pnl'] for r in closed)
        comms = sum(r['commission'] for r in orders)
        slippage = sum(r['slippage'] for r in orders)
        
        print(f"DEBUG: Found {len(snapshots)} snapshots")
        if snapshots:
            print(f"DEBUG: Last snapshot: equity={snapshots[-1]['current_equity']} at {snapshots[-1]['timestamp']}")
            print(f"DEBUG: First snapshot: equity={snapshots[0]['current_equity']} at {snapshots[0]['timestamp']}")
            
        print("SIMULATION COMPLETED:")
        print(f"- Bars Processed: {len(bars)}")
        print(f"- Entries: {len(closed) + len(open_pos)}")
        print(f"- Exits: {len(closed)}")
        print(f"- Final Equity: {final_equity:.2f}")
        print(f"- Realized PnL: {pnl:.2f}")
        print(f"- Comm/Slippage: {comms:.2f} / {slippage:.2f}")
        
    except Exception as e:
        print(f"Error during simulation: {e}")
        
    finally:
        os.close(fd)
        os.remove(path)

if __name__ == "__main__":
    main()
