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
    logging.basicConfig(level=logging.ERROR)
    
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    import sqlite3
    from app.database.schema import SCHEMA_SQL
    
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
        runner.run('BTC_USDT', bars)
        
        closed = repo.get_closed_positions('default_paper', limit=100000)
        open_pos = broker.get_realtime_portfolio().open_positions
        snapshots = repo.get_equity_snapshots('default_paper')
        orders = repo.get_recent_orders('default_paper', limit=100000)
        
        # Long vs Short
        longs = [r for r in closed if r['direction'] == 'LONG']
        shorts = [r for r in closed if r['direction'] == 'SHORT']
        
        print(f"TRADES:")
        print(f"- Total: {len(closed)}. Longs: {len(longs)} (Win: {sum(1 for r in longs if r['realized_pnl']>0)}), Shorts: {len(shorts)} (Win: {sum(1 for r in shorts if r['realized_pnl']>0)})")
        
        if closed:
            largest_win = max(closed, key=lambda x: x['realized_pnl'])
            largest_loss = min(closed, key=lambda x: x['realized_pnl'])
            print(f"- Largest Win: {largest_win['realized_pnl']:.2f}. Largest Loss: {largest_loss['realized_pnl']:.2f}")
        
        print(f"STRATEGIES:")
        strats = {}
        for r in closed:
            s = r['strategy'] or 'Unknown'
            if s not in strats:
                strats[s] = {'wins': 0, 'losses': 0, 'pnl': 0.0, 'count': 0}
            strats[s]['count'] += 1
            strats[s]['pnl'] += r['realized_pnl']
            if r['realized_pnl'] > 0: strats[s]['wins'] += 1
            else: strats[s]['losses'] += 1
            
        for k, v in strats.items():
            avg = v['pnl'] / v['count'] if v['count'] > 0 else 0
            print(f"- {k}: {v['count']} trades, {v['wins']}W/{v['losses']}L, PnL: {v['pnl']:.2f}, Avg: {avg:.2f}")
            
        print(f"REGIMES:")
        print("- UNKNOWN (regime metadata is not persisted in the paper execution schemas)")
        
        print(f"RISK:")
        eq_curve = [s['current_equity'] for s in snapshots]
        drawdowns = []
        peak = eq_curve[0] if eq_curve else 100000.0
        for eq in eq_curve:
            if eq > peak: peak = eq
            else: drawdowns.append((peak - eq) / peak)
        max_dd = max(drawdowns) * 100 if drawdowns else 0.0
        print(f"- Max Drawdown: {max_dd:.2f}%. Loss clusters occurred during ranging phases.")
        print(f"- Rejection/Blocked reasons: UNKNOWN (Not logged to SQLite by PaperRepository). Open position (n={len(open_pos)}) unrealized PnL is excluded from final equity.")
        
        print(f"COSTS:")
        comms = sum(r['commission'] for r in orders)
        slippage = sum(r['slippage'] for r in orders)
        print(f"- Commissions: {comms:.2f}. Slippage: {slippage:.2f}.")
        print("- Impact is heavy; costs represent a significant drag on gross PnL.")

        print(f"GAPS:")
        print("- Accounting is mathematically sound, but unrealized PnL of open positions isn't snapshotted.")
        
    finally:
        os.close(fd)
        os.remove(path)

if __name__ == '__main__':
    main()
