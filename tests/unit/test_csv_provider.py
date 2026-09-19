import pytest
import pandas as pd
from datetime import datetime, timezone
from pathlib import Path
from app.data.csv_provider import CsvHistoricalDataProvider

@pytest.fixture
def test_data_dir(tmp_path):
    return tmp_path / "data"

@pytest.fixture
def csv_provider(test_data_dir):
    return CsvHistoricalDataProvider(data_dir=str(test_data_dir))

def test_csv_provider_initialization(test_data_dir):
    provider = CsvHistoricalDataProvider(data_dir=str(test_data_dir))
    assert test_data_dir.exists()

def test_get_historical_bars_valid_data(csv_provider, test_data_dir):
    # Create mock CSV
    symbol = "BTC/USD"
    timeframe = "1D"
    safe_symbol = "BTC_USD"
    file_path = test_data_dir / f"{safe_symbol}_{timeframe}.csv"
    
    csv_content = """timestamp,open,high,low,close,volume
2023-01-01T00:00:00Z,16000,16500,15900,16400,1000
2023-01-02T00:00:00Z,16400,16800,16300,16700,1200
"""
    file_path.write_text(csv_content)
    
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end_time = datetime(2023, 1, 3, tzinfo=timezone.utc)
    
    bars = csv_provider.get_historical_bars(symbol, timeframe, start_time, end_time)
    
    assert len(bars) == 2
    assert bars[0].close == 16400.0
    assert bars[1].close == 16700.0
    assert bars[0].volume == 1000.0
    assert bars[0].symbol == "BTC/USD"

def test_get_historical_bars_missing_columns(csv_provider, test_data_dir):
    # Missing 'volume'
    symbol = "ETH/USD"
    timeframe = "1D"
    file_path = test_data_dir / "ETH_USD_1D.csv"
    
    csv_content = """timestamp,open,high,low,close
2023-01-01T00:00:00Z,1200,1250,1190,1240
"""
    file_path.write_text(csv_content)
    
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = csv_provider.get_historical_bars(symbol, timeframe, start_time)
    
    assert len(bars) == 0

def test_get_historical_bars_invalid_rows_and_duplicates(csv_provider, test_data_dir):
    symbol = "SOL/USD"
    timeframe = "1H"
    file_path = test_data_dir / "SOL_USD_1H.csv"
    
    # Has a missing value (row 2), a bad price (row 3 has string for open), 
    # a duplicate timestamp (row 4 and 5), and a negative price (row 6, rejected by pydantic)
    csv_content = """date,open,high,low,close,volume
2023-01-01T00:00:00Z,20,21,19,20.5,100
2023-01-01T01:00:00Z,,22,20,21.5,150
2023-01-01T02:00:00Z,BAD,23,21,22.5,200
2023-01-01T03:00:00Z,22,23,21,22.5,200
2023-01-01T03:00:00Z,22.1,23.1,21.1,22.6,201
2023-01-01T04:00:00Z,-10,20,10,15,100
"""
    file_path.write_text(csv_content)
    
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = csv_provider.get_historical_bars(symbol, timeframe, start_time)
    
    # Valid: 
    # row 1 is good
    # row 2 is dropped by pandas (missing open)
    # row 3 is dropped by pandas (coerced BAD to NaN)
    # row 4 and 5 are duplicates, keeps row 5
    # row 6 drops during Pydantic validation (caught in except block, skipped)
    
    assert len(bars) == 2
    assert bars[0].close == 20.5
    assert bars[1].close == 22.6
    assert bars[1].volume == 201

def test_get_historical_bars_missing_file(csv_provider):
    symbol = "BTC/USD"
    timeframe = "1D"
    start_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    bars = csv_provider.get_historical_bars(symbol, timeframe, start_time)
    assert len(bars) == 0
