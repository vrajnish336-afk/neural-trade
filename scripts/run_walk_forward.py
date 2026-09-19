import logging
from datetime import datetime, timezone
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
from app.analytics.performance import calculate_equity_metrics

from unittest.mock import Mock
import sqlite3
from app.database.schema import SCHEMA_SQL

def run_window(name: str, bars_slice: list):
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    
    try:
        repo = PaperRepository(db_path=path)
        repo.get_or_create_portfolio('default_paper', 100000.0)
        
        limits = PortfolioRiskLimits(initial_equity=100000.0)
        risk_engine = RiskEngine(limits, 0.02)
        
        from app.backtesting.models import ExecutionAssumptions
        broker = StreamingPaperBroker(repo, risk_engine, cost_config=ExecutionAssumptions.BASELINE)
        
        ensemble = StrategyEnsemble([BreakoutStrategy(20, 20), TrendFollowingStrategy(10, 30), MeanReversionStrategy(20, 2.0)])
        orchestrator = DecisionOrchestrator(
            ensemble=ensemble, risk_engine=risk_engine,
            intelligence_service=Mock(generate_intelligence=Mock(return_value=None)),
            forecasting_service=Mock(generate_forecast=Mock(return_value=None))
        )
        
        runner = PaperSimulationRunner(broker, orchestrator)
        runner.run('BTC_USDT', bars_slice)
        
        closed = repo.get_closed_positions('default_paper', limit=100000)
        open_pos = broker.get_realtime_portfolio().open_positions
        snapshots = repo.get_equity_snapshots('default_paper')
        orders = repo.get_recent_orders('default_paper', limit=100000)
        
        rejections = [o for o in orders if o['status'] == 'REJECTED']
        filled = [o for o in orders if o['status'] == 'FILLED']
        
        portfolio = repo.get_or_create_portfolio('default_paper')
        final_equity = portfolio['current_equity']
        pnl = sum(r['realized_pnl'] for r in closed)
        comms = sum(r['commission'] for r in filled)
        slippage = sum(r['slippage'] for r in filled)
        
        wins = sum(1 for r in closed if r['realized_pnl'] > 0)
        losses = sum(1 for r in closed if r['realized_pnl'] <= 0)
        
        eq_curve = [{'equity': s['current_equity'], 'unrealized_pnl': s['unrealized_pnl']} for s in snapshots]
        max_dd = calculate_equity_metrics(eq_curve, 100000.0).max_drawdown_pct if eq_curve else 0.0
        
        print(f"WINDOW: {name}")
        print(f"- Bars: {len(bars_slice)}")
        print(f"- Final Equity: {final_equity:.2f} | PnL: {pnl:.2f} | Comm: {comms:.2f} | Slip: {slippage:.2f}")
        print(f"- Trades: Entries={len(closed)+len(open_pos)}, Exits={len(closed)}, Win/Loss={wins}/{losses}, Open={len(open_pos)}")
        print(f"- Rejections: {len(rejections)}")
        print(f"- Max Drawdown: {max_dd:.2f}%")
        
        # Verify accounting consistency
        calculated_eq = 100000.0 + pnl - comms
        if abs(calculated_eq - final_equity) > 0.1:
            print(f"- CONSISTENCY ERROR: Calculated {calculated_eq} != DB Equity {final_equity}")
        
    finally:
        os.close(fd)
        os.remove(path)

def main():
    logging.basicConfig(level=logging.ERROR)
    
    from app.data.csv_provider import CsvHistoricalDataProvider
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    chunk_size = len(bars) // 5
    w1 = bars[0:chunk_size]
    w2 = bars[chunk_size:2*chunk_size]
    w3 = bars[2*chunk_size:3*chunk_size]
    w4 = bars[3*chunk_size:4*chunk_size]
    w5 = bars[4*chunk_size:]
    
    run_window("WINDOW 1", w1)
    run_window("WINDOW 2", w2)
    run_window("WINDOW 3", w3)
    run_window("WINDOW 4", w4)
    run_window("WINDOW 5", w5)

if __name__ == '__main__':
    main()
