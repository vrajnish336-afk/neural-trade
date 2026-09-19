import pytest
from datetime import datetime, timezone
from app.core.models import TradingSignal
from app.analysis.signal_validation import is_valid_signal

def test_valid_signal():
    signal = TradingSignal(
        symbol="BTC", timestamp=datetime.now(timezone.utc),
        direction="LONG", strategy="Test", confidence=0.8,
        entry_price=100.0, stop_loss=90.0, take_profit=120.0, reason="test"
    )
    assert is_valid_signal(signal) is True

def test_invalid_signal_logic():
    # Long with stop loss above entry
    signal_long_bad_sl = TradingSignal(
        symbol="BTC", timestamp=datetime.now(timezone.utc),
        direction="LONG", strategy="Test", confidence=0.8,
        entry_price=100.0, stop_loss=110.0, take_profit=120.0, reason="test"
    )
    assert is_valid_signal(signal_long_bad_sl) is False
    
    # Short with take profit above entry
    signal_short_bad_tp = TradingSignal(
        symbol="BTC", timestamp=datetime.now(timezone.utc),
        direction="SHORT", strategy="Test", confidence=0.8,
        entry_price=100.0, stop_loss=110.0, take_profit=120.0, reason="test"
    )
    assert is_valid_signal(signal_short_bad_tp) is False
    
def test_invalid_confidence():
    with pytest.raises(ValueError):
        TradingSignal(
            symbol="BTC", timestamp=datetime.now(timezone.utc),
            direction="LONG", strategy="Test", confidence=1.5,
            reason="test"
        )
