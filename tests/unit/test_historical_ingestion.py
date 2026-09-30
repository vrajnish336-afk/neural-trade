import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import pandas as pd
from datetime import datetime, timezone

from app.data.ingestion import (
    sanitize_symbol,
    format_binance_symbol,
    fetch_binance_klines,
    clean_and_validate_klines,
    ingest_historical_ohlcv
)
from app.data.csv_provider import CsvHistoricalDataProvider

@pytest.fixture
def sample_raw_klines():
    return [
        [1700000000000, "50000.0", "51000.0", "49500.0", "50500.0", "123.45", 1700003599999, "...", 100, "...", "...", "0"],
        [1700003600000, "50500.0", "52000.0", "50000.0", "51500.0", "200.10", 1700007199999, "...", 150, "...", "...", "0"],
        # Duplicate timestamp entry
        [1700003600000, "50500.0", "52000.0", "50000.0", "51500.0", "205.00", 1700007199999, "...", 150, "...", "...", "0"],
        # Invalid entry (high < low)
        [1700007200000, "51500.0", "48000.0", "52000.0", "51000.0", "50.00", 1700010799999, "...", 80, "...", "...", "0"],
    ]

def test_symbol_formatting():
    assert sanitize_symbol("BTC/USDT") == "BTC_USDT"
    assert sanitize_symbol("ETH/USDT") == "ETH_USDT"
    assert format_binance_symbol("BTC/USDT") == "BTCUSDT"
    assert format_binance_symbol("ETH/USDT") == "ETHUSDT"

def test_clean_and_validate_klines_valid_and_dedup(sample_raw_klines):
    df = clean_and_validate_klines(sample_raw_klines, "BTC/USDT", "1H")
    
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) == {"timestamp", "open", "high", "low", "close", "volume"}
    assert len(df) == 2  # 1 duplicate removed, 1 invalid high<low removed
    assert df["open"].iloc[0] == 50000.0
    assert df["volume"].iloc[1] == 205.00  # Kept last duplicate

def test_clean_and_validate_klines_empty_and_malformed():
    df_empty = clean_and_validate_klines([], "BTC/USDT", "1H")
    assert df_empty.empty
    assert set(df_empty.columns) == {"timestamp", "open", "high", "low", "close", "volume"}
    
    malformed = [["invalid"], [None, "open", "high"]]
    df_malformed = clean_and_validate_klines(malformed, "BTC/USDT", "1H")
    assert df_malformed.empty

@patch("urllib.request.urlopen")
def test_fetch_binance_klines_mocked(mock_urlopen, sample_raw_klines):
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.read.return_value = json.dumps(sample_raw_klines).encode("utf-8")
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    klines = fetch_binance_klines("BTC/USDT", "1H", limit=10)
    assert len(klines) == 4
    assert klines[0][0] == 1700000000000

@patch("app.data.ingestion.fetch_binance_klines")
def test_ingest_historical_ohlcv_end_to_end(mock_fetch, sample_raw_klines, tmp_path):
    mock_fetch.return_value = sample_raw_klines
    
    summary = ingest_historical_ohlcv(
        symbols=["BTC/USDT", "ETH/USDT"],
        timeframes=["1H", "4H"],
        data_dir=str(tmp_path)
    )
    
    assert summary["BTC_USDT_1H"]["status"] == "SUCCESS"
    assert summary["BTC_USDT_1H"]["rows"] == 2
    
    csv_file = tmp_path / "BTC_USDT_1H.csv"
    assert csv_file.exists()
    
    # Test reading saved file with CsvHistoricalDataProvider
    provider = CsvHistoricalDataProvider(str(tmp_path))
    bars = provider.get_historical_bars("BTC/USDT", "1H", start_time=datetime(1970, 1, 1, tzinfo=timezone.utc))
    assert len(bars) == 2
    assert bars[0].open == 50000.0
    assert bars[0].close == 50500.0
