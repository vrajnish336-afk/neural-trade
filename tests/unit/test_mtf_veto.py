"""
Unit tests for Multi-Timeframe (MTF) Alignment and Resampling in DecisionOrchestrator.
Verifies that:
1. resample_bars() is called to synthesize higher-timeframe candles when data_provider is absent.
2. A LONG signal is rejected if higher timeframes (4H/1D) are strictly BEARISH.
3. A SHORT signal is rejected if higher timeframes (4H/1D) are strictly BULLISH.
4. Signals aligned with higher timeframe trends pass through.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

from app.core.models import MarketBar, TradingSignal, MarketIntelligence, SentimentResult
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.analysis.mtf_engine import MultiTimeframeEngine
from app.analysis.timeframes import resample_bars, resample_to_market_bars
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits


def _generate_bars(count: int, start_time: datetime, step_hours: int = 1, base_price: float = 100.0, trend_up: bool = True) -> list[MarketBar]:
    bars = []
    current = base_price
    for i in range(count):
        ts = start_time + timedelta(hours=i * step_hours)
        current += 1.0 if trend_up else -1.0
        bars.append(MarketBar(
            symbol="BTC/USD",
            timestamp=ts,
            open=current - 0.5,
            high=current + 1.0,
            low=current - 1.0,
            close=current,
            volume=100.0
        ))
    return bars


@pytest.fixture
def mock_dependencies():
    ensemble = MagicMock(spec=StrategyEnsemble)
    intel = MagicMock()
    intel.generate_intelligence.return_value = None
    forecast = MagicMock()
    forecast.generate_forecast.return_value = None
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, 0.02)
    # Mock evaluate_trade to approve if reaches risk engine
    risk_decision = MagicMock()
    risk_decision.approved = True
    risk_decision.position_size = 1.0
    risk_engine.evaluate_trade = MagicMock(return_value=risk_decision)

    return {
        'ensemble': ensemble,
        'intel': intel,
        'forecast': forecast,
        'risk_engine': risk_engine
    }


def test_orchestrator_synthesizes_htf_via_resample_bars(mock_dependencies):
    """
    When data_provider is None, DecisionOrchestrator uses resample_bars()
    to derive 4H bars from 1H bars.
    """
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    # 80 1H bars trending up -> resamples to 20 completed 4H bars
    h1_bars = _generate_bars(80, start, step_hours=1, base_price=100.0, trend_up=True)

    signal = TradingSignal(
        symbol="BTC/USD", timestamp=h1_bars[-1].timestamp, direction="LONG", strategy="Breakout",
        confidence=0.9, reason="Breakout buy", entry_price=h1_bars[-1].close, stop_loss=h1_bars[-1].close * 0.95
    )
    mock_dependencies['ensemble'].evaluate.return_value = signal

    orchestrator = DecisionOrchestrator(
        ensemble=mock_dependencies['ensemble'],
        risk_engine=mock_dependencies['risk_engine'],
        intelligence_service=mock_dependencies['intel'],
        forecasting_service=mock_dependencies['forecast'],
        data_provider=None,  # No data provider! Must synthesize via resample_bars
        mtf_engine=MultiTimeframeEngine()
    )

    decision = orchestrator.evaluate("BTC/USD", h1_bars, 10000.0, 0, 0.0)
    
    # 4H bars must have been synthesized and found bullish
    assert decision.decision == "LONG"
    assert decision.risk_gate_approved is True
    assert decision.multi_timeframe_alignment in ("ALIGNED_BULLISH", "NEUTRAL")


def test_long_signal_rejected_when_htf_is_bearish(mock_dependencies):
    """
    A LONG signal must be blocked if the 4H/1D timeframe is strictly BEARISH.
    """
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Primary bars trending down overall (80 bars trending down)
    h1_bars = _generate_bars(80, start, step_hours=1, base_price=200.0, trend_up=False)

    # Strategy emits an anomalous counter-trend LONG signal on the 1H timeframe
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=h1_bars[-1].timestamp, direction="LONG", strategy="MeanReversion",
        confidence=0.85, reason="Oversold bounce", entry_price=h1_bars[-1].close, stop_loss=h1_bars[-1].close * 0.95
    )
    mock_dependencies['ensemble'].evaluate.return_value = signal

    orchestrator = DecisionOrchestrator(
        ensemble=mock_dependencies['ensemble'],
        risk_engine=mock_dependencies['risk_engine'],
        intelligence_service=mock_dependencies['intel'],
        forecasting_service=mock_dependencies['forecast'],
        data_provider=None,
        mtf_engine=MultiTimeframeEngine()
    )

    decision = orchestrator.evaluate("BTC/USD", h1_bars, 10000.0, 0, 0.0)

    # Must be vetoed to WAIT due to MTF Conflict
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert any("Multi-Timeframe Conflict" in r for r in decision.main_risks)
    assert "Higher timeframe trend is conflicting" in decision.rationale


def test_short_signal_rejected_when_htf_is_bullish(mock_dependencies):
    """
    A SHORT signal must be blocked if the 4H/1D timeframe is strictly BULLISH.
    """
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    # Primary bars trending up strongly (80 bars trending up)
    h1_bars = _generate_bars(80, start, step_hours=1, base_price=100.0, trend_up=True)

    # Strategy emits an anomalous counter-trend SHORT signal
    signal = TradingSignal(
        symbol="BTC/USD", timestamp=h1_bars[-1].timestamp, direction="SHORT", strategy="MeanReversion",
        confidence=0.85, reason="Overbought dip", entry_price=h1_bars[-1].close, stop_loss=h1_bars[-1].close * 1.05
    )
    mock_dependencies['ensemble'].evaluate.return_value = signal

    orchestrator = DecisionOrchestrator(
        ensemble=mock_dependencies['ensemble'],
        risk_engine=mock_dependencies['risk_engine'],
        intelligence_service=mock_dependencies['intel'],
        forecasting_service=mock_dependencies['forecast'],
        data_provider=None,
        mtf_engine=MultiTimeframeEngine()
    )

    decision = orchestrator.evaluate("BTC/USD", h1_bars, 10000.0, 0, 0.0)

    # Must be vetoed to WAIT due to MTF Conflict
    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert any("Multi-Timeframe Conflict" in r for r in decision.main_risks)
    assert "SHORT signal rejected: Higher timeframe trend is conflicting" in decision.rationale


def test_explicit_htf_data_provider_bearish_veto(mock_dependencies):
    """
    When data_provider explicitly supplies 4H/1D bars that are BEARISH,
    a LONG signal is vetoed even if the lower timeframe had a brief bounce.
    """
    start = datetime(2026, 9, 1, 0, 0, 0, tzinfo=timezone.utc)
    h1_bars = _generate_bars(25, start + timedelta(days=20), step_hours=1, base_price=150.0, trend_up=True)
    h4_bearish = _generate_bars(30, start, step_hours=4, base_price=200.0, trend_up=False)

    mock_provider = MagicMock()
    mock_provider.get_historical_bars.side_effect = lambda sym, tf, **kw: h4_bearish if tf == "4h" else []

    signal = TradingSignal(
        symbol="BTC/USD", timestamp=h1_bars[-1].timestamp, direction="LONG", strategy="TrendStrategy",
        confidence=0.9, reason="1H buy", entry_price=150.0, stop_loss=140.0
    )
    mock_dependencies['ensemble'].evaluate.return_value = signal

    orchestrator = DecisionOrchestrator(
        ensemble=mock_dependencies['ensemble'],
        risk_engine=mock_dependencies['risk_engine'],
        intelligence_service=mock_dependencies['intel'],
        forecasting_service=mock_dependencies['forecast'],
        data_provider=mock_provider,
        mtf_engine=MultiTimeframeEngine()
    )

    decision = orchestrator.evaluate("BTC/USD", h1_bars, 10000.0, 0, 0.0)

    assert decision.decision == "WAIT"
    assert decision.risk_gate_approved is False
    assert any("Multi-Timeframe Conflict" in r for r in decision.main_risks)
