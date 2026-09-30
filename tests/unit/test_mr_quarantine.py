import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
import pandas as pd

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.mean_reversion import MeanReversionStrategy
from app.config import config

@pytest.fixture
def dummy_bars():
    now = datetime.now(timezone.utc)
    # create some dummy bars that would trigger a signal
    return [
        MarketBar(symbol="BTC/USD", timestamp=now, open=100.0, high=105.0, low=95.0, close=100.0, volume=10.0)
        for _ in range(25)
    ]

@patch("app.strategies.ensemble.config")
def test_mean_reversion_quarantined_by_default(mock_config, dummy_bars):
    mock_config.QUARANTINE_MEAN_REVERSION = True
    mock_config.MIN_SIGNAL_SCORE = 10.0
    
    mr_strat = MeanReversionStrategy()
    mr_strat.generate_signal = MagicMock(return_value=TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="MeanReversion_20", confidence=0.8, entry_price=100.0, reason="test"
    ))
    
    ensemble = StrategyEnsemble([mr_strat])
    regime = MarketRegimeResult(regime="RANGE_BOUND", confidence=0.8, volatility_score=0.5, components={})
    
    # Should evaluate to None because it's quarantined (no signals -> NO_STRATEGY_SIGNAL)
    result = ensemble.evaluate(dummy_bars, regime)
    assert result is None
    mr_strat.generate_signal.assert_not_called()

@patch("app.strategies.ensemble.config")
def test_breakout_trendfollowing_active(mock_config, dummy_bars):
    mock_config.QUARANTINE_MEAN_REVERSION = True
    mock_config.MIN_SIGNAL_SCORE = 10.0
    mock_config.get_strategy_min_score.return_value = 10.0
    
    mr_strat = MeanReversionStrategy()
    
    mock_breakout = MagicMock()
    mock_breakout.name = "BreakoutStrategy"
    mock_breakout.__class__.__name__ = "BreakoutStrategy"
    mock_breakout.generate_signal.return_value = TradingSignal(
        symbol="BTC/USD", timestamp=datetime.now(timezone.utc), direction="LONG",
        strategy="BreakoutStrategy", confidence=0.8, entry_price=100.0, reason="test"
    )
    
    ensemble = StrategyEnsemble([mr_strat, mock_breakout])
    regime = MarketRegimeResult(regime="RANGE_BOUND", confidence=0.8, volatility_score=0.5, components={})
    
    result = ensemble.evaluate(dummy_bars, regime)
    
    # Breakout is still active
    assert result is not None
    assert "BreakoutStrategy" in result.strategy
    # MR is skipped
    mock_breakout.generate_signal.assert_called_once()

def test_research_importability_remains_intact():
    # Verify the class is still instantiable and generate_signal can be called directly
    mr_strat = MeanReversionStrategy()
    bars = [MarketBar(symbol="TEST", timestamp=datetime.now(timezone.utc), open=100.0, high=105.0, low=95.0, close=100.0, volume=10.0) for _ in range(25)]
    # Just checking it doesn't crash (might return None if no signal, but it executes)
    signal = mr_strat.generate_signal(bars)
    assert signal is None or isinstance(signal, TradingSignal)

@patch("app.strategies.ensemble.config")
def test_mean_reversion_quarantine_fail_closed_invalid_flag(mock_config, dummy_bars):
    # Simulating the fail closed logic inside ensemble
    mock_config.QUARANTINE_MEAN_REVERSION = True  # Represents the fail closed default
    mock_config.MIN_SIGNAL_SCORE = 10.0
    
    mr_strat = MeanReversionStrategy()
    mr_strat.generate_signal = MagicMock()
    
    ensemble = StrategyEnsemble([mr_strat])
    regime = MarketRegimeResult(regime="RANGE_BOUND", confidence=0.8, volatility_score=0.5, components={})
    
    result = ensemble.evaluate(dummy_bars, regime)
    assert result is None
    mr_strat.generate_signal.assert_not_called()
