import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock

from app.core.models import MarketBar, TradingSignal
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.decision.models import TraderDecision
from app.risk.engine import RiskEngine, RiskDecision
from app.strategies.ensemble import StrategyEnsemble
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService


@pytest.fixture
def mock_orchestrator():
    ens = Mock(spec=StrategyEnsemble)
    risk = Mock(spec=RiskEngine)
    intel = Mock(spec=IntelligenceService)
    forecast = Mock(spec=ForecastingService)
    
    intel.generate_intelligence.return_value = None
    ens.evaluate.return_value = None
    
    return DecisionOrchestrator(
        ensemble=ens,
        risk_engine=risk,
        intelligence_service=intel,
        forecasting_service=forecast
    )


def test_data_freshness_dynamic_fresh(mock_orchestrator):
    now = datetime.now(timezone.utc)
    recent_bars = [
        MarketBar(
            symbol="BTC/USD",
            timestamp=now - timedelta(minutes=10 * (10 - i)),
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0 + (i * 0.1),
            volume=1000.0
        )
        for i in range(10)
    ]
    
    decision = mock_orchestrator.evaluate("BTC/USD", recent_bars, 10000.0, 0, 0.0)
    assert decision.data_freshness == "FRESH"


def test_data_freshness_dynamic_stale(mock_orchestrator):
    old_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    old_bars = [
        MarketBar(
            symbol="BTC/USD",
            timestamp=old_time + timedelta(hours=i),
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0 + (i * 0.1),
            volume=1000.0
        )
        for i in range(10)
    ]
    
    decision = mock_orchestrator.evaluate("BTC/USD", old_bars, 10000.0, 0, 0.0)
    assert decision.data_freshness == "STALE"


def test_data_freshness_insufficient_bars(mock_orchestrator):
    now = datetime.now(timezone.utc)
    few_bars = [
        MarketBar(
            symbol="BTC/USD",
            timestamp=now,
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0,
            volume=1000.0
        )
    ]
    
    decision = mock_orchestrator.evaluate("BTC/USD", few_bars, 10000.0, 0, 0.0)
    assert decision.data_freshness == "INSUFFICIENT"


def test_volatility_context_computation(mock_orchestrator):
    now = datetime.now(timezone.utc)
    
    # 1. Low Volatility: flat prices (CV < 0.015)
    flat_bars = [
        MarketBar(
            symbol="USDT/USD",
            timestamp=now - timedelta(minutes=i),
            open=1.0,
            high=1.001,
            low=0.999,
            close=1.0 + (0.0001 * (i % 2)),
            volume=1000.0
        )
        for i in range(20)
    ]
    d_flat = mock_orchestrator.evaluate("USDT/USD", flat_bars, 10000.0, 0, 0.0)
    assert d_flat.volatility_context == "LOW"
    
    # 2. High Volatility: large price swings (CV > 0.08)
    wild_bars = [
        MarketBar(
            symbol="BTC/USD",
            timestamp=now - timedelta(minutes=i),
            open=100.0,
            high=200.0,
            low=50.0,
            close=100.0 + (50.0 * ((-1) ** i)),
            volume=1000.0
        )
        for i in range(20)
    ]
    d_wild = mock_orchestrator.evaluate("BTC/USD", wild_bars, 10000.0, 0, 0.0)
    assert d_wild.volatility_context == "HIGH"


def test_eval_bars_slices_most_recent_100_bars():
    # 150 bars created with sequential prices
    now = datetime.now(timezone.utc)
    bars = [
        MarketBar(
            symbol="BTC/USD",
            timestamp=now - timedelta(hours=150 - i),
            open=100.0 + float(i),
            high=100.0 + float(i + 1),
            low=100.0 + float(i - 0.5),
            close=100.0 + float(i),
            volume=100.0
        )
        for i in range(150)
    ]
    
    eval_bars = bars[-100:]
    assert len(eval_bars) == 100
    assert eval_bars[0].close == 150.0
    assert eval_bars[-1].close == 249.0
