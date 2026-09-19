import logging
import sqlite3
import os
import tempfile
import pandas as pd
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
from app.core.models import MarketRegimeResult
from app.diagnostics.models import RejectionReason

def run_simulation(bars, mode="ON", context_bars=None):
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
    import app.strategies.ensemble
    
    # Reload modules to reset state
    importlib.reload(app.analysis.regime)
    importlib.reload(app.strategies.ensemble)
    
    veto_stats = {"hv_veto": 0, "dir_veto": 0, "hv_detected": 0}
    
    # Intercept telemetry to count vetoes
    real_record_rejection = app.strategies.ensemble.telemetry.record_rejection
    def mock_record_rejection(reason, context, *args, **kwargs):
        if reason == RejectionReason.REGIME_VETO:
            if context == "HIGH_VOLATILITY":
                veto_stats["hv_veto"] += 1
            elif context in ["TRENDING_UP", "TRENDING_DOWN", "RANGE_BOUND"]:
                veto_stats["dir_veto"] += 1
        real_record_rejection(reason, context, *args, **kwargs)
    app.strategies.ensemble.telemetry.record_rejection = mock_record_rejection
    
    # Intercept regime detector to count HV detections
    real_detect = app.analysis.regime.detect_market_regime
    def mock_detect(*args, **kwargs):
        res = real_detect(*args, **kwargs)
        if res.regime == "HIGH_VOLATILITY":
            veto_stats["hv_detected"] += 1
        return res
    app.analysis.regime.detect_market_regime = mock_detect
    
    if mode == "OFF":
        # Disable HV veto elegantly by zeroing volatility metric at the source
        # This completely preserves directional regime logic and 110-bar warm-up block
        def mock_calc_vol(series, lookback):
            return pd.Series(0.0, index=series.index)
        app.analysis.regime.calculate_volatility = mock_calc_vol
        
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
        "entries": entries, "exits": exits,
        "pnl": realized_pnl, "wins": wins, "losses": losses, "max_dd": max_dd,
        "final_eq": final_eq, "hv_veto": veto_stats["hv_veto"], "dir_veto": veto_stats["dir_veto"],
        "hv_detected": veto_stats["hv_detected"], "comms": comms, "slip": slip
    }

def main():
    logging.basicConfig(level=logging.ERROR)
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    chunk_size = len(bars) // 5
    
    print(f"{'W':<2} | {'Mode':<4} | {'Eq':<9} | {'PnL':<9} | {'DD%':<5} | {'W/L':<5} | {'En/Ex':<5} | {'HV_Det':<6} | {'HV_V':<4} | {'Dir_V':<5} | {'Comms':<6} | {'Slip':<6}")
    print("-" * 110)
    
    for i in range(5):
        start_idx = i * chunk_size
        end_idx = (i + 1) * chunk_size
        w_bars = bars[start_idx:end_idx]
        ctx_start = max(0, start_idx - 110)
        context_bars = bars[ctx_start:start_idx] if start_idx > 0 else []
        
        res_on = run_simulation(w_bars, mode="ON", context_bars=context_bars)
        res_off = run_simulation(w_bars, mode="OFF", context_bars=context_bars)
        
        print(f"W{i+1:<1} | ON   | {res_on['final_eq']:<9.2f} | {res_on['pnl']:<9.2f} | {res_on['max_dd']:<5.2f} | {res_on['wins']}/{res_on['losses']:<3} | {res_on['entries']}/{res_on['exits']:<3} | {res_on['hv_detected']:<6} | {res_on['hv_veto']:<4} | {res_on['dir_veto']:<5} | {res_on['comms']:<6.2f} | {res_on['slip']:<6.2f}")
        print(f"W{i+1:<1} | OFF  | {res_off['final_eq']:<9.2f} | {res_off['pnl']:<9.2f} | {res_off['max_dd']:<5.2f} | {res_off['wins']}/{res_off['losses']:<3} | {res_off['entries']}/{res_off['exits']:<3} | {res_off['hv_detected']:<6} | {res_off['hv_veto']:<4} | {res_off['dir_veto']:<5} | {res_off['comms']:<6.2f} | {res_off['slip']:<6.2f}")
        
        diff_pnl = res_on['pnl'] - res_off['pnl']
        diff_dd = res_on['max_dd'] - res_off['max_dd']
        print(f"     | DIFF | {diff_pnl:<9.2f} | {diff_dd:<6.2f} |")
        print("-" * 80)

if __name__ == '__main__':
    main()
