import pytest
import sqlite3
import os
import tempfile
from datetime import datetime, timezone
import pandas as pd

from app.core.models import MarketBar
from app.analysis.regime import detect_market_regime
from app.database.schema import SCHEMA_SQL, init_db
from app.execution.paper_repository import PaperRepository
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from unittest.mock import Mock

@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix='.sqlite')
    conn = sqlite3.connect(path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()
    yield path
    os.close(fd)
    os.remove(path)

def generate_bars(count, base_price=100.0, vol_scale=0.01):
    import numpy as np
    np.random.seed(42)
    bars = []
    price = base_price
    for i in range(count):
        change = np.random.normal(0, vol_scale)
        price = price * (1 + change)
        bars.append(MarketBar(
            symbol="BTC_USDT",
            timestamp=datetime(2020, 1, 1, tzinfo=timezone.utc),
            open=price, high=price, low=price, close=price, volume=100.0
        ))
    return bars

def test_dynamic_threshold_warmup():
    bars = generate_bars(50) # Less than 90
    res = detect_market_regime(bars)
    assert res.regime == "INSUFFICIENT_DATA"

def test_dynamic_threshold_calculation():
    # 120 bars normal vol
    bars = generate_bars(120, vol_scale=0.01)
    res = detect_market_regime(bars)
    assert res.regime != "INSUFFICIENT_DATA"
    
    # Add a huge spike at the end
    bars.append(MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=100.0, high=150.0, low=90.0, close=150.0, volume=100.0))
    res2 = detect_market_regime(bars)
    assert res2.regime == "HIGH_VOLATILITY"

def test_orchestrator_receives_real_detector(temp_db):
    repo = PaperRepository(db_path=temp_db)
    limits = PortfolioRiskLimits(initial_equity=100000.0)
    risk = RiskEngine(limits, 0.02)
    ens = StrategyEnsemble([]) # No strategies
    
    # Use None for services to avoid mock validation errors
    orch = DecisionOrchestrator(ens, risk, Mock(generate_intelligence=Mock(return_value=None)), Mock(generate_forecast=Mock(return_value=None)), repo)
    
    bars = generate_bars(50)
    decision = orch.evaluate("BTC_USDT", bars, 100000.0, 0, 0.0)
    assert decision.regime == "INSUFFICIENT_DATA" # Replaced hardcoded logic!

def test_regime_persistence(temp_db):
    repo = PaperRepository(db_path=temp_db)
    repo.get_or_create_portfolio("default_paper", 100000.0)
    
    repo.execute_order(
        portfolio_id="default_paper", decision_id="dec123", symbol="BTC", direction="LONG",
        quantity=1.0, price=50.0, actual_price=51.0, commission=1.0, slippage=1.0,
        timestamp=datetime.now(timezone.utc), regime="TRENDING_UP"
    )
    
    orders = repo.get_recent_orders("default_paper")
    assert orders[0]["regime"] == "TRENDING_UP"
    
    positions = repo.get_open_positions("default_paper")
    assert positions[0]["regime"] == "TRENDING_UP"
    
    repo.execute_exit(
        portfolio_id="default_paper", position_id=positions[0]["position_id"], 
        exit_price=60.0, actual_price=59.0, commission=1.0, slippage=1.0, 
        timestamp=datetime.now(timezone.utc), regime="TRENDING_DOWN"
    )
    closed = repo.get_closed_positions("default_paper")
    assert closed[0]["regime"] == "TRENDING_DOWN"

def test_legacy_database_backward_compatibility(temp_db):
    conn = sqlite3.connect(temp_db)
    for table in ['paper_orders', 'paper_positions', 'paper_closed_positions']:
        conn.execute(f"ALTER TABLE {table} DROP COLUMN regime")
    conn.commit()
    conn.close()
    
    from app.config import config
    config.DB_PATH = temp_db
    config.ENABLE_PERSISTENCE = True
    init_db() # Should add the columns back
    
    repo = PaperRepository(db_path=temp_db)
    repo.get_or_create_portfolio("default", 100.0)
    repo.record_rejected_trade("default", "dec1", "BTC", "LONG", "test", datetime.now(timezone.utc), regime="HIGH_VOLATILITY")
    assert repo.get_recent_orders("default")[0]["regime"] == "HIGH_VOLATILITY"
