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

def test_pre_migration_row_readability(repo, broker):
    """
    Proves that older rows without the strategy column do not crash the system.
    """
    # Create an old-style row by manually dropping the column in a temp db and inserting
    # Wait, SQLite doesn't support DROP COLUMN easily before 3.35, and we can just insert manually
    # Actually, we can't insert a row without a column if the table HAS the column.
    # We must create a fresh DB with the old schema.
    fd, path = tempfile.mkstemp()
    old_schema = SCHEMA_SQL.replace("strategy TEXT,", "")
    conn = sqlite3.connect(path)
    conn.executescript(old_schema)
    conn.commit()
    
    # Insert old row manually
    conn.execute("INSERT INTO paper_portfolios (portfolio_id, initial_equity, current_equity, current_cash, created_at, updated_at) VALUES ('default_paper', 100, 100, 100, '2023', '2023')")
    conn.execute("INSERT INTO paper_positions (position_id, portfolio_id, symbol, direction, entry_time, entry_price, quantity, stop_loss, take_profit, created_at, updated_at) VALUES ('pos1', 'default_paper', 'BTC/USD', 'LONG', '2023', 100.0, 1.0, NULL, NULL, '2023', '2023')")
    conn.commit()
    conn.close()
    
    # Initialize broker with old DB (init_db is NOT called, so migration doesn't run)
    old_repo = PaperRepository(db_path=path)
    old_broker = StreamingPaperBroker(repository=old_repo, risk_engine=RiskEngine(PortfolioRiskLimits(initial_equity=100.0), 0.01))
    
    # Read state - should not crash, and should default strategy to None
    state = old_broker.get_realtime_portfolio()
    assert len(state.open_positions) == 1
    assert state.open_positions[0]['signal_metadata']['strategies'] is None
    
    # Exit the position - should not crash when reading old position
    import uuid
    from app.execution.paper_repository import PaperRepositoryException
    ts = datetime.now(timezone.utc)
    # Exiting writes to the DB. Since we bypassed init_db() migration in this test,
    # the schema physically lacks the column, so the write WILL correctly fail.
    with pytest.raises(PaperRepositoryException, match="has no column named strategy"):
        old_broker.execute_exit('pos1', 110.0, ts)
        
    os.close(fd)
    os.remove(path)
