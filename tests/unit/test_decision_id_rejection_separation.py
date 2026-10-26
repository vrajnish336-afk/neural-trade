import pytest
import sqlite3
import tempfile
import os
from datetime import datetime, timezone

from app.execution.paper_repository import PaperRepository
from app.database.schema import SCHEMA_SQL, init_db
from app.config import config


@pytest.fixture
def repo_with_db():
    fd, path = tempfile.mkstemp()
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    init_db()
    repo = PaperRepository(db_path=path)
    repo.get_or_create_portfolio("test_port", 10000.0)
    yield repo, path
    os.close(fd)
    if os.path.exists(path):
        os.remove(path)


def test_generate_decision_id_payload_variation(repo_with_db):
    repo, _ = repo_with_db
    ts = datetime(2026, 10, 26, 12, 0, 0, tzinfo=timezone.utc)
    
    # Same symbol & timestamp, but different decision or strategy
    id_base = repo.generate_decision_id("BTC/USD", ts)
    id_wait = repo.generate_decision_id("BTC/USD", ts, decision="WAIT", strategy_name="Breakout")
    id_buy = repo.generate_decision_id("BTC/USD", ts, decision="BUY", strategy_name="Breakout")
    id_diff_strategy = repo.generate_decision_id("BTC/USD", ts, decision="BUY", strategy_name="TrendFollowing")
    
    # All must be distinct SHA256 hashes
    hashes = {id_base, id_wait, id_buy, id_diff_strategy}
    assert len(hashes) == 4
    for h in hashes:
        assert len(h) == 64


def test_rejected_order_separation_and_no_collision(repo_with_db):
    repo, _ = repo_with_db
    portfolio_id = "test_port"
    symbol = "ETH/USD"
    ts = datetime(2026, 10, 26, 14, 30, 0, tzinfo=timezone.utc)
    
    # 1. Generate decision ID for a rejected/wait action
    wait_decision_id = repo.generate_decision_id(symbol, ts, decision="WAIT", strategy_name="MeanReversion")
    
    # 2. Record rejected trade
    repo.record_rejected_trade(
        portfolio_id=portfolio_id,
        decision_id=wait_decision_id,
        symbol=symbol,
        decision="WAIT",
        reason="Market in consolidation",
        timestamp=ts,
        strategy="MeanReversion",
        regime="RANGE"
    )
    
    # Verify rejection went exclusively into rejected_paper_orders
    rejected_orders = repo.get_rejected_orders(portfolio_id)
    assert len(rejected_orders) == 1
    assert rejected_orders[0]["decision_id"] == wait_decision_id
    assert rejected_orders[0]["symbol"] == symbol
    assert rejected_orders[0]["decision"] == "WAIT"
    assert rejected_orders[0]["reason"] == "Market in consolidation"
    assert rejected_orders[0]["strategy"] == "MeanReversion"
    assert rejected_orders[0]["regime"] == "RANGE"
    
    # Verify paper_orders table has 0 orders (no pollution)
    orders = repo.get_recent_orders(portfolio_id)
    assert len(orders) == 0
    
    # 3. Now execute a genuine order for that same symbol and timestamp
    buy_decision_id = repo.generate_decision_id(symbol, ts, decision="BUY", strategy_name="MeanReversion")
    assert buy_decision_id != wait_decision_id
    
    executed = repo.execute_order(
        portfolio_id=portfolio_id,
        decision_id=buy_decision_id,
        symbol=symbol,
        direction="LONG",
        quantity=2.0,
        price=2000.0,
        actual_price=2000.0,
        commission=2.0,
        slippage=0.0,
        timestamp=ts,
        stop_loss=1950.0,
        take_profit=2150.0,
        strategy="MeanReversion",
        regime="RANGE"
    )
    
    # Must execute successfully without collision!
    assert executed is True
    
    # Now paper_orders has exactly 1 order
    orders = repo.get_recent_orders(portfolio_id)
    assert len(orders) == 1
    assert orders[0]["decision_id"] == buy_decision_id
    assert orders[0]["status"] == "FILLED"
    
    # Rejections table still has 1 rejected order
    rejected_orders = repo.get_rejected_orders(portfolio_id)
    assert len(rejected_orders) == 1
