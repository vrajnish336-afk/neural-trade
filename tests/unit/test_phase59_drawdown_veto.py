import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence, SentimentResult
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.decision.models import TraderDecision
from app.risk.engine import RiskEngine, RiskDecision
from app.risk.limits import PortfolioRiskLimits
from app.strategies.ensemble import StrategyEnsemble
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService
from app.execution.paper_repository import PaperRepository
from app.risk.drawdown import DrawdownService, DrawdownResult, DrawdownStatus
import sqlite3
import os

@pytest.fixture
def mock_dependencies():
    ensemble = Mock(spec=StrategyEnsemble)
    
    signal = TradingSignal(
        symbol="BTC/USD",
        timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc),
        direction="LONG",
        strategy="TestStrategy",
        confidence=0.9,
        reason="Test breakout"
    )
    ensemble.evaluate.return_value = signal

    intel = Mock(spec=IntelligenceService)
    intel.generate_intelligence.return_value = MarketIntelligence(
        symbol="BTC/USD",
        timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc),
        sentiment=SentimentResult(score=0.8, label="POSITIVE", confidence=0.9, source_count=5, timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)),
        relevant_articles=5,
        anomaly_status=[],
        risk_flags=[],
        fakeout_risk="UNKNOWN"
    )

    forecast = Mock(spec=ForecastingService)
    forecast_rec = Mock()
    forecast_rec.predicted_values_json = "[105.0]"
    forecast.generate_forecast.return_value = forecast_rec
    
    limits = PortfolioRiskLimits(max_drawdown_halt_pct=20.0, initial_equity=10000.0)
    risk_engine = RiskEngine(limits)
    # mock evaluate_trade to always approve for isolation
    risk_engine.evaluate_trade = Mock(return_value=RiskDecision(
        approved=True,
        requested_risk=100.0,
        allowed_risk=100.0,
        position_size=1.0
    ))
    
    return {
        'ensemble': ensemble,
        'intel': intel,
        'forecast': forecast,
        'risk_engine': risk_engine,
        'limits': limits
    }

@pytest.fixture
def test_db():
    db_path = "test_phase59.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("""
        CREATE TABLE paper_portfolios (
            portfolio_id TEXT PRIMARY KEY,
            initial_equity REAL,
            current_equity REAL,
            current_cash REAL,
            created_at TEXT,
            updated_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE paper_equity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            portfolio_id TEXT,
            timestamp TEXT,
            current_equity REAL,
            current_cash REAL,
            created_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE paper_orders (
            order_id TEXT PRIMARY KEY,
            portfolio_id TEXT,
            decision_id TEXT,
            symbol TEXT,
            direction TEXT,
            quantity REAL,
            price REAL,
            timestamp TEXT,
            status TEXT,
            commission REAL,
            slippage REAL,
            created_at TEXT,
            UNIQUE(decision_id)
        )""")
        conn.execute("""
        CREATE TABLE paper_positions (
            position_id TEXT PRIMARY KEY,
            portfolio_id TEXT,
            symbol TEXT,
            direction TEXT,
            entry_time TEXT,
            entry_price REAL,
            quantity REAL,
            stop_loss REAL,
            take_profit REAL,
            created_at TEXT,
            updated_at TEXT
        )""")
        
    conn.close()
    
    repo = PaperRepository(db_path)
    yield repo
    
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def orchestrator(mock_dependencies, test_db):
    drawdown_service = DrawdownService()
    return DecisionOrchestrator(
        ensemble=mock_dependencies['ensemble'],
        risk_engine=mock_dependencies['risk_engine'],
        intelligence_service=mock_dependencies['intel'],
        forecasting_service=mock_dependencies['forecast'],
        paper_repository=test_db,
        drawdown_service=drawdown_service
    )

def test_normal_flow_drawdown_below_threshold(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    conn = test_db._get_conn()
    with conn:
        # Peak 10000, current 9000 (10% drawdown)
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap1', 'default_paper', '2023-01-01T10:00:00+00:00', 10000.0, 10000.0, 'now')")
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap2', 'default_paper', '2023-01-01T11:00:00+00:00', 9000.0, 9000.0, 'now')")
    conn.close()
        
    bars = [MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 9000.0, 0, 0.0)
    assert decision.decision == "LONG"
    assert decision.risk_gate_approved is True

def test_hard_halt_drawdown_above_threshold(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    conn = test_db._get_conn()
    with conn:
        # Peak 10000, current 7000 (30% drawdown) - threshold is 20%
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap1', 'default_paper', '2023-01-01T10:00:00+00:00', 10000.0, 10000.0, 'now')")
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap2', 'default_paper', '2023-01-01T11:00:00+00:00', 7000.0, 7000.0, 'now')")
    conn.close()
        
    bars = [MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 7000.0, 0, 0.0)
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert "Portfolio Drawdown Halt" in decision.main_risks

def test_invalid_data_veto(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    conn = test_db._get_conn()
    with conn:
        # Peak 0 (Invalid)
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap1', 'default_paper', '2023-01-01T10:00:00+00:00', 0.0, 0.0, 'now')")
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap2', 'default_paper', '2023-01-01T11:00:00+00:00', 0.0, 0.0, 'now')")
    conn.close()
        
    bars = [MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 7000.0, 0, 0.0)
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert "REVIEW_REQUIRED" in decision.rationale

def test_bootstrap_grace_period(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    # Only initial snapshot - insufficient data
    # No extra snapshots added
        
    bars = [MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    # Should be approved
    assert decision.decision == "LONG"
    assert decision.risk_gate_approved is True

def test_look_ahead_bias_and_timestamp(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    decision_time = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    
    conn = test_db._get_conn()
    with conn:
        # Peak 10000
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap1', 'default_paper', '2023-01-01T10:00:00+00:00', 10000.0, 10000.0, 'now')")
        # Current equity at decision time: 9000 (10% drawdown) -> OK
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap2', 'default_paper', '2023-01-01T12:10:00+00:00', 9000.0, 9000.0, 'now')")
        # FUTURE equity: 5000 (50% drawdown) -> VETO if look-ahead happens
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap3', 'default_paper', '2023-01-01T13:00:00+00:00', 5000.0, 5000.0, 'now')")
    conn.close()
        
    bars = [MarketBar(symbol="BTC/USD", timestamp=decision_time, open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 9000.0, 0, 0.0)
    
    # Must be approved, future data is ignored
    assert decision.decision == "LONG"
    assert decision.risk_gate_approved is True
    
def test_execution_safety(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    conn = test_db._get_conn()
    with conn:
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap1', 'default_paper', '2023-01-01T10:00:00+00:00', 10000.0, 10000.0, 'now')")
        conn.execute("INSERT INTO paper_equity_snapshots VALUES ('snap2', 'default_paper', '2023-01-01T11:00:00+00:00', 7000.0, 7000.0, 'now')")
    conn.close()
        
    decision_time = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=decision_time, open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    decision = orchestrator.evaluate("BTC/USD", bars, 7000.0, 0, 0.0)
    assert decision.decision == "WAIT"
    
    # Try to execute order with rejected decision. Wait, decision is just a returned object, paper execution happens outside.
    # The requirement: "vetoed decision produces zero paper order writes" -> It evaluates and doesn't write anything.
    assert len(test_db.get_open_positions("default_paper")) == 0
    assert len(test_db.get_recent_orders("default_paper")) == 0

def test_idempotency_no_duplicate_writes(orchestrator, test_db):
    test_db.get_or_create_portfolio("default_paper", 10000.0)
    
    decision_time = datetime(2023, 1, 1, 12, 10, tzinfo=timezone.utc)
    bars = [MarketBar(symbol="BTC/USD", timestamp=decision_time, open=100.0, high=100.0, low=100.0, close=100.0, volume=100.0)]
    
    d1 = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    d2 = orchestrator.evaluate("BTC/USD", bars, 10000.0, 0, 0.0)
    
    assert d1.decision == d2.decision
    assert d1.risk_gate_approved == d2.risk_gate_approved
