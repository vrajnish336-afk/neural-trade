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

def run_simulation(bars, enable_dynamic=True):
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
    
    if not enable_dynamic:
        # Mock it back to the old dummy logic or just a flat RANGE_BOUND
        from app.core.models import MarketRegimeResult
        def mock_detect(bars, *args, **kwargs):
            return MarketRegimeResult(regime="RANGE_BOUND", confidence=0.5)
        import app.analysis.regime
        app.analysis.regime.detect_market_regime = mock_detect
        
    # Intercept to count vetoes
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
    runner.run('BTC_USDT', bars)
    
    # Audit DB
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM paper_orders WHERE status='FILLED'")
    entries = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM paper_closed_positions")
    exits = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM paper_positions")
    open_pos = c.fetchone()[0]
    
    c.execute("SELECT SUM(quantity * entry_price) FROM paper_positions")
    exposure_row = c.fetchone()[0]
    exposure = exposure_row if exposure_row else 0.0
    
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
    
    conn.close()
    
    os.close(fd)
    os.remove(path)
    
    return {
        "entries": entries, "exits": exits, "open_pos": open_pos, "exposure": exposure,
        "pnl": realized_pnl, "wins": wins, "losses": losses, "max_dd": max_dd,
        "final_eq": final_eq, "vetoes": veto_count["vetoes"], "high_vol": veto_count["high_vol"]
    }

def main():
    logging.basicConfig(level=logging.ERROR)
    
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    # Window 4
    chunk_size = len(bars) // 5
    w4 = bars[3*chunk_size:4*chunk_size]
    
    print("--- FULL AUDIT ---")
    full_dynamic = run_simulation(bars, enable_dynamic=True)
    print(f"Full Entries: {full_dynamic['entries']}")
    print(f"Full Exits: {full_dynamic['exits']}")
    print(f"Full Open Pos: {full_dynamic['open_pos']} (Exposure: {full_dynamic['exposure']})")
    print(f"Accounting diff (entries - exits - open_pos) = {full_dynamic['entries'] - full_dynamic['exits'] - full_dynamic['open_pos']}")
    
    print("--- W4 BASELINE ---")
    w4_baseline = run_simulation(w4, enable_dynamic=False)
    print(f"W4 Baseline - Entries: {w4_baseline['entries'] - w4_baseline['exits']}, Exits: {w4_baseline['exits']}, Wins/Losses: {w4_baseline['wins']}/{w4_baseline['losses']}")
    print(f"W4 Baseline - PnL: {w4_baseline['pnl']}, DD: {w4_baseline['max_dd']}%")
    print(f"W4 Baseline - High Vol: {w4_baseline['high_vol']}, Vetoes: {w4_baseline['vetoes']}")
    
    import importlib
    import app.analysis.regime
    importlib.reload(app.analysis.regime)
    
    print("--- W4 DYNAMIC ---")
    w4_dynamic = run_simulation(w4, enable_dynamic=True)
    print(f"W4 Dynamic - Entries: {w4_dynamic['entries'] - w4_dynamic['exits']}, Exits: {w4_dynamic['exits']}, Wins/Losses: {w4_dynamic['wins']}/{w4_dynamic['losses']}")
    print(f"W4 Dynamic - PnL: {w4_dynamic['pnl']}, DD: {w4_dynamic['max_dd']}%")
    print(f"W4 Dynamic - High Vol: {w4_dynamic['high_vol']}, Vetoes: {w4_dynamic['vetoes']}")

if __name__ == '__main__':
    main()
