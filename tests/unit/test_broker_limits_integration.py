import pytest
import sqlite3
import os
import tempfile
import copy
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

from app.decision.models import TraderDecision, ScenarioAnalysis
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.execution.paper_repository import PaperRepository
from app.database.schema import SCHEMA_SQL
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.portfolio import PortfolioRiskManager, PortfolioRiskConfig
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
    os.remove(path)

@pytest.fixture
def repo(temp_db):
    r = PaperRepository(db_path=temp_db)
    r.get_or_create_portfolio("default_paper", initial_equity=100000.0)
    return r

@pytest.fixture
def broker(repo):
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=100000.0), 0.01)
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
        strategy_signals=[{"strategy": "MACD", "direction": "LONG"}],
        forecast_direction="UP",
        forecast_uncertainty=0.5,
        world_context="POSITIVE",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="B", bearish_scenario="B", neutral_scenario="N"),
        main_risks=[],
        invalidation_conditions=[],
        rationale="Test Limit",
        confidence=0.9,
        decision="LONG",
        evaluated_price=100.0,
        risk_gate_approved=True,
        paper_execution_eligible=True
    )

def test_max_strategy_exposure_limit_rejection(broker, base_decision):
    """
    Proves the actual strategy is used and max_strategy_exposure_pct rejection works at broker level
    for a single order that breaches the limit.
    """
    original_init = PortfolioRiskManager.__init__
    
    def mock_init(self, config):
        config.max_strategy_exposure_pct = 0.5  # 50% max strategy exposure
        original_init(self, config)
        
    with patch.object(PortfolioRiskManager, '__init__', new=mock_init):
        # We start with 100k equity. 50% is 50k.
        # Position size 501 at $100 = 50,100, which exceeds 50%.
        success = broker.execute_decision(base_decision, position_size=501.0)
        
        # It should be rejected by the broker!
        assert success is False
        
        # Verify no mutations occurred
        state = broker.get_realtime_portfolio()
        assert len(state.open_positions) == 0

def test_max_concurrent_positions_rejection(broker, base_decision):
    """
    Proves max_concurrent_positions rejection works at broker level.
    """
    original_init = PortfolioRiskManager.__init__
    
    def mock_init(self, config):
        config.max_concurrent_positions = 1
        original_init(self, config)
        
    with patch.object(PortfolioRiskManager, '__init__', new=mock_init):
        # First execution should succeed
        success1 = broker.execute_decision(base_decision, position_size=1.0)
        assert success1 is True
        
        # Second execution for a different symbol should be rejected due to max positions
        decision2 = copy.deepcopy(base_decision)
        decision2.symbol = "ETH/USD"
        
        success2 = broker.execute_decision(decision2, position_size=1.0)
        assert success2 is False
        
        # Verify only 1 position exists
        state = broker.get_realtime_portfolio()
        assert len(state.open_positions) == 1
        assert state.open_positions[0]['symbol'] == "BTC/USD"

def test_accepted_decision_executes_normally(broker, base_decision):
    """
    Proves that a normal decision beneath limits executes successfully.
    """
    # Size 10 at $100 = $1,000, well below 100k limits
    success = broker.execute_decision(base_decision, position_size=10.0)
    assert success is True
    
    state = broker.get_realtime_portfolio()
    assert len(state.open_positions) == 1
    assert state.open_positions[0]['quantity'] == 10.0

def test_strategy_exposure_accumulation(broker, base_decision):
    """
    Proves that strategy positions are correctly accumulated across multiple trades.
    """
    original_init = PortfolioRiskManager.__init__
    
    def mock_init(self, config):
        config.max_strategy_exposure_pct = 0.5  # 50% max
        config.max_concurrent_positions = 10
        config.max_symbol_exposure_pct = 1.0
        original_init(self, config)
        
    with patch.object(PortfolioRiskManager, '__init__', new=mock_init):
        # 1. Open 40% exposure (40k). This succeeds.
        decision1 = copy.deepcopy(base_decision)
        decision1.timestamp += timedelta(minutes=1)
        success1 = broker.execute_decision(decision1, position_size=400.0)
        assert success1 is True
        
        # 2. Open another 40% exposure (40k). 
        # Total strategy exposure should be 80%, exceeding the 50% limit.
        decision2 = copy.deepcopy(base_decision)
        decision2.timestamp += timedelta(minutes=2)
        success2 = broker.execute_decision(decision2, position_size=400.0)
        
        # It should now be rejected because the first position's strategy was persisted and reloaded!
        assert success2 is False
        
        # Verify no second position was created
        state = broker.get_realtime_portfolio()
        assert len(state.open_positions) == 1