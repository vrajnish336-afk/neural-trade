import logging
import sqlite3
import os
import tempfile
from datetime import datetime, timezone

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
from app.database.schema import SCHEMA_SQL

def run_simulation(bars, enable_dynamic=True, context_bars=None):
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
    
    import importlib
    import app.analysis.regime
    
    if not enable_dynamic:
        def mock_detect(bars, *args, **kwargs):
            from app.core.models import MarketRegimeResult
            # Simulating the old hardcoded 10-bar delta used in orchestration
            if len(bars) < 10:
                return MarketRegimeResult(regime="INSUFFICIENT_DATA", confidence=0.0)
            p_first = bars[-10].close
            p_last = bars[-1].close
            pct_change = (p_last - p_first) / p_first if p_first else 0.0
            if pct_change > 0.05:
                reg = "TRENDING_UP"
            elif pct_change < -0.05:
                reg = "TRENDING_DOWN"
            else:
                reg = "RANGE_BOUND"
            return MarketRegimeResult(regime=reg, confidence=0.7)
            
        app.analysis.regime.detect_market_regime = mock_detect
    else:
        # reload original module
        importlib.reload(app.analysis.regime)
        
    real_eval = orchestrator.evaluate
    veto_count = {"vetoes": 0, "high_vol": 0}
    def intercepted_eval(*args, **kwargs):
        dec = real_eval(*args, **kwargs)
        if dec.rationale and "Regime Veto" in dec.rationale:
            veto_count["vetoes"] += 1
        if dec.regime == "HIGH_VOLATILITY":
            veto_count["high_vol"] += 1
        return dec
    orchestrator.evaluate = intercepted_eval
    
    runner = PaperSimulationRunner(broker, orchestrator)
    runner.run('BTC_USDT', bars, context_bars=context_bars)
    
    # Audit DB
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM paper_orders WHERE status='FILLED'")
    filled_orders = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM paper_closed_positions")
    exits = c.fetchone()[0]
    entries = filled_orders - exits
    
    c.execute("SELECT COUNT(*) FROM paper_positions")
    open_pos = c.fetchone()[0]
    
    c.execute("SELECT SUM(realized_pnl) FROM paper_closed_positions")
    pnl_row = c.fetchone()[0]
    realized_pnl = pnl_row if pnl_row else 0.0
    
    c.execute("SELECT COUNT(*) FROM paper_closed_positions WHERE realized_pnl > 0")
    wins = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM paper_closed_positions WHERE realized_pnl <= 0")
    losses = c.fetchone()[0]
    
    c.execute("SELECT * FROM paper_equity_snapshots ORDER BY timestamp ASC")
    snaps = c.fetchall()
    eq_curve = [{'equity': s['current_equity'], 'unrealized_pnl': s['unrealized_pnl'] if 'unrealized_pnl' in s.keys() else 0.0} for s in snaps]
    max_dd = calculate_equity_metrics(eq_curve, 100000.0).max_drawdown_pct if eq_curve else 0.0
    
    c.execute("SELECT current_equity FROM paper_portfolios LIMIT 1")
    final_eq = c.fetchone()[0]
    
    c.execute("SELECT SUM(commission) FROM paper_orders WHERE status='FILLED'")
    comms = c.fetchone()[0] or 0.0
    c.execute("SELECT SUM(slippage) FROM paper_orders WHERE status='FILLED'")
    slip = c.fetchone()[0] or 0.0
    
    conn.close()
    
    os.close(fd)
    os.remove(path)
    
    return {
        "entries": entries, "exits": exits, "open_pos": open_pos,
        "pnl": realized_pnl, "wins": wins, "losses": losses, "max_dd": max_dd,
        "final_eq": final_eq, "vetoes": veto_count["vetoes"], "high_vol": veto_count["high_vol"],
        "comms": comms, "slip": slip
    }

def main():
    logging.basicConfig(level=logging.ERROR)
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    chunk_size = len(bars) // 5
    results_prev = []
    results_curr = []
    
    for i in range(5):
        start_idx = i * chunk_size
        end_idx = (i + 1) * chunk_size
        
        w_bars = bars[start_idx:end_idx]
        
        # 110 bars of context required for the dynamic regime (90 rolling + 20 volatility window)
        ctx_start = max(0, start_idx - 110)
        context_bars = bars[ctx_start:start_idx] if start_idx > 0 else []
        
        print(f"Running W{i+1} PREVIOUS (Eval: {len(w_bars)}, Context: {len(context_bars)})")
        res_prev = run_simulation(w_bars, enable_dynamic=False, context_bars=context_bars)
        results_prev.append(res_prev)
        
        print(f"Running W{i+1} CURRENT (Eval: {len(w_bars)}, Context: {len(context_bars)})")
        res_curr = run_simulation(w_bars, enable_dynamic=True, context_bars=context_bars)
        results_curr.append(res_curr)
        
        print(f"W{i+1} PREV: PnL={res_prev['pnl']:.2f}, DD={res_prev['max_dd']:.2f}%, Entries={res_prev['entries']}")
        print(f"W{i+1} CURR: PnL={res_curr['pnl']:.2f}, DD={res_curr['max_dd']:.2f}%, Entries={res_curr['entries']}")
        
    import json
    with open("wf_results.json", "w") as f:
        json.dump({"prev": results_prev, "curr": results_curr}, f)
        
if __name__ == '__main__':
    main()
