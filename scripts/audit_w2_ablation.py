import logging
import sqlite3
import os
import tempfile
import pandas as pd
from datetime import datetime, timezone
from unittest.mock import Mock, patch

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
from app.database.schema import SCHEMA_SQL
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
    
    importlib.reload(app.analysis.regime)
    importlib.reload(app.strategies.ensemble)
    
    events = []
    
    real_record_rejection = app.strategies.ensemble.telemetry.record_rejection
    
    current_eval_state = {"reason": None, "context": None, "signals": [], "hv_detected": False, "regime_eval": None}
    
    def mock_record_rejection(reason, context, *args, **kwargs):
        current_eval_state["reason"] = reason
        current_eval_state["context"] = context
        real_record_rejection(reason, context, *args, **kwargs)
    app.strategies.ensemble.telemetry.record_rejection = mock_record_rejection
    
    real_detect = app.analysis.regime.detect_market_regime
    
    def mock_detect(*args, **kwargs):
        res_real = real_detect(*args, **kwargs)
        if res_real.regime == "HIGH_VOLATILITY":
            current_eval_state["hv_detected"] = True
            
        if mode == "OFF" and res_real.regime == "HIGH_VOLATILITY":
            bars_len = len(args[0]) if args else len(kwargs.get('bars', []))
            def mock_calc_vol(series, lookback):
                return pd.Series(0.0, index=series.index)
            with patch('app.analysis.regime.calculate_volatility', side_effect=mock_calc_vol):
                res_trend = real_detect(*args, **kwargs)
            current_eval_state["regime_eval"] = res_trend.regime
            return res_trend
            
        current_eval_state["regime_eval"] = res_real.regime
        return res_real

    app.analysis.regime.detect_market_regime = mock_detect
    
    real_ensemble_evaluate = ensemble.evaluate
    
    def mock_ensemble_evaluate(bars, regime, intelligence=None, pre_generated_signals=None):
        current_eval_state["reason"] = None
        current_eval_state["context"] = None
        current_eval_state["signals"] = []
        current_eval_state["hv_detected"] = False
        current_eval_state["regime_eval"] = None
        
        # We need to run the regime check manually inside this mock to trigger the telemetry 
        # since the real orchestration evaluates regime first.
        # Actually, orchestrator already evaluated regime, so let's just use what's passed in!
        if regime.regime == "HIGH_VOLATILITY":
            current_eval_state["hv_detected"] = True
            
        current_eval_state["regime_eval"] = regime.regime
        
        sig = real_ensemble_evaluate(bars, regime, intelligence, pre_generated_signals)
        
        events.append({
            "timestamp": bars[-1].timestamp,
            "close": bars[-1].close,
            "has_open_pos": False, # Will fill later
            "evaluated": True,
            "hv_detected": current_eval_state["hv_detected"],
            "regime_eval": current_eval_state["regime_eval"],
            "veto_reason": current_eval_state["reason"],
            "veto_context": current_eval_state["context"],
            "signal_generated": sig is not None,
            "direction": sig.direction if sig else None
        })
        return sig
        
    ensemble.evaluate = mock_ensemble_evaluate
    
    real_evaluate = orchestrator.evaluate
    def mock_evaluate(symbol, bars, current_equity, current_positions_count, current_exposure, portfolio_id="default_paper"):
        positions = orchestrator.paper_repository.get_open_positions(portfolio_id)
        has_pos = any(p['symbol'] == symbol for p in positions)
        if has_pos:
            events.append({
                "timestamp": bars[-1].timestamp,
                "close": bars[-1].close,
                "has_open_pos": True,
                "evaluated": False,
                "hv_detected": False,
                "regime_eval": None,
                "veto_reason": None,
                "veto_context": None,
                "signal_generated": False,
                "direction": None
            })
        return real_evaluate(symbol, bars, current_equity, current_positions_count, current_exposure, portfolio_id)
        
    orchestrator.evaluate = mock_evaluate

    runner = PaperSimulationRunner(broker, orchestrator)
    runner.run('BTC_USDT', bars, context_bars=context_bars)
    
    # Audit DB to get trades
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM paper_closed_positions")
    trades = [dict(row) for row in c.fetchall()]
    conn.close()
    
    os.close(fd)
    os.remove(path)
    
    return {"events": events, "trades": trades}

def main():
    logging.basicConfig(level=logging.ERROR)
    provider = CsvHistoricalDataProvider('data/historical')
    bars = provider.get_historical_bars('BTC_USDT', '1D', datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2030, 1, 1, tzinfo=timezone.utc))
    
    chunk_size = len(bars) // 5
    i = 1 # W2
    start_idx = i * chunk_size
    end_idx = (i + 1) * chunk_size
    w_bars = bars[start_idx:end_idx]
    ctx_start = max(0, start_idx - 110)
    context_bars = bars[ctx_start:start_idx] if start_idx > 0 else []
    
    res_on = run_simulation(w_bars, mode="ON", context_bars=context_bars)
    res_off = run_simulation(w_bars, mode="OFF", context_bars=context_bars)
    
    events_on = {e["timestamp"]: e for e in res_on["events"]}
    events_off = {e["timestamp"]: e for e in res_off["events"]}
    
    print("--- DIVERGENCE ANALYSIS ---")
    for b in w_bars:
        ts = b.timestamp
        e_on = events_on.get(ts)
        e_off = events_off.get(ts)
        
        if not e_on or not e_off:
            continue
            
        if e_on["has_open_pos"] != e_off["has_open_pos"] or e_on["signal_generated"] != e_off["signal_generated"] or e_on["veto_reason"] != e_off["veto_reason"]:
            print(f"DIVERGENCE AT: {ts}")
            print(f"ON : POS={e_on['has_open_pos']} EVAL={e_on['evaluated']} HV={e_on['hv_detected']} REG={e_on['regime_eval']} VETO={e_on['veto_reason']} ({e_on['veto_context']}) SIG={e_on['signal_generated']}")
            print(f"OFF: POS={e_off['has_open_pos']} EVAL={e_off['evaluated']} HV={e_off['hv_detected']} REG={e_off['regime_eval']} VETO={e_off['veto_reason']} ({e_off['veto_context']}) SIG={e_off['signal_generated']}")
                
    print("\n--- TRADES OFF ---")
    for t in res_off["trades"]:
        print(t)
        
    print("\n--- TRADES ON ---")
    for t in res_on["trades"]:
        print(t)

if __name__ == '__main__':
    main()
