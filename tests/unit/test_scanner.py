import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from app.services.scanner import MarketScanner
from app.core.models import MarketBar

@pytest.fixture
def mock_data_provider():
    provider = Mock()
    # Create some mock bars
    bars_btc = [
        MarketBar(symbol="BTC", timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc), open=16000, high=16500, low=15900, close=16400, volume=1000),
        MarketBar(symbol="BTC", timestamp=datetime(2023, 1, 2, tzinfo=timezone.utc), open=16400, high=16800, low=16300, close=16700, volume=1200)
    ]
    bars_eth = [
        MarketBar(symbol="ETH/USD", timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc), open=1200, high=1250, low=1190, close=1240, volume=500),
        MarketBar(symbol="ETH/USD", timestamp=datetime(2023, 1, 2, tzinfo=timezone.utc), open=1240, high=1200, low=1180, close=1190, volume=600)
    ]
    
    def side_effect(symbol, timeframe, start_time, end_time=None):
        if symbol == "BTC":
            return bars_btc
        elif symbol == "ETH/USD":
            return bars_eth
        else:
            return []
            
    provider.get_historical_bars.side_effect = side_effect
    return provider

@pytest.fixture
def scanner(mock_data_provider):
    return MarketScanner(data_provider=mock_data_provider)

def test_market_scanner_condition(scanner):
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 3, tzinfo=timezone.utc)
    
    # Condition: The last close must be higher than the previous close
    def uptrend_condition(bars):
        if len(bars) < 2:
            return False
        return bars[-1].close > bars[-2].close
        
    symbols = ["BTC", "ETH/USD", "FAKE/USD"]
    matched = scanner.scan(symbols, "1D", start_time, end_time, uptrend_condition)
    
    assert len(matched) == 1
    assert matched[0] == "BTC"
    
def test_market_scanner_get_latest_prices(scanner):
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 3, tzinfo=timezone.utc)
    
    symbols = ["BTC", "ETH/USD"]
    prices = scanner.get_latest_close_prices(symbols, "1D", start_time, end_time)
    
    assert len(prices) == 2
    assert prices["BTC"] == 16700.0
    assert prices["ETH/USD"] == 1190.0

def test_market_scanner_handles_exceptions_gracefully():
    # Provider that raises exception on ETH
    provider = Mock()
    def side_effect(symbol, timeframe, start_time, end_time=None):
        if symbol == "ETH/USD":
            raise ValueError("API Error")
        return [MarketBar(symbol="BTC", timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc), open=16000, high=16500, low=15900, close=16400, volume=1000)]
        
    provider.get_historical_bars.side_effect = side_effect
    scanner = MarketScanner(provider)
    
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 3, tzinfo=timezone.utc)
    
    prices = scanner.get_latest_close_prices(["BTC", "ETH/USD"], "1D", start_time, end_time)
    
    # Should safely skip ETH
    assert "BTC" in prices
    assert "ETH/USD" not in prices
