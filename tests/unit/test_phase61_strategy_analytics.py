import pytest
import sqlite3
import tempfile
from app.config import config
from datetime import datetime, timezone
from app.execution.paper_repository import PaperRepository
from app.database.schema import init_db

def test_paper_orders_strategy_migration():
    fd, path = tempfile.mkstemp()
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    # 1. Create OLD schema (without strategy)
    conn = sqlite3.connect(path)
    conn.execute("""
    CREATE TABLE paper_portfolios (
        portfolio_id TEXT PRIMARY KEY,
        current_equity REAL,
        current_cash REAL,
        created_at TEXT
    )
    """)
    conn.execute("""
    CREATE TABLE paper_orders (
        order_id TEXT PRIMARY KEY,
        portfolio_id TEXT NOT NULL,
        decision_id TEXT UNIQUE NOT NULL,
        symbol TEXT NOT NULL,
        direction TEXT NOT NULL,
        quantity REAL NOT NULL,
        price REAL NOT NULL,
        timestamp TEXT NOT NULL,
        status TEXT NOT NULL,
        commission REAL,
        slippage REAL,
        created_at TEXT NOT NULL,
        reason TEXT,
        regime TEXT,
        FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
    )
    """)
    conn.execute("""
    INSERT INTO paper_orders (
        order_id, portfolio_id, decision_id, symbol, direction, quantity, price, timestamp, status, commission, slippage, created_at
    ) VALUES ('ord1', 'port1', 'dec1', 'BTC', 'LONG', 1.0, 50000, '2022-01-01T00:00:00Z', 'FILLED', 0, 0, '2022-01-01T00:00:00Z')
    """)
    conn.commit()
    conn.close()
    
    # 2. Run migration via init_db
    init_db()
    
    # 3. Check migration backward compatibility
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM paper_orders WHERE order_id='ord1'").fetchone()
    assert row['strategy'] == 'Unavailable'
    conn.close()

def test_paper_orders_strategy_persistence():
    fd, path = tempfile.mkstemp()
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    init_db()
    repo = PaperRepository(db_path=path)
    repo.get_or_create_portfolio('port1')
    
    now = datetime.now(timezone.utc)
    # Order execution with strategy
    repo.execute_order(
        portfolio_id='port1',
        decision_id='dec2',
        symbol='ETH',
        direction='LONG',
        quantity=2.0,
        price=3000.0,
        actual_price=3000.0,
        commission=1.0,
        slippage=0.0,
        timestamp=now,
        regime='TRENDING',
        strategy='Momentum'
    )
    
    orders = repo.get_recent_orders('port1', limit=10)
    assert len(orders) == 1
    assert orders[0]['strategy'] == 'Momentum'

def test_paper_orders_rejected_strategy_persistence():
    fd, path = tempfile.mkstemp()
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    init_db()
    repo = PaperRepository(db_path=path)
    repo.get_or_create_portfolio('port1')
    
    now = datetime.now(timezone.utc)
    # Rejected trade with strategy
    repo.record_rejected_trade(
        portfolio_id='port1',
        decision_id='dec3',
        symbol='SOL',
        direction='LONG',
        reason='Risk Gate',
        timestamp=now,
        strategy='MeanReversion',
        regime='RANGE'
    )
    
    orders = repo.get_recent_orders('port1', limit=10)
    assert len(orders) == 1
    assert orders[0]['strategy'] == 'MeanReversion'

def test_paper_orders_exit_strategy_persistence():
    fd, path = tempfile.mkstemp()
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    init_db()
    repo = PaperRepository(db_path=path)
    repo.get_or_create_portfolio('port1')
    
    now = datetime.now(timezone.utc)
    repo.execute_order(
        portfolio_id='port1',
        decision_id='dec4',
        symbol='ADA',
        direction='LONG',
        quantity=10.0,
        price=1.0,
        actual_price=1.0,
        commission=0.0,
        slippage=0.0,
        timestamp=now,
        regime='REG',
        strategy='StratA'
    )
    
    pos = repo.get_open_positions('port1')
    assert len(pos) == 1
    
    repo.execute_exit(
        portfolio_id='port1',
        position_id=pos[0]['position_id'],
        exit_price=1.1,
        actual_price=1.1,
        commission=0.0,
        slippage=0.0,
        timestamp=now,
        regime='REG'
    )
    
    orders = repo.get_recent_orders('port1', limit=10)
    assert len(orders) == 2
    # The exit order should inherit the strategy from the position
    exit_order = [o for o in orders if o['direction'] == 'CLOSE_LONG'][0]
    assert exit_order['strategy'] == 'StratA'
