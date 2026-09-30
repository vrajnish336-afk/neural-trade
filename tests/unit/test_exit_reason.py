import pytest
from datetime import datetime, timezone
import uuid
from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.models import CostConfig

def test_exit_reason_persisted(tmp_path):
    db_path = str(tmp_path / "test.db")
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        with open("app/database/schema.py", "r") as f:
            content = f.read()
            import ast
            for node in ast.parse(content).body:
                if isinstance(node, ast.Assign) and node.targets[0].id == "SCHEMA_SQL":
                    conn.executescript(node.value.value)
                    
    repo = PaperRepository(db_path=db_path)
    # Manual table creation for tests since they depend on app.database.schema initialization usually
    with repo._get_conn() as conn:
        conn.executescript('''
        CREATE TABLE IF NOT EXISTS paper_portfolios (
            portfolio_id TEXT PRIMARY KEY,
            initial_equity REAL NOT NULL,
            current_equity REAL NOT NULL,
            current_cash REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS paper_equity_snapshots (
            snapshot_id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            current_equity REAL NOT NULL,
            current_cash REAL NOT NULL,
            created_at TEXT NOT NULL,
            unrealized_pnl REAL DEFAULT 0.0,
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
        );
        CREATE TABLE IF NOT EXISTS paper_positions (
            position_id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            quantity REAL NOT NULL,
            stop_loss REAL,
            take_profit REAL,
            strategy TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            regime TEXT,
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
        );
        CREATE TABLE IF NOT EXISTS paper_orders (
            order_id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            decision_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            quantity REAL NOT NULL,
            price REAL NOT NULL,
            timestamp TEXT NOT NULL,
            status TEXT NOT NULL,
            commission REAL NOT NULL,
            slippage REAL NOT NULL,
            created_at TEXT NOT NULL,
            reason TEXT,
            regime TEXT,
            strategy TEXT,
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
        );
        CREATE TABLE IF NOT EXISTS paper_closed_positions (
            position_id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_time TEXT NOT NULL,
            exit_price REAL NOT NULL,
            quantity REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            exit_reason TEXT NOT NULL,
            strategy TEXT,
            regime TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(portfolio_id) REFERENCES paper_portfolios(portfolio_id)
        );
        ''')
    
    repo.get_or_create_portfolio("test_port")
    
    # insert a mock position
    pos_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    with repo._get_conn() as conn:
        conn.execute('''
        INSERT INTO paper_positions (position_id, portfolio_id, symbol, direction, entry_time, entry_price, quantity, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (pos_id, "test_port", "BTC", "LONG", now.isoformat(), 50000.0, 1.0, now.isoformat(), now.isoformat()))
        conn.commit()

    risk_engine = RiskEngine(PortfolioRiskLimits(10000))
    broker = StreamingPaperBroker(repo, risk_engine, CostConfig(), "test_port")
    
    success = broker.execute_exit(pos_id, 51000.0, now, reason="TP_HIT")
    assert success
    
    closed = repo.get_closed_positions("test_port")
    assert len(closed) == 1
    assert closed[0]['exit_reason'] == "TP_HIT"
