import pytest
from datetime import datetime
from pydantic import ValidationError
from app.core.models import MarketBar, TradingSignal, RiskDecision, TradeRecord

def test_marketbar_validation():
    # Valid bar
    bar = MarketBar(
        symbol="BTC",
        timestamp=datetime.now(),
        open=50000.0,
        high=51000.0,
        low=49000.0,
        close=50500.0,
        volume=1.5
    )
    assert bar.symbol == "BTC"
    
    # Invalid bar - negative price
    with pytest.raises(ValidationError):
        MarketBar(
            symbol="BTC",
            timestamp=datetime.now(),
            open=-100.0,
            high=51000.0,
            low=49000.0,
            close=50500.0,
            volume=1.5
        )

def test_tradingsignal_validation():
    # Valid signal
    signal = TradingSignal(
        symbol="ETH/USD",
        timestamp=datetime.now(),
        direction="LONG",
        strategy="MovingAverageCrossover",
        confidence=0.85,
        reason="Golden cross detected"
    )
    assert signal.direction == "LONG"
    
    # Invalid direction
    with pytest.raises(ValidationError):
        TradingSignal(
            symbol="ETH/USD",
            timestamp=datetime.now(),
            direction="SIDEWAYS",
            strategy="MovingAverageCrossover",
            confidence=0.85,
            reason="Invalid direction"
        )
        
    # Invalid confidence (must be 0-1)
    with pytest.raises(ValidationError):
        TradingSignal(
            symbol="ETH/USD",
            timestamp=datetime.now(),
            direction="LONG",
            strategy="MACD",
            confidence=1.5,
            reason="High confidence"
        )

def test_riskdecision_validation():
    # Valid decision
    decision = RiskDecision(
        approved=True,
        requested_risk=100.0,
        allowed_risk=100.0,
        position_size=0.5,
        rejection_reason=None
    )
    assert decision.approved is True
    
    # Invalid risk amount
    with pytest.raises(ValidationError):
        RiskDecision(
            approved=True,
            requested_risk=-50.0,
            allowed_risk=100.0,
            position_size=0.5
        )

def test_traderecord_validation():
    # Valid record
    record = TradeRecord(
        id="trade-123",
        symbol="AAPL",
        direction="SHORT",
        entry_price=150.0,
        quantity=10.0,
        status="OPEN",
        timestamp=datetime.now()
    )
    assert record.id == "trade-123"
    assert record.direction == "SHORT"
    
    # Invalid quantity
    with pytest.raises(ValidationError):
        TradeRecord(
            id="trade-124",
            symbol="AAPL",
            direction="LONG",
            entry_price=150.0,
            quantity=0.0,  # Must be strictly greater than 0
            status="OPEN",
            timestamp=datetime.now()
        )
