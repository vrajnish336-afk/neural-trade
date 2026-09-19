import pytest
import sqlite3
import uuid
import json
from datetime import datetime, timezone, timedelta
from app.database.schema import init_db
from app.config import config
from app.research.forward_validation_models import (
    FrozenSpecification, ForwardValidationRun, ForwardValidationState, ForwardDriftState
)
from app.research.forward_validation_service import ForwardValidationService
from app.core.models import MarketBar
from app.backtesting.models import BacktestResult

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_forward.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    yield

def test_frozen_specification_hash():
    # 2. frozen specification determinism
    # 3. timestamps excluded from identity
    spec1 = FrozenSpecification(
        strategy="Trend",
        symbols=["BTC", "ETH"],
        timeframe="1d",
        historical_end=datetime(2025, 1, 1, tzinfo=timezone.utc),
        configuration="default",
        random_seed=42
    )
    
    spec2 = FrozenSpecification(
        strategy="Trend",
        symbols=["ETH", "BTC"], # Reverse order
        timeframe="1d",
        historical_end=datetime(2025, 1, 1, tzinfo=timezone.utc),
        configuration="default",
        random_seed=42
    )
    
    assert spec1.get_hash() == spec2.get_hash()
    
def test_forward_run_creation_and_duplicate_prevention():
    service = ForwardValidationService()
    spec = FrozenSpecification(
        strategy="Trend",
        symbols=["BTC"],
        timeframe="1d",
        historical_end=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    
    run1 = service.create_validation_request("ident_1", "exp_1", spec)
    assert run1 is not None
    assert run1.state == ForwardValidationState.CREATED
    
    # 17. duplicate validation prevention
    run2 = service.create_validation_request("ident_1", "exp_1", spec)
    assert run2 is None # Should be blocked

def test_insufficient_forward_data_rejection(monkeypatch):
    service = ForwardValidationService()
    spec = FrozenSpecification(
        strategy="TrendFollowing",
        symbols=["BTC/USD"],
        timeframe="1d",
        historical_end=datetime(2025, 1, 1, tzinfo=timezone.utc)
    )
    
    run = service.create_validation_request("ident_1", "exp_1", spec)
    
    # Mock data provider to return only old data (no forward data)
    class DummyProvider:
        def __init__(self, *args, **kwargs): pass
        def get_historical_bars(self, sym, tf, start):
            # 4. chronological boundary validation
            # Return old bars strictly BEFORE start
            return [
                MarketBar(symbol="BTC/USD", timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1),
                MarketBar(symbol="BTC/USD", timestamp=datetime(2024, 1, 2, tzinfo=timezone.utc), open=1, high=1, low=1, close=1, volume=1)
            ]
            
    monkeypatch.setattr("app.research.forward_validation_service.CsvHistoricalDataProvider", DummyProvider)
    
    service.execute_validation(run)
    
    assert run.state == ForwardValidationState.INSUFFICIENT_DATA
    assert "No forward data available" in run.failure_reason

def test_drift_analyzer():
    from app.research.drift_analyzer import PerformanceDriftAnalyzer
    
    hist = BacktestResult(
        initial_capital=10000,
        final_equity=12000,
        total_return_pct=20,
        number_of_trades=50,
        winning_trades=30,
        losing_trades=20,
        win_rate=60.0,
        gross_profit=3000,
        gross_loss=1000,
        net_profit=2000,
        max_drawdown_pct=5.0,
        average_trade_result=40.0,
        profit_factor=3.0,
        average_holding_period_hours=24,
        trades=[],
        telemetry_snapshot={}
    )
    
    # Case 1: Stable
    fwd_stable = BacktestResult(
        initial_capital=10000, final_equity=11000, total_return_pct=10,
        number_of_trades=20, winning_trades=11, losing_trades=9,
        win_rate=55.0, # Slight drop
        gross_profit=1500, gross_loss=500, net_profit=1000,
        max_drawdown_pct=6.0, average_trade_result=50.0, profit_factor=3.0,
        average_holding_period_hours=24, trades=[], telemetry_snapshot={}
    )
    assert PerformanceDriftAnalyzer.analyze(hist, fwd_stable) == ForwardDriftState.STABLE
    
    # Case 2: Degraded (Win rate dropped > 15%)
    fwd_deg = BacktestResult(
        initial_capital=10000, final_equity=11000, total_return_pct=10,
        number_of_trades=20, winning_trades=8, losing_trades=12,
        win_rate=40.0, # Dropped by 20%
        gross_profit=1500, gross_loss=500, net_profit=1000,
        max_drawdown_pct=6.0, average_trade_result=50.0, profit_factor=3.0,
        average_holding_period_hours=24, trades=[], telemetry_snapshot={}
    )
    assert PerformanceDriftAnalyzer.analyze(hist, fwd_deg) == ForwardDriftState.DEGRADED
    
    # Case 3: Significantly Degraded (PF dropped > 50%)
    fwd_sig = BacktestResult(
        initial_capital=10000, final_equity=11000, total_return_pct=10,
        number_of_trades=20, winning_trades=10, losing_trades=10,
        win_rate=50.0,
        gross_profit=1000, gross_loss=1000, net_profit=0,
        max_drawdown_pct=6.0, average_trade_result=0.0, profit_factor=1.0, # PF dropped from 3 to 1
        average_holding_period_hours=24, trades=[], telemetry_snapshot={}
    )
    assert PerformanceDriftAnalyzer.analyze(hist, fwd_sig) == ForwardDriftState.SIGNIFICANTLY_DEGRADED
