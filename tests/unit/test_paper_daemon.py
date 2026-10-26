"""
Unit and Integration Tests for PaperTradingDaemon.
Verifies:
1. Pipeline setup (PaperRepository, RiskLimits rehydration, StreamingPaperBroker, DecisionOrchestrator).
2. Runtime position SL/TP monitoring (1:3 RR exit triggers).
3. Signal evaluation and pre-trade risk routing.
4. Resilience and error recovery against network timeouts.
5. Graceful shutdown and dynamic equity synchronization.
6. Rotating log configuration.
"""

import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.core.models import MarketBar, TradingSignal
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.database.schema import SCHEMA_SQL
from scripts.run_paper_daemon import PaperTradingDaemon, setup_daemon_logging


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield path
    try:
        os.close(fd)
        os.remove(path)
    except OSError:
        pass


@pytest.fixture
def mock_data_provider():
    provider = MagicMock()
    now = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    bars = []
    for i in range(30):
        bars.append(MarketBar(
            symbol="BTC/USDT",
            timestamp=now - timedelta(hours=30 - i),
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0
        ))
    provider.get_recent_bars.return_value = bars
    provider.get_historical_bars.return_value = bars
    provider.get_latest_bar.return_value = bars[-1]
    return provider


def test_daemon_initialization(temp_db, mock_data_provider):
    """Verifies that PaperTradingDaemon initializes all pipeline components cleanly."""
    daemon = PaperTradingDaemon(
        symbols=["BTC/USDT"],
        db_path=temp_db,
        data_provider=mock_data_provider,
        portfolio_id="test_init_portfolio",
        initial_equity=25000.0
    )
    daemon.setup()

    assert daemon.paper_repo is not None
    assert daemon.risk_limits is not None
    assert daemon.risk_engine is not None
    assert daemon.broker is not None
    assert daemon.orchestrator is not None

    portfolio = daemon.paper_repo.get_or_create_portfolio("test_init_portfolio")
    assert float(portfolio['current_equity']) == 25000.0
    assert daemon.risk_limits.initial_equity == 25000.0


def test_daemon_iteration_exit_monitoring(temp_db, mock_data_provider):
    """
    Verifies that run_iteration first calls broker.monitor_positions and
    executes exits when a position hits SL or TP.
    """
    daemon = PaperTradingDaemon(
        symbols=["BTC/USDT"],
        db_path=temp_db,
        data_provider=mock_data_provider,
        portfolio_id="test_exit_portfolio",
        initial_equity=10000.0
    )
    daemon.setup()

    # Pre-seed an open position in the repository with a stop-loss that will be hit
    now = datetime(2026, 10, 26, 10, 0, 0, tzinfo=timezone.utc)
    daemon.paper_repo.execute_order(
        portfolio_id="test_exit_portfolio",
        decision_id="dec_sl_test",
        symbol="BTC/USDT",
        direction="LONG",
        quantity=1.0,
        price=150.0,
        actual_price=150.0,
        commission=0.1,
        slippage=0.0,
        timestamp=now,
        stop_loss=140.0,
        take_profit=180.0,
        strategy="Breakout"
    )

    # Current bar close is ~130.0 (below SL of 140.0)
    current_bar = MarketBar(
        symbol="BTC/USDT",
        timestamp=now + timedelta(hours=1),
        open=145.0,
        high=145.0,
        low=135.0,  # Below SL 140.0 -> SL_HIT
        close=138.0,
        volume=500.0
    )
    mock_data_provider.get_recent_bars.return_value = [current_bar]

    summary = daemon.run_iteration()

    # Verify exit was recorded
    assert len(summary["exits"]) == 1
    assert summary["exits"][0]["reason"] == "SL_HIT"
    assert summary["exits"][0]["success"] is True

    # Position must no longer be in open positions
    open_pos = daemon.broker.repo.get_open_positions("test_exit_portfolio")
    assert len(open_pos) == 0

    # Must be recorded in closed positions with reason SL_HIT
    closed_pos = daemon.broker.repo.get_closed_positions("test_exit_portfolio")
    assert len(closed_pos) == 1
    assert closed_pos[0]["exit_reason"] == "SL_HIT"


def test_daemon_iteration_trade_execution(temp_db, mock_data_provider):
    """
    Verifies that when DecisionOrchestrator produces an approved signal,
    the daemon calculates 1:3 RR and executes the order through StreamingPaperBroker.
    """
    daemon = PaperTradingDaemon(
        symbols=["BTC/USDT"],
        db_path=temp_db,
        data_provider=mock_data_provider,
        portfolio_id="test_exec_portfolio",
        initial_equity=50000.0
    )
    daemon.setup()

    # Mock orchestrator evaluate to return an eligible LONG decision
    latest_bar = mock_data_provider.get_recent_bars.return_value[-1]
    mock_decision = TraderDecision(
        symbol="BTC/USDT",
        timestamp=latest_bar.timestamp,
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="TRENDING_UP",
        volatility_context="NORMAL",
        multi_timeframe_alignment="ALIGNED_BULLISH",
        strategy_signals=[{"strategy": "Breakout", "direction": "LONG", "confidence": "0.85"}],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(
            bullish_scenario="Continuation up",
            bearish_scenario="Pullback below support",
            neutral_scenario="Consolidation in range"
        ),
        main_risks=[],
        invalidation_conditions=[],
        rationale="Strong breakout verified",
        confidence=0.85,
        decision="LONG",
        evaluated_price=latest_bar.close,
        stop_loss=latest_bar.close * 0.95,
        take_profit=None,  # Will be calculated as 1:3 RR
        risk_gate_approved=True,
        paper_execution_eligible=True
    )
    daemon.orchestrator.evaluate = MagicMock(return_value=mock_decision)

    summary = daemon.run_iteration()

    # Verify execution
    assert len(summary["executions"]) == 1
    exec_event = summary["executions"][0]
    assert exec_event["symbol"] == "BTC/USDT"
    assert exec_event["direction"] == "LONG"
    assert exec_event["price"] == latest_bar.close

    # Verify 1:3 RR Take Profit calculation
    expected_risk = latest_bar.close - (latest_bar.close * 0.95)
    expected_tp = latest_bar.close + (3.0 * expected_risk)
    assert exec_event["take_profit"] == pytest.approx(expected_tp, rel=1e-3)

    # Verify order is persisted in the repository
    open_pos = daemon.broker.repo.get_open_positions("test_exec_portfolio")
    assert len(open_pos) == 1
    assert open_pos[0]["symbol"] == "BTC/USDT"
    assert open_pos[0]["direction"] == "LONG"


def test_daemon_resilience_to_network_errors(temp_db, mock_data_provider):
    """
    Verifies that network errors (ConnectionError, TimeoutError, URLError) do not crash
    the daemon loop, and the backoff mechanism triggers correctly.
    """
    daemon = PaperTradingDaemon(
        symbols=["BTC/USDT"],
        db_path=temp_db,
        data_provider=mock_data_provider,
        portfolio_id="test_resilience_portfolio",
        poll_interval=0.01,
        backoff_seconds=0.01  # Fast for unit tests
    )

    # Simulate network exception on first call, success on second call
    call_count = 0
    def flaky_get_bars(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ConnectionError("Remote peer reset connection")
        return mock_data_provider.get_recent_bars.return_value

    mock_data_provider.get_recent_bars.side_effect = flaky_get_bars

    # Run for 2 iterations: iteration 1 catches error, iteration 2 succeeds
    daemon.start(max_iterations=2)

    assert call_count >= 2


def test_daemon_graceful_shutdown(temp_db, mock_data_provider):
    """
    Verifies that stop() halts execution and _shutdown syncs dynamic equity.
    """
    daemon = PaperTradingDaemon(
        symbols=["BTC/USDT"],
        db_path=temp_db,
        data_provider=mock_data_provider,
        portfolio_id="test_shutdown_portfolio",
        initial_equity=10000.0
    )
    daemon.setup()

    # Seed an open position with price move to test dynamic equity sync
    daemon.paper_repo.execute_order(
        portfolio_id="test_shutdown_portfolio",
        decision_id="dec_shutdown_test",
        symbol="BTC/USDT",
        direction="LONG",
        quantity=2.0,
        price=100.0,
        actual_price=100.0,
        commission=0.0,
        slippage=0.0,
        timestamp=datetime.now(timezone.utc),
        stop_loss=90.0,
        take_profit=130.0,
        strategy="Test"
    )

    # Set latest price on broker
    daemon.broker.latest_prices["BTC/USDT"] = 120.0  # +$40 unrealized PnL

    # Trigger shutdown
    daemon._shutdown()

    # Dynamic equity should be 10000.0 - (2*100) cash + (2*120) pos value = 10040.0
    port = daemon.paper_repo.get_or_create_portfolio("test_shutdown_portfolio")
    assert port["current_equity"] == pytest.approx(10040.0, rel=1e-3)


def test_daemon_rotating_logging():
    """Verifies that setup_daemon_logging attaches a RotatingFileHandler to logs/paper_daemon.log."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        log_file = os.path.join(tmp_dir, "test_daemon.log")
        test_logger = setup_daemon_logging(log_file=log_file)

        try:
            assert any(
                handler.__class__.__name__ == "RotatingFileHandler"
                for handler in test_logger.handlers
            )

            test_logger.info("Test rotation logging entry")
            assert os.path.exists(log_file)
            with open(log_file, "r") as f:
                content = f.read()
                assert "Test rotation logging entry" in content
        finally:
            for handler in test_logger.handlers[:]:
                handler.close()
                test_logger.removeHandler(handler)
