import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone
from unittest.mock import Mock

from app.execution.paper_repository import PaperRepository
from app.database.schema import SCHEMA_SQL, init_db

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

def test_record_rejected_trade_persistence(temp_db):
    repo = PaperRepository(db_path=temp_db)
    repo.get_or_create_portfolio("default", 100.0)
    
    # Record a rejection
    repo.record_rejected_trade("default", "dec123", "BTC", "LONG", "Risk Limit", datetime.now(timezone.utc), "StrategyA")
    
    orders = repo.get_recent_orders("default")
    assert len(orders) == 1
    
    o = orders[0]
    assert o["status"] == "REJECTED"
    assert o["reason"] == "Risk Limit"
    assert o["symbol"] == "BTC"

def test_unrealized_pnl_snapshot_and_backward_compatibility(temp_db):
    # Test that unrealized_pnl is persisted in snapshot
    repo = PaperRepository(db_path=temp_db)
    repo.get_or_create_portfolio("default", 100.0)
    
    repo.execute_order(
        portfolio_id="default", decision_id="dec123", symbol="BTC", direction="LONG",
        quantity=1.0, price=50.0, actual_price=51.0, commission=1.0, slippage=1.0,
        timestamp=datetime.now(timezone.utc), unrealized_pnl=5.5
    )
    
    snapshots = repo.get_equity_snapshots("default")
    assert len(snapshots) == 2 # 1 initial, 1 after order
    last_snap = snapshots[-1]
    
    # Check current_equity meaning hasn't changed
    assert last_snap["current_equity"] == 99.0 # 100 - 1.0 commission
    
    # Check new unrealized_pnl field
    assert "unrealized_pnl" in last_snap.keys()
    assert last_snap["unrealized_pnl"] == 5.5

def test_backward_compatibility_old_db(temp_db):
    # Simulate old DB without reason and unrealized_pnl
    conn = sqlite3.connect(temp_db)
    conn.execute("ALTER TABLE paper_orders DROP COLUMN reason")
    conn.execute("ALTER TABLE paper_equity_snapshots DROP COLUMN unrealized_pnl")
    conn.commit()
    conn.close()
    
    # init_db should add them back safely
    from app.config import config
    config.DB_PATH = temp_db
    config.ENABLE_PERSISTENCE = True
    init_db()
    
    # Verify we can record rejected trade now
    repo = PaperRepository(db_path=temp_db)
    repo.get_or_create_portfolio("default", 100.0)
    repo.record_rejected_trade("default", "dec123", "BTC", "LONG", "Risk Limit", datetime.now(timezone.utc), "StrategyA")
    
    orders = repo.get_recent_orders("default")
    assert orders[0]["reason"] == "Risk Limit"
