import pytest
from datetime import datetime, timezone
from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.models import CostConfig
from app.decision.models import TraderDecision

def test_broker_uses_injected_risk_engine(tmp_path):
    db_path = str(tmp_path / "test.db")
    import sqlite3
    repo = PaperRepository(db_path=db_path)
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
        CREATE TABLE IF NOT EXISTS paper_rejected_trades (
            id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            decision_id TEXT,
            symbol TEXT,
            decision TEXT,
            reason TEXT,
            timestamp TEXT,
            strategy TEXT,
            regime TEXT,
            created_at TEXT
        );
        ''')
    
    # Configure an authoritative risk engine with very strict limits so it fails
    limits = PortfolioRiskLimits(10000, max_positions=0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    broker = StreamingPaperBroker(repo, risk_engine, CostConfig(), "test_port")
    
    from app.decision.models import ScenarioAnalysis
    decision = TraderDecision(
        symbol="BTC",
        decision="LONG",
        confidence=0.9,
        evaluated_price=50000.0,
        rationale="test",
        timestamp=datetime.now(timezone.utc),
        risk_gate_approved=True,
        data_freshness="FRESH",
        regime="TRENDING_UP",
        trend_context="BULLISH",
        volatility_context="LOW",
        multi_timeframe_alignment="STRONG",
        strategy_signals=[{"strategy": "mock", "signal": "LONG"}],
        forecast_direction="LONG",
        forecast_uncertainty=0.1,
        world_context="NORMAL",
        scenario_analysis=ScenarioAnalysis(bullish_scenario="up", bearish_scenario="down", neutral_scenario="flat"),
        main_risks=["none"],
        invalidation_conditions=["none"],
        paper_execution_eligible=True
    )
    
    success = broker.execute_decision(decision, 1.0, 49000.0, 52000.0)
    assert not success, "Should be rejected by the authoritative risk engine limit (max_positions=0)"
    
    with repo._get_conn() as conn:
        rej = conn.execute("SELECT * FROM paper_orders WHERE status = 'REJECTED'").fetchone()
        assert rej is not None
        assert "RiskEngine" in rej['reason']
