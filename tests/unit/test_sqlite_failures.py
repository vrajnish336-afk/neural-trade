import pytest
import sqlite3
import os
import tempfile
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.execution.paper_repository import PaperRepository, PaperRepositoryException
from app.database.schema import SCHEMA_SQL

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
    r.get_or_create_portfolio("default_paper", 10000.0)
    return r

def test_db_constraint_idempotency(repo):
    """
    Test duplicate decision IDs at the database constraint level.
    We bypass the application-level SELECT check to force a database-level UNIQUE constraint collision.
    """
    ts = datetime(2023, 1, 1, tzinfo=timezone.utc)
    decision_id = repo.generate_decision_id("BTC/USD", ts)
    
    # First execution succeeds
    success1 = repo.execute_order(
        portfolio_id="default_paper",
        decision_id=decision_id,
        symbol="BTC/USD",
        direction="LONG",
        quantity=1.0,
        price=100.0,
        actual_price=100.0,
        commission=1.0,
        slippage=0.0,
        timestamp=ts
    )
    assert success1 is True
    
    # Simulate a race condition: directly attempt to INSERT the duplicate decision_id
    # bypassing the repo's SELECT check.
    conn = repo._get_conn()
    with conn:
        cursor = conn.cursor()
        with pytest.raises(sqlite3.IntegrityError):
            # This must fail due to the UNIQUE constraint on decision_id
            cursor.execute(
                """
                INSERT INTO paper_orders (
                    order_id, portfolio_id, decision_id, symbol, direction, 
                    quantity, price, timestamp, status, commission, slippage, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("some_new_order_id", "default_paper", decision_id, "BTC/USD", "LONG", 1.0, 
                 100.0, ts.isoformat(), "FILLED", 1.0, 0.0, datetime.now(timezone.utc).isoformat())
            )
            
    # Verify no duplicate was created
    orders = repo.get_recent_orders("default_paper", 10)
    assert len(orders) == 1
    
    # Close connection to avoid Windows tempfile permission leak
    conn.close()

def test_operational_error_rollback(repo, temp_db):
    """
    Test SQLite OperationalError / database-lock behavior using an exclusive lock.
    Verifies that a failed transaction cleanly rolls back and leaves no partial state.
    """
    ts = datetime(2023, 1, 1, tzinfo=timezone.utc)
    decision_id = repo.generate_decision_id("ETH/USD", ts)
    
    # 1. Capture initial state
    initial_port = repo.get_or_create_portfolio("default_paper")
    initial_equity = initial_port['current_equity']
    
    assert len(repo.get_open_positions("default_paper")) == 0
    assert len(repo.get_recent_orders("default_paper", 10)) == 0
    
    # 2. Acquire EXCLUSIVE lock on a separate connection
    conn2 = sqlite3.connect(temp_db, timeout=0.1)
    conn2.execute("BEGIN EXCLUSIVE TRANSACTION")
    
    # 3. Try to execute order in repo (which uses its own connection)
    # Patch connect to use a short timeout so we don't wait forever
    original_connect = sqlite3.connect
    def mock_connect(db_path, **kwargs):
        kwargs['timeout'] = 0.1
        return original_connect(db_path, **kwargs)
        
    with patch("sqlite3.connect", new=mock_connect):
        # With the fix, the initial SELECT is covered by the try block, 
        # so it correctly wraps OperationalError into PaperRepositoryException
        with pytest.raises(PaperRepositoryException, match="Failed to execute order"):
            repo.execute_order(
                portfolio_id="default_paper",
                decision_id=decision_id,
                symbol="ETH/USD",
                direction="LONG",
                quantity=1.0,
                price=100.0,
                actual_price=100.0,
                commission=1.0,
                slippage=0.0,
                timestamp=ts
            )
            
    # 4. Release lock
    conn2.rollback()
    conn2.close()
    
    # 5. Verify Rollback (No partial writes)
    port_after = repo.get_or_create_portfolio("default_paper")
    assert port_after['current_equity'] == initial_equity, "Equity should be untouched"
    
    assert len(repo.get_open_positions("default_paper")) == 0, "No position should be created"
    assert len(repo.get_recent_orders("default_paper", 10)) == 0, "No order should be recorded"
    
    snapshots = repo.get_equity_snapshots("default_paper")
    assert len(snapshots) == 1, "Only the initial snapshot should exist"
