import pytest
from datetime import datetime, timezone
from unittest.mock import Mock
from app.core.models import MarketBar
from app.broker.interfaces import IMarketDataEngine
from app.broker.adapters import ReadOnlyLiveMarketDataAdapter

def test_readonly_adapter_implements_interface():
    adapter = ReadOnlyLiveMarketDataAdapter()
    assert isinstance(adapter, IMarketDataEngine)

def test_readonly_adapter_delegates_historical_bars():
    mock_provider = Mock(spec=["get_historical_bars", "get_latest_bar"])
    now = datetime.now(timezone.utc)
    sample_bar = MarketBar(
        symbol="BTC/USD", timestamp=now, open=50000.0, high=51000.0, low=49500.0, close=50500.0, volume=10.0
    )
    mock_provider.get_historical_bars.return_value = [sample_bar]
    
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_provider)
    bars = adapter.get_historical_bars("BTC/USD", "1h", now)
    
    assert len(bars) == 1
    assert bars[0].symbol == "BTC/USD"
    mock_provider.get_historical_bars.assert_called_once()

def test_readonly_adapter_fallback_when_provider_none():
    adapter = ReadOnlyLiveMarketDataAdapter(provider=None)
    assert adapter.get_latest_bar("BTC/USD") is None
    assert adapter.get_historical_bars("BTC/USD", "1h", datetime.now(timezone.utc)) == []

def test_readonly_adapter_blocks_order_execution():
    adapter = ReadOnlyLiveMarketDataAdapter()
    with pytest.raises(PermissionError) as exc_info:
        adapter.place_order()
    assert "strictly read-only" in str(exc_info.value)
    
    with pytest.raises(PermissionError) as exc_info2:
        adapter.submit_order()
    assert "strictly read-only" in str(exc_info2.value)

    with pytest.raises(PermissionError) as exc_info3:
        adapter.cancel_order()
    assert "strictly read-only" in str(exc_info3.value)

def test_readonly_adapter_ccxt_successful_fetch():
    mock_ccxt = Mock(spec=["fetch_ohlcv", "create_order", "createOrder", "cancel_order"])
    ts_ms = int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
    mock_ccxt.fetch_ohlcv.return_value = [
        [ts_ms, 50000.0, 51000.0, 49500.0, 50500.0, 10.0]
    ]
    
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_ccxt)
    
    bars = adapter.get_historical_bars("BTC/USD", "1h", datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert len(bars) == 1
    assert bars[0].close == 50500.0
    mock_ccxt.fetch_ohlcv.assert_called_once()
    
    # Check latest bar
    latest = adapter.get_latest_bar("BTC/USD")
    assert latest is not None
    assert latest.close == 50500.0

def test_readonly_adapter_ccxt_malformed_response():
    mock_ccxt = Mock(spec=["fetch_ohlcv"])
    # Missing volume
    mock_ccxt.fetch_ohlcv.return_value = [
        [1672531200000, 50000.0, 51000.0, 49500.0, 50500.0]
    ]
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_ccxt)
    
    bars = adapter.get_historical_bars("BTC/USD", "1h", datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert bars == []
    
    latest = adapter.get_latest_bar("BTC/USD")
    assert latest is None

def test_readonly_adapter_ccxt_network_failure():
    mock_ccxt = Mock(spec=["fetch_ohlcv"])
    mock_ccxt.fetch_ohlcv.side_effect = Exception("ccxt.NetworkError: Connection timeout")
    
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_ccxt)
    bars = adapter.get_historical_bars("BTC/USD", "1h", datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert bars == []
    
    latest = adapter.get_latest_bar("BTC/USD")
    assert latest is None

def test_readonly_adapter_ccxt_unsupported_symbol():
    mock_ccxt = Mock(spec=["fetch_ohlcv"])
    mock_ccxt.fetch_ohlcv.side_effect = Exception("ccxt.BadSymbol: Invalid symbol INVALID/USD")
    
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_ccxt)
    bars = adapter.get_historical_bars("INVALID/USD", "1h", datetime(2023, 1, 1, tzinfo=timezone.utc))
    assert bars == []
    
    latest = adapter.get_latest_bar("INVALID/USD")
    assert latest is None

def test_readonly_adapter_no_trading_endpoints():
    mock_ccxt = Mock(spec=["create_order", "createOrder", "cancel_order"])
    adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_ccxt)
    
    with pytest.raises(PermissionError):
        adapter.place_order()
    
    with pytest.raises(PermissionError):
        adapter.submit_order()
        
    with pytest.raises(PermissionError):
        adapter.cancel_order()
        
    mock_ccxt.create_order.assert_not_called()
    mock_ccxt.createOrder.assert_not_called()
    mock_ccxt.cancel_order.assert_not_called()
