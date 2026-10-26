import pytest
from datetime import datetime, timezone
import sqlite3

from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.decision.models import TraderDecision
from app.core.models import TradingSignal, RiskDecision
from unittest.mock import MagicMock

def _init_repo():
    import tempfile
    db_path = tempfile.mktemp()
    with sqlite3.connect(db_path) as conn:
        from app.database.schema import SCHEMA_SQL
        conn.executescript(SCHEMA_SQL)
    return PaperRepository(db_path=db_path)

def test_historical_portfolio_timestamp():
    """Test that get_or_create_portfolio uses the as_of timestamp."""
    repo = _init_repo()
    
    past_time = datetime(2020, 1, 1, tzinfo=timezone.utc)
    port = repo.get_or_create_portfolio("test_port", 10000.0, as_of=past_time)
    
    assert port['created_at'] == past_time.isoformat()
    
    # Check the snapshot
    snaps = repo.get_equity_snapshots("test_port")
    assert len(snaps) == 1
    assert snaps[0]['timestamp'] == past_time.isoformat()

def test_chronological_drawdown_correct(monkeypatch):
    """Test drawdown calculates correctly and excludes future data."""
    repo = _init_repo()
    
    t1 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    t2 = datetime(2020, 1, 2, tzinfo=timezone.utc)
    future = datetime(2025, 1, 1, tzinfo=timezone.utc)
    
    repo.get_or_create_portfolio("port1", 10000.0, as_of=t1)
    
    # Simulate a trade taking equity to 12000
    with sqlite3.connect(repo.db_path) as _:
        conn = repo._get_conn()
        conn.execute("UPDATE paper_portfolios SET current_equity=12000 WHERE portfolio_id='port1'")
        conn.execute(
            "INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at, unrealized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("snap2", "port1", t2.isoformat(), 12000.0, 12000.0, t2.isoformat(), 0)
        )
        # Artifact future snapshot
        conn.execute(
            "INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at, unrealized_pnl) VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("snap_future", "port1", future.isoformat(), 5000.0, 5000.0, future.isoformat(), 0)
        )
        conn.commit()
        
    from app.risk.drawdown import DrawdownService
    ds = DrawdownService()
    
    # Query as of t2 (future hidden)
    snaps = repo.get_equity_snapshots("port1", as_of=t2)
    assert len(snaps) == 2
    res = ds.calculate(snaps)
    assert res.max_drawdown_pct == 0.0 # 10k -> 12k
    
    # Query all (future visible)
    snaps_all = repo.get_equity_snapshots("port1")
    assert len(snaps_all) == 3
    res_all = ds.calculate(snaps_all)
    assert res_all.max_drawdown_pct > 0 # 12k -> 5k is a huge drawdown

from app.decision.models import TraderDecision, ScenarioAnalysis

def make_dec(ts):
    return TraderDecision(
        symbol="BTC/USDT", timestamp=ts, decision="LONG", rationale="Test", 
        confidence=1.0, evaluated_price=10000, risk_gate_approved=True,
        data_freshness="0m", regime="UNKNOWN", trend_context="NONE", volatility_context="NONE",
        multi_timeframe_alignment="NONE", strategy_signals=[], forecast_direction="NONE",
        forecast_uncertainty=0.0, world_context="NONE", scenario_analysis=ScenarioAnalysis(bullish_scenario="A", bearish_scenario="B", neutral_scenario="C"),
        main_risks=[], invalidation_conditions=[], paper_execution_eligible=True, risk_gate_reason=None
    )

def test_broker_uses_risk_decision_size():
    """Test broker uses exact RiskEngine position size and discards hardcoded argument."""
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    
    # Mock evaluate_trade to return a specific size
    mock_risk_decision = RiskDecision(approved=True, requested_risk=100, allowed_risk=100, position_size=1.23, rejection_reason=None, relevant_limit=None)
    re.evaluate_trade = MagicMock(return_value=mock_risk_decision)
    
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts)
    
    # Pass 999.0 as the hardcoded size, but it should use 1.23
    broker.execute_decision(dec, position_size=999.0)
    
    pos = repo.get_open_positions("test_port")
    assert len(pos) == 1
    assert pos[0]['quantity'] == 1.23

def test_broker_rejects_zero_invalid_size():
    """Test broker safely rejects zero or negative position sizes."""
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    
    mock_risk_decision = RiskDecision(approved=True, requested_risk=100, allowed_risk=100, position_size=0.0, rejection_reason=None, relevant_limit=None)
    re.evaluate_trade = MagicMock(return_value=mock_risk_decision)
    
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts)
    
    res = broker.execute_decision(dec, position_size=0.05)
    assert res is False
    pos = repo.get_open_positions("test_port")
    assert len(pos) == 0

def test_hard_position_exposure_cap_enforced():
    """Test that the broker honors RiskEngine rejection due to limits."""
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    
    mock_risk_decision = RiskDecision(approved=False, requested_risk=0, allowed_risk=0, position_size=0.0, rejection_reason="Too much exposure", relevant_limit="Exposure")
    re.evaluate_trade = MagicMock(return_value=mock_risk_decision)
    
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts)
    
    res = broker.execute_decision(dec, position_size=0.05)
    assert res is False
    pos = repo.get_open_positions("test_port")
    assert len(pos) == 0
def test_long_sl_tp_direction():
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts)
    dec.evaluated_price = 100.0
    dec.stop_loss = 90.0
    dec.take_profit = 110.0
    res = broker.execute_decision(dec, position_size=1.0, stop_loss=dec.stop_loss, take_profit=dec.take_profit)
    assert res is True
    pos = repo.get_open_positions("test_port")
    assert pos[0]['stop_loss'] == 90.0
    assert pos[0]['take_profit'] == 110.0

def test_short_sl_tp_direction():
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    ts = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts)
    dec.decision = "SHORT"
    dec.evaluated_price = 100.0
    dec.stop_loss = 110.0
    dec.take_profit = 90.0
    res = broker.execute_decision(dec, position_size=1.0, stop_loss=dec.stop_loss, take_profit=dec.take_profit)
    assert res is True
    pos = repo.get_open_positions("test_port")
    assert pos[0]['stop_loss'] == 110.0
    assert pos[0]['take_profit'] == 90.0

def test_short_loses_normally():
    repo = _init_repo()
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    re = RiskEngine(limits)
    broker = StreamingPaperBroker(repo, re, portfolio_id="test_port")
    ts1 = datetime(2020, 1, 1, tzinfo=timezone.utc)
    dec = make_dec(ts1)
    dec.decision = "SHORT"
    dec.evaluated_price = 100.0
    dec.stop_loss = 110.0
    res = broker.execute_decision(dec, position_size=1.0, stop_loss=dec.stop_loss)
    assert res is True
    pos = repo.get_open_positions("test_port")
    pos_id = pos[0]['position_id']
    ts2 = datetime(2020, 1, 2, tzinfo=timezone.utc)
    broker.execute_exit(pos_id, exit_price=110.0, timestamp=ts2, reason="SL")
    closed = repo.get_closed_positions("test_port")
    assert len(closed) == 1
    assert closed[0]['realized_pnl'] < 0
    assert closed[0]['realized_pnl'] <= -10.0
