import logging
import sqlite3
import os
import tempfile
from datetime import datetime, timezone
from collections import defaultdict

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
from app.database.schema import SCHEMA_SQL
import app.analysis.regime

def run_and_analyze():
    logging.basicConfig(level=logging.ERROR)
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    chunk_size = len(bars) // 5
    
    all_trades = []
    all_vetoes = []
    
    from app.diagnostics.telemetry import telemetry
    recent_signals = []
    real_record_strategy_eval = telemetry.record_strategy_eval
    def mock_record_strategy_eval(strategy_name, direction, *args, **kwargs):
        if direction in ("LONG", "SHORT"):
            recent_signals.append((strategy_name, direction))
        return real_record_strategy_eval(strategy_name, direction, *args, **kwargs)
    telemetry.record_strategy_eval = mock_record_strategy_eval
    
    real_record_rejection = telemetry.record_rejection
    def mock_record_rejection(reason, regime, *args, **kwargs):
        from app.diagnostics.models import RejectionReason
        if reason == RejectionReason.REGIME_VETO:
            for strat, d in recent_signals:
                all_vetoes.append({'regime': regime, 'strategy': strat})
        return real_record_rejection(reason, regime, *args, **kwargs)
    telemetry.record_rejection = mock_record_rejection
    
    for i in range(5):
        fd, path = tempfile.mkstemp(suffix='.sqlite')
        conn = sqlite3.connect(path)
        conn.executescript(SCHEMA_SQL)
        conn.commit()
        conn.close()
        
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
        
        real_orch_eval = orchestrator.evaluate
        def intercepted_orch_eval(*args, **kwargs):
            recent_signals.clear()  # Clear signals before evaluating the bar
            return real_orch_eval(*args, **kwargs)
        orchestrator.evaluate = intercepted_orch_eval
        
        start_idx = i * chunk_size
        end_idx = (i + 1) * chunk_size
        w_bars = bars[start_idx:end_idx]
        ctx_start = max(0, start_idx - 110)
        context_bars = bars[ctx_start:start_idx] if start_idx > 0 else []
        
        runner = PaperSimulationRunner(broker, orchestrator)
        runner.run('BTC_USDT', w_bars, context_bars=context_bars)
        
        # Analyze SQLite
        conn = sqlite3.connect(path)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        c.execute("SELECT * FROM paper_closed_positions")
        closed = c.fetchall()
        
        c.execute("SELECT timestamp, regime FROM paper_orders WHERE status='FILLED' AND direction IN ('LONG', 'SHORT')")
        orders = c.fetchall()
        order_regimes = {o['timestamp']: o['regime'] for o in orders}
        
        for pos in closed:
            reg = order_regimes.get(pos['entry_time'], 'UNKNOWN')
            all_trades.append({
                'window': i + 1,
                'strategy': pos['strategy'] if 'strategy' in pos.keys() else 'UNKNOWN',
                'regime': reg,
                'pnl': pos['realized_pnl']
            })
            
        conn.close()
        os.close(fd)
        os.remove(path)
        
    return all_trades, all_vetoes

def main():
    trades, vetoes = run_and_analyze()
    
    regime_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0})
    strat_regime = defaultdict(lambda: {'count': 0, 'wins': 0, 'losses': 0, 'pnl': 0.0})
    
    w4_pnl = 0.0
    w4_strats = defaultdict(float)
    
    for t in trades:
        reg = t['regime']
        strat = t['strategy']
        pnl = t['pnl']
        win = 1 if pnl > 0 else 0
        loss = 1 if pnl <= 0 else 0
        
        regime_stats[reg]['count'] += 1
        regime_stats[reg]['wins'] += win
        regime_stats[reg]['losses'] += loss
        regime_stats[reg]['pnl'] += pnl
        
        key = f"{strat} in {reg}"
        strat_regime[key]['count'] += 1
        strat_regime[key]['wins'] += win
        strat_regime[key]['losses'] += loss
        strat_regime[key]['pnl'] += pnl
        
        if t['window'] == 4:
            w4_pnl += pnl
            w4_strats[key] += pnl
            
    print("--- REGIME STATS ---")
    for r, s in regime_stats.items():
        print(f"{r}: {s['count']} trades, W/L={s['wins']}/{s['losses']}, PnL={s['pnl']:.2f}")
        
    print("\n--- WORST STRATEGY/REGIME ---")
    worst = sorted(strat_regime.items(), key=lambda x: x[1]['pnl'])[:3]
    for k, v in worst:
        print(f"{k}: {v['count']} trades, W/L={v['wins']}/{v['losses']}, PnL={v['pnl']:.2f}")
        
    print("\n--- W4 LOSSES ---")
    print(f"Total W4 PnL: {w4_pnl:.2f}")
    for k, pnl in sorted(w4_strats.items(), key=lambda x: x[1]):
        print(f"{k}: {pnl:.2f}")
        
    print(f"\n--- VETOES ---")
    print(f"Total signals suppressed by Regime Veto: {len(vetoes)}")
    if vetoes:
        veto_strat = defaultdict(int)
        for v in vetoes:
            veto_strat[v['strategy']] += 1
        for k, v in veto_strat.items():
            print(f"- {k}: {v}")

if __name__ == '__main__':
    main()
