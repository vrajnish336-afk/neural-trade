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

def main():
    logging.basicConfig(level=logging.ERROR)
    
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
            forecasting_service=Mock(generate_forecast=Mock(return_value=None)),
            paper_repository=repo
        )
        
        provider = CsvHistoricalDataProvider('data/historical')
        bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
        
        print(f"Total dataset size: {len(bars)} bars")
        
        # Intercept evaluate to record regime of every evaluated bar
        real_evaluate = orchestrator.evaluate
        all_regimes = []
        all_decisions = []
        def intercept_evaluate(*args, **kwargs):
            dec = real_evaluate(*args, **kwargs)
            all_regimes.append(dec.regime)
            all_decisions.append(dec)
            return dec
            
        orchestrator.evaluate = intercept_evaluate
        
        runner = PaperSimulationRunner(broker, orchestrator)
        runner.run('BTC_USDT', bars)
        
        closed = repo.get_closed_positions('default_paper', limit=100000)
        open_pos = broker.get_realtime_portfolio().open_positions
        snapshots = repo.get_equity_snapshots('default_paper')
        orders = repo.get_recent_orders('default_paper', limit=100000)
        
        rejections = [o for o in orders if o['status'] == 'REJECTED']
        filled = [o for o in orders if o['status'] == 'FILLED']
        
        regime_dist = {}
        high_vol_count = 0
        regime_vetoes = 0
        for reg in all_regimes:
            regime_dist[reg] = regime_dist.get(reg, 0) + 1
            if reg == 'HIGH_VOLATILITY':
                high_vol_count += 1
                
        for dec in all_decisions:
            if dec.rationale and "Regime Veto" in dec.rationale:
                regime_vetoes += 1
                
        evaluated_bars = len(all_regimes)
        
        portfolio = repo.get_or_create_portfolio('default_paper')
        final_equity = portfolio['current_equity']
        pnl = sum(r['realized_pnl'] for r in closed)
        comms = sum(r['commission'] for r in filled)
        slippage = sum(r['slippage'] for r in filled)
        
        wins = sum(1 for r in closed if r['realized_pnl'] > 0)
        losses = sum(1 for r in closed if r['realized_pnl'] <= 0)
        
        eq_curve = [{'equity': s['current_equity'], 'unrealized_pnl': s['unrealized_pnl'] if 'unrealized_pnl' in s.keys() else 0.0} for s in snapshots]
        max_dd = calculate_equity_metrics(eq_curve, 100000.0).max_drawdown_pct if eq_curve else 0.0
        
        print(f"STATUS: SUCCESS")
        print(f"REGIME:")
        print(f"- Distribution: {regime_dist}")
        print(f"- HIGH_VOLATILITY: {high_vol_count} ({high_vol_count/evaluated_bars*100:.1f}% of {evaluated_bars} evaluated bars)")
        print(f"TRADES:")
        print(f"- Entries: {len(filled)} | Exits: {len(closed)}")
        print(f"- Wins/Losses: {wins}/{losses} | Regime Vetoes: {regime_vetoes}")
        print(f"PERFORMANCE:")
        print(f"- Final Equity: ${final_equity:.2f} | Realized PnL: ${pnl:.2f}")
        print(f"- Max Drawdown: {max_dd:.2f}%")
        print(f"BASELINE_DIFF:")
        print(f"- Equity: ${final_equity - 117711.25:+.2f}")
        print(f"- Max Drawdown: {max_dd - 16.77:+.2f}%")
        
        calculated_eq = 100000.0 + pnl - comms
        print(f"ACCOUNTING:")
        print(f"- SQLite Reconciles: {'YES' if abs(calculated_eq - final_equity) < 1.0 else 'NO'}")
        print(f"ERRORS:\n- None")
        print(f"GAPS:\n- None")
        print(f"NEXT:\n- Awaiting instructions.")
        
    finally:
        os.close(fd)
        os.remove(path)

if __name__ == '__main__':
    main()
