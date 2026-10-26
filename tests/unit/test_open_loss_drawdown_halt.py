"""
Unit tests explicitly verifying that open-position floating losses are reflected
in dynamic equity and correctly trigger the Portfolio Drawdown Halt.
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from app.core.models import MarketBar, TradingSignal, MarketIntelligence, SentimentResult
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.database.schema import SCHEMA_SQL
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.portfolio import PortfolioState, PortfolioRiskManager, PortfolioRiskConfig
from app.risk.drawdown import DrawdownService, DrawdownStatus
from app.strategies.ensemble import StrategyEnsemble
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService
from app.backtesting.models import ExecutionAssumptions


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield path
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)


@pytest.fixture
def repo(temp_db):
    return PaperRepository(db_path=temp_db)


@pytest.fixture
def risk_engine():
    # 20% drawdown halt threshold, initial equity 10,000.0, max_exposure_pct 2.0, 30% risk per trade
    limits = PortfolioRiskLimits(initial_equity=10000.0, max_exposure_pct=2.0, max_drawdown_halt_pct=20.0)
    return RiskEngine(limits, 0.30)


@pytest.fixture
def broker(repo, risk_engine):
    return StreamingPaperBroker(
        repository=repo,
        risk_engine=risk_engine,
        cost_config=ExecutionAssumptions.BASELINE,
        portfolio_id="test_dd_portfolio"
    )


def _make_decision(symbol: str, price: float, direction: str = "LONG", timestamp: datetime = None) -> TraderDecision:
    ts = timestamp or datetime.now(timezone.utc)
    return TraderDecision(
        symbol=symbol,
        timestamp=ts,
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="TRENDING_UP",
        volatility_context="NORMAL",
        multi_timeframe_alignment="UNKNOWN",
        strategy_signals=[{"strategy": "Breakout", "direction": direction}],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="B", bearish_scenario="B", neutral_scenario="N"),
        main_risks=[],
        invalidation_conditions=[],
        rationale="Test trade",
        confidence=0.9,
        decision=direction,
        evaluated_price=price,
        stop_loss=price * 0.95 if direction == "LONG" else price * 1.05,
        take_profit=price * 1.15 if direction == "LONG" else price * 0.85,
        risk_gate_approved=True,
        paper_execution_eligible=True
    )


# ---------------------------------------------------------------------------
# 1. Dynamic Equity Calculation Tests
# ---------------------------------------------------------------------------

def test_portfolio_state_dynamic_equity():
    """Verify PortfolioState calculates true dynamic equity including unrealized open loss."""
    state = PortfolioState(current_cash=10000.0)
    assert state.current_equity == 10000.0

    # Add a LONG position entered at 100 with qty 10 (value 1000)
    state.add_position({
        'position_id': 'pos1',
        'symbol': 'BTC/USD',
        'direction': 'LONG',
        'entry_price': 100.0,
        'quantity': 10.0,
        'current_price': 100.0,
        'stop_loss': 90.0,
        'take_profit': 130.0,
        'signal_metadata': {'strategies': 'Test'}
    })
    assert state.calculate_unrealized_pnl() == 0.0
    assert state.current_equity == 10000.0

    # Price drops to 70: unrealized loss = (70 - 100) * 10 = -300
    pnl = state.calculate_unrealized_pnl(current_prices={'BTC/USD': 70.0})
    assert pnl == -300.0
    assert state.get_dynamic_equity(current_prices={'BTC/USD': 70.0}) == 9700.0


def test_paper_repository_dynamic_equity_sync(repo):
    """Verify PaperRepository computes and syncs dynamic equity with open positions."""
    portfolio_id = "sync_test"
    repo.get_or_create_portfolio(portfolio_id, initial_equity=10000.0)

    # Record an entry order for 1.0 BTC at 50000.0
    now = datetime.now(timezone.utc)
    success = repo.execute_order(
        portfolio_id=portfolio_id,
        decision_id="dec_entry_1",
        symbol="BTC/USD",
        direction="LONG",
        quantity=1.0,
        price=50000.0,
        actual_price=50000.0,
        commission=10.0,
        slippage=0.0,
        timestamp=now,
        stop_loss=45000.0,
        take_profit=65000.0,
        strategy="Test"
    )
    assert success is True

    # Realized cash should be 10000.0 - 10.0 = 9990.0
    port = repo.get_or_create_portfolio(portfolio_id)
    assert port['current_cash'] == 9990.0

    # Without price updates, unrealized PnL is 0.0
    assert repo.calculate_unrealized_pnl(portfolio_id) == 0.0

    # Market price drops to 47000.0 (-3000.0 open loss)
    unrealized = repo.calculate_unrealized_pnl(portfolio_id, current_prices={"BTC/USD": 47000.0})
    assert unrealized == -3000.0

    dynamic_eq = repo.get_dynamic_equity(portfolio_id, current_prices={"BTC/USD": 47000.0})
    assert dynamic_eq == 9990.0 - 3000.0 == 6990.0

    # Sync into database
    synced_eq = repo.sync_dynamic_equity(portfolio_id, current_prices={"BTC/USD": 47000.0})
    assert synced_eq == 6990.0
    port_updated = repo.get_or_create_portfolio(portfolio_id)
    assert port_updated['current_equity'] == 6990.0


# ---------------------------------------------------------------------------
# 2. Drawdown Halt Enforcement with Open Loss Tests
# ---------------------------------------------------------------------------

def test_open_position_loss_triggers_drawdown_halt_in_broker(broker, repo):
    """
    Severe open-position loss pushes true dynamic equity past the 20% halt threshold,
    causing the RiskEngine to authoritative-veto and block new entry orders.
    """
    initial_time = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
    
    # 1. Execute initial entry order: BUY BTC at 100.0 with SL 70.0 (sizes 100 units on 30% risk)
    entry_dec = _make_decision("BTC/USD", 100.0, "LONG", timestamp=initial_time)
    entry_dec.stop_loss = 70.0
    entry_dec.take_profit = 190.0
    success = broker.execute_decision(entry_dec, position_size=100.0, stop_loss=70.0, take_profit=190.0)
    assert success is True

    # Verify open position exists
    positions = repo.get_open_positions(broker.portfolio_id)
    assert len(positions) == 1

    # 2. Market price drops from 100 to 70 ($-3000 open loss on $10k account = ~30% drawdown)
    # Stream in current bar with dropped price
    drop_time = initial_time + timedelta(hours=1)
    bar = MarketBar(
        symbol="BTC/USD",
        timestamp=drop_time,
        open=75.0,
        high=75.0,
        low=69.5,
        close=70.0,
        volume=100.0
    )
    broker.monitor_positions(bar)
    assert broker.latest_prices["BTC/USD"] == 70.0

    # Check that repo synced dynamic equity accounts for open loss
    port = repo.get_or_create_portfolio(broker.portfolio_id)
    assert port['current_equity'] < 7500.0  # ~6990

    # 3. New entry signal arrives for ETH/USD
    new_dec = _make_decision("ETH/USD", 50.0, "LONG", timestamp=drop_time)
    new_dec.stop_loss = 45.0
    new_dec.take_profit = 65.0

    # 4. Attempt to execute the new decision - MUST be blocked by Drawdown Halt!
    result = broker.execute_decision(new_dec, position_size=10.0, stop_loss=45.0, take_profit=65.0)
    assert result is False

    # 5. Verify rejection was recorded in rejected_paper_orders with Drawdown Veto reason
    rejected = repo.get_rejected_orders(broker.portfolio_id)
    assert len(rejected) >= 1
    rejection_reasons = [r['reason'] for r in rejected]
    assert any("DRAWDOWN_VETO" in r for r in rejection_reasons)


def test_open_position_recovery_clears_drawdown_halt(broker, repo):
    """
    When market price recovers from drawdown, the halt is cleared and new entries proceed.
    """
    initial_time = datetime(2023, 1, 1, 10, 0, tzinfo=timezone.utc)
    
    # 1. Execute initial entry order
    entry_dec = _make_decision("BTC/USD", 100.0, "LONG", timestamp=initial_time)
    entry_dec.stop_loss = 70.0
    entry_dec.take_profit = 190.0
    assert broker.execute_decision(entry_dec, position_size=100.0, stop_loss=70.0, take_profit=190.0) is True

    # 2. Simulate price recovery to entry price (100.0)
    recover_time = initial_time + timedelta(hours=2)
    bar = MarketBar(
        symbol="BTC/USD",
        timestamp=recover_time,
        open=99.0,
        high=101.0,
        low=99.0,
        close=100.0,
        volume=100.0
    )
    broker.monitor_positions(bar)

    # 3. Dynamic equity is ~9990 (only commission loss ~0.1% drawdown, well below 20%)
    port = repo.get_or_create_portfolio(broker.portfolio_id)
    assert port['current_equity'] > 9500.0

    # 4. New entry for ETH/USD should be approved
    new_dec = _make_decision("ETH/USD", 50.0, "LONG", timestamp=recover_time)
    new_dec.stop_loss = 45.0
    new_dec.take_profit = 65.0
    result = broker.execute_decision(new_dec, position_size=10.0, stop_loss=45.0, take_profit=65.0)
    assert result is True


def test_decision_orchestrator_drawdown_halt_with_open_loss(repo):
    """
    DecisionOrchestrator.evaluate checks dynamic equity with open-loss and vetoes signals.
    """
    limits = PortfolioRiskLimits(max_drawdown_halt_pct=20.0, initial_equity=10000.0)
    risk_engine = RiskEngine(limits)

    ensemble = Mock(spec=StrategyEnsemble)
    signal = TradingSignal(
        symbol="ETH/USD",
        timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        direction="LONG",
        strategy="Breakout",
        confidence=0.9,
        reason="Breakout detected"
    )
    ensemble.evaluate.return_value = signal

    intel = Mock(spec=IntelligenceService)
    intel.generate_intelligence.return_value = MarketIntelligence(
        symbol="ETH/USD",
        timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc),
        sentiment=SentimentResult(score=0.8, label="POSITIVE", confidence=0.9, source_count=5, timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc)),
        relevant_articles=5,
        anomaly_status=[],
        risk_flags=[],
        fakeout_risk="UNKNOWN"
    )

    forecast = Mock(spec=ForecastingService)
    forecast_rec = Mock()
    forecast_rec.predicted_values_json = "[3100.0]"
    forecast.generate_forecast.return_value = forecast_rec

    drawdown_service = DrawdownService()
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel,
        forecasting_service=forecast,
        paper_repository=repo,
        drawdown_service=drawdown_service
    )

    portfolio_id = "orch_dd_test"
    repo.get_or_create_portfolio(portfolio_id, 10000.0)

    # Insert an open position for BTC/USD entered at 50000 with qty 1.0
    conn = repo._get_conn()
    with conn:
        conn.execute("""
            INSERT INTO paper_positions (position_id, portfolio_id, symbol, direction, entry_time, entry_price, quantity, stop_loss, take_profit, created_at, updated_at)
            VALUES ('pos_btc', 'orch_dd_test', 'BTC/USD', 'LONG', '2023-01-01T10:00:00+00:00', 50000.0, 1.0, 45000.0, 65000.0, 'now', 'now')
        """)
        # Historical initial snapshot: 10000.0
        conn.execute("INSERT INTO paper_equity_snapshots (snapshot_id, portfolio_id, timestamp, current_equity, current_cash, created_at) VALUES ('s1', 'orch_dd_test', '2023-01-01T10:00:00+00:00', 10000.0, 10000.0, 'now')")
    conn.close()

    # Now evaluate BTC/USD at 47000 ($-3000 loss -> ~30% drawdown)
    bars = [
        MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 11, 0, tzinfo=timezone.utc), open=48000.0, high=48000.0, low=46900.0, close=47000.0, volume=100.0),
        MarketBar(symbol="BTC/USD", timestamp=datetime(2023, 1, 1, 12, 0, tzinfo=timezone.utc), open=47000.0, high=47100.0, low=46900.0, close=47000.0, volume=100.0)
    ]

    decision = orchestrator.evaluate(
        symbol="BTC/USD",
        bars=bars,
        current_equity=10000.0,
        current_positions_count=1,
        current_exposure=50000.0,
        portfolio_id=portfolio_id
    )

    # Decision must be WAIT and risk_gate_approved must be False due to Drawdown Halt
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert any("Portfolio Drawdown Halt" in r for r in decision.main_risks)
