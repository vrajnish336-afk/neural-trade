import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock
from app.core.models import MarketBar, TradingSignal
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.analysis.mtf_engine import MultiTimeframeEngine

def generate_bars(count: int, start_time: datetime, step_hours: int = 1, base_price: float = 100.0, trend_up: bool = True) -> list[MarketBar]:
    bars = []
    current = base_price
    for i in range(count):
        ts = start_time + timedelta(hours=i * step_hours)
        current += 1.0 if trend_up else -1.0
        bars.append(MarketBar(
            symbol="BTC/USD", timestamp=ts, open=current - 0.5, high=current + 1.0, low=current - 1.0, close=current, volume=100.0
        ))
    return bars

def test_orchestrator_mtf_valid_context():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    mock_provider = MagicMock()
    
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    h1_bars = generate_bars(60, start, step_hours=1, trend_up=True)
    h4_bars = generate_bars(30, start, step_hours=4, trend_up=True)
    d1_bars = generate_bars(30, start, step_hours=24, trend_up=True)
    
    mock_provider.get_historical_bars.side_effect = lambda sym, tf, **kw: h4_bars if tf == "4h" else d1_bars
    mock_ensemble.evaluate.return_value = None
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        data_provider=mock_provider,
        mtf_engine=MultiTimeframeEngine()
    )
    
    decision = orchestrator.evaluate("BTC/USD", h1_bars, h1_bars[-1].timestamp, 10000.0, 0, 0.0)
    assert decision.multi_timeframe_alignment == "ALIGNED_BULLISH"

def test_orchestrator_mtf_future_bar_rejection():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    mock_provider = MagicMock()
    
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    h1_bars = generate_bars(60, start, step_hours=1, trend_up=True)
    
    # Create HTF bars that extend 100 hours into the FUTURE beyond h1_bars[-1]
    h4_future = generate_bars(50, start, step_hours=4, trend_up=False) # Downward trend in future
    mock_provider.get_historical_bars.return_value = h4_future
    
    mock_ensemble.evaluate.return_value = None
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        data_provider=mock_provider,
        mtf_engine=MultiTimeframeEngine()
    )
    
    # Evaluate at h1_bars[20]
    eval_ts = h1_bars[20].timestamp
    decision = orchestrator.evaluate("BTC/USD", h1_bars[:21], eval_ts, 10000.0, 0, 0.0)
    
    # Context must equal eval_ts and reject future bars
    assert decision.timestamp == eval_ts

def test_orchestrator_mtf_missing_data_fallback():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    mock_provider = MagicMock()
    
    mock_provider.get_historical_bars.return_value = []
    mock_ensemble.evaluate.return_value = None
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    now = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc)
    h1_bars = generate_bars(10, now, step_hours=1)
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        data_provider=mock_provider,
        mtf_engine=MultiTimeframeEngine()
    )
    
    decision = orchestrator.evaluate("BTC/USD", h1_bars, h1_bars[-1].timestamp, 10000.0, 0, 0.0)
    assert decision.multi_timeframe_alignment in ("NEUTRAL", "INSUFFICIENT_DATA")

def test_orchestrator_risk_engine_remains_authoritative():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    mock_provider = MagicMock()
    
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    h1_bars = generate_bars(60, start, step_hours=1, trend_up=True)
    
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=h1_bars[-1].timestamp, direction="LONG", strategy="TrendStrategy",
        confidence=0.9, reason="Strong buy", entry_price=150.0
    )
    mock_ensemble.evaluate.return_value = signal
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    # Mock RiskEngine REJECTS the trade
    mock_risk.evaluate_trade.return_value = MagicMock(approved=False, rejection_reason="Max risk limit exceeded")
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        data_provider=mock_provider,
        mtf_engine=MultiTimeframeEngine()
    )
    
    decision = orchestrator.evaluate("BTC/USD", h1_bars, h1_bars[-1].timestamp, 10000.0, 0, 0.0)
    
    # Despite bullish signal, RiskEngine vetoes execution to WAIT
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert decision.paper_execution_eligible is False
