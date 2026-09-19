import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.database.schema import SCHEMA_SQL
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp()
    
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    
    yield path
    
    os.close(fd)
    os.remove(path)

@pytest.fixture
def repo(temp_db):
    return PaperRepository(db_path=temp_db)

@pytest.fixture
def risk_engine():
    return RiskEngine(PortfolioRiskLimits(initial_equity=10000.0), 0.01)

@pytest.fixture
def broker(repo, risk_engine):
    from app.backtesting.models import ExecutionAssumptions
    return StreamingPaperBroker(repository=repo, risk_engine=risk_engine, cost_config=ExecutionAssumptions.BASELINE)
    
@pytest.fixture
def base_decision():
    return TraderDecision(
        symbol="BTC/USD",
        timestamp=datetime.now(timezone.utc),
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="TRENDING_UP",
        volatility_context="NORMAL",
        multi_timeframe_alignment="UNKNOWN",
        strategy_signals=[],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="B", bearish_scenario="B", neutral_scenario="N"),
        main_risks=[],
        invalidation_conditions=[],
        rationale="Test",
        confidence=0.9,
        decision="LONG",
        evaluated_price=100.0,
        risk_gate_approved=True,
        paper_execution_eligible=True
    )

def test_reject_wait(broker, base_decision):
    base_decision.decision = "WAIT"
    assert broker.execute_decision(base_decision, 1.0) is False

def test_reject_no_trade(broker, base_decision):
    base_decision.decision = "NO TRADE"
    assert broker.execute_decision(base_decision, 1.0) is False

def test_reject_risk_veto_bypass(broker, base_decision):
    base_decision.decision = "LONG"
    base_decision.risk_gate_approved = False
    assert broker.execute_decision(base_decision, 1.0) is False

def test_approved_decision_success_and_idempotency(broker, base_decision):
    base_decision.decision = "LONG"
    base_decision.risk_gate_approved = True
    
    # First execution should succeed
    success1 = broker.execute_decision(base_decision, position_size=1.0)
    assert success1 is True
    
    # Second execution of identical decision should be rejected for idempotency
    success2 = broker.execute_decision(base_decision, position_size=1.0)
    assert success2 is False

def test_accounting_consistency(broker, base_decision):
    initial_equity = 10000.0
    
    # Execute
    success = broker.execute_decision(base_decision, position_size=1.0)
    assert success is True
    
    # Verify portfolio state
    portfolio = broker.repo.get_or_create_portfolio(broker.portfolio_id)
    assert portfolio['initial_equity'] == initial_equity
    # Current equity should be strictly less than initial due to commission
    assert portfolio['current_equity'] < initial_equity
    assert portfolio['current_cash'] == portfolio['current_equity']
    
    state = broker.get_realtime_portfolio()
    assert len(state.open_positions) == 1
    assert state.open_positions[0]['symbol'] == "BTC/USD"
    assert state.open_positions[0]['direction'] == "LONG"
    # Verify slippage: entry_price should be > 100.0 (dummy price) due to LONG slippage
    assert state.open_positions[0]['entry_price'] > 100.0 

def test_reopen_db_preserves_state(temp_db, risk_engine, base_decision):
    from app.backtesting.models import ExecutionAssumptions
    repo1 = PaperRepository(temp_db)
    broker1 = StreamingPaperBroker(repository=repo1, risk_engine=risk_engine, cost_config=ExecutionAssumptions.BASELINE)
    
    success = broker1.execute_decision(base_decision, position_size=1.0)
    assert success is True
    
    # Reopen
    repo2 = PaperRepository(temp_db)
    broker2 = StreamingPaperBroker(repository=repo2, risk_engine=risk_engine, cost_config=ExecutionAssumptions.BASELINE)
    
    state = broker2.get_realtime_portfolio()
    assert len(state.open_positions) == 1
    
    portfolio = repo2.get_or_create_portfolio(broker2.portfolio_id)
    assert portfolio['current_equity'] < 10000.0

def test_execute_exit_success(broker, base_decision):
    initial_equity = 10000.0
    
    # 1. Execute Entry (LONG at 100)
    base_decision.decision = "LONG"
    base_decision.evaluated_price = 100.0
    broker.execute_decision(base_decision, position_size=1.0)
    
    portfolio = broker.repo.get_or_create_portfolio(broker.portfolio_id)
    assert portfolio['current_cash'] < initial_equity
    positions = broker.get_realtime_portfolio().open_positions
    assert len(positions) == 1
    
    pos_id = broker.repo.get_open_positions(broker.portfolio_id)[0]['position_id']
    
    # 2. Execute Exit (at 110)
    from datetime import datetime, timezone, timedelta
    exit_ts = base_decision.timestamp + timedelta(hours=1)
    
    success = broker.execute_exit(pos_id, 110.0, exit_ts)
    assert success is True
    
    portfolio = broker.repo.get_or_create_portfolio(broker.portfolio_id)
    positions = broker.get_realtime_portfolio().open_positions
    assert len(positions) == 0
    assert portfolio['current_equity'] > initial_equity
    
def test_execute_exit_no_positions(broker):
    from datetime import datetime, timezone
    success = broker.execute_exit("invalid_id", 1500.0, datetime.now(timezone.utc))
    assert success is False

def test_execute_exit_short(broker, base_decision):
    base_decision.decision = "SHORT"
    base_decision.evaluated_price = 100.0
    broker.execute_decision(base_decision, position_size=1.0)
    
    pos_id = broker.repo.get_open_positions(broker.portfolio_id)[0]['position_id']
    
    from datetime import datetime, timezone, timedelta
    exit_ts = base_decision.timestamp + timedelta(hours=1)
    
    success = broker.execute_exit(pos_id, 90.0, exit_ts)
    assert success is True
    
    portfolio = broker.repo.get_or_create_portfolio(broker.portfolio_id)
    assert portfolio['current_equity'] > 10000.0

def test_execute_exit_invalid_price(broker, base_decision):
    base_decision.decision = "LONG"
    base_decision.evaluated_price = 100.0
    broker.execute_decision(base_decision, position_size=1.0)
    
    pos_id = broker.repo.get_open_positions(broker.portfolio_id)[0]['position_id']
    from datetime import datetime, timezone, timedelta
    exit_ts = base_decision.timestamp + timedelta(hours=1)
    
    success = broker.execute_exit(pos_id, -10.0, exit_ts)
    assert success is False
    assert len(broker.get_realtime_portfolio().open_positions) == 1

def test_execute_exit_duplicate_idempotency(broker, base_decision):
    base_decision.decision = "LONG"
    base_decision.evaluated_price = 100.0
    broker.execute_decision(base_decision, position_size=1.0)
    
    pos_id = broker.repo.get_open_positions(broker.portfolio_id)[0]['position_id']
    from datetime import datetime, timezone, timedelta
    exit_ts = base_decision.timestamp + timedelta(hours=1)
    
    success1 = broker.execute_exit(pos_id, 110.0, exit_ts)
    assert success1 is True
    
    success2 = broker.execute_exit(pos_id, 110.0, exit_ts)
    assert success2 is False

def test_execute_exit_wrong_symbol(broker, base_decision):
    # Replaced by missing pos_id test above, this is basically testing non-existent ID
    from datetime import datetime, timezone, timedelta
    exit_ts = base_decision.timestamp + timedelta(hours=1)
    success = broker.execute_exit("random_id", 110.0, exit_ts)
    assert success is False
