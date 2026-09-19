import pytest
from unittest.mock import MagicMock
from datetime import datetime
from app.services.scanner import MarketScanner
from app.core.models import MarketBar

def test_scanner_timeout_handling(caplog):
    mock_provider = MagicMock()
    mock_provider.get_historical_bars.side_effect = TimeoutError("Request timed out")
    
    scanner = MarketScanner(mock_provider)
    symbols = ["BTC/USD"]
    
    results = scanner.scan(
        symbols=symbols,
        timeframe="1D",
        start_time=datetime(2023, 1, 1),
        end_time=datetime(2023, 1, 2),
        condition=lambda bars: True
    )
    
    assert len(results) == 0
    assert "Market-data request timed out: symbol=BTC/USD" in caplog.text

def test_scanner_connection_error_handling(caplog):
    mock_provider = MagicMock()
    mock_provider.get_historical_bars.side_effect = ConnectionError("Connection refused")
    
    scanner = MarketScanner(mock_provider)
    symbols = ["ETH/USD"]
    
    results = scanner.scan(
        symbols=symbols,
        timeframe="1H",
        start_time=datetime(2023, 1, 1),
        end_time=datetime(2023, 1, 2),
        condition=lambda bars: True
    )
    
    assert len(results) == 0
    assert "Market-data connection failed: symbol=ETH/USD" in caplog.text

def test_scanner_unexpected_error_handling(caplog):
    mock_provider = MagicMock()
    mock_provider.get_historical_bars.side_effect = Exception("Malformed response")
    
    scanner = MarketScanner(mock_provider)
    symbols = ["SOL/USD"]
    
    results = scanner.scan(
        symbols=symbols,
        timeframe="15m",
        start_time=datetime(2023, 1, 1),
        end_time=datetime(2023, 1, 2),
        condition=lambda bars: True
    )
    
    assert len(results) == 0
    assert "Unexpected market-data failure: symbol=SOL/USD error=Malformed response" in caplog.text
