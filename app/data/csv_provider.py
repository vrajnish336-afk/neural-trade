import pandas as pd
import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from app.data.interfaces import HistoricalDataProvider
from app.core.models import MarketBar

logger = logging.getLogger(__name__)

class CsvHistoricalDataProvider(HistoricalDataProvider):
    """
    Historical data provider that reads from CSV files.
    Useful for deterministic testing without external API dependencies.
    """
    
    def __init__(self, data_dir: str):
        self.data_dir = Path(data_dir)
        if not self.data_dir.exists():
            logger.warning("Data directory %s does not exist. Creating it.", self.data_dir)
            self.data_dir.mkdir(parents=True, exist_ok=True)
            
    def _get_file_path(self, symbol: str, timeframe: str) -> Path:
        """Constructs the expected CSV file path for a symbol and timeframe."""
        # Sanitize symbol for filename
        safe_symbol = symbol.replace("/", "_").replace("\\", "_")
        return self.data_dir / f"{safe_symbol}_{timeframe}.csv"

    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        """
        Fetch historical OHLCV bars from a CSV file.
        Expects CSV to have columns that can be mapped to:
        timestamp, open, high, low, close, volume.
        """
        file_path = self._get_file_path(symbol, timeframe)
        
        if not file_path.exists():
            logger.error("CSV file not found: %s", file_path)
            return []
            
        try:
            # Read CSV
            df = pd.read_csv(file_path)
            
            # Normalize column names to lowercase and strip whitespace
            df.columns = [str(c).strip().lower() for c in df.columns]
            
            # Map common column names if necessary (e.g., 'date' -> 'timestamp')
            column_mapping = {
                'date': 'timestamp',
                'time': 'timestamp',
                'datetime': 'timestamp'
            }
            df = df.rename(columns=column_mapping)
            
            # Validate required columns
            required_cols = {'timestamp', 'open', 'high', 'low', 'close', 'volume'}
            if not required_cols.issubset(df.columns):
                missing = required_cols - set(df.columns)
                logger.error("CSV %s is missing required columns: %s", file_path, missing)
                return []
                
            # Convert timestamp to datetime if not already
            df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce', utc=True)
            
            # Convert OHLCV to numeric, coercing errors to NaN
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                
            # Drop invalid rows (missing timestamps or any OHLCV)
            df = df.dropna(subset=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            
            # Ensure proper datetime format for comparisons
            start_time_utc = pd.to_datetime(start_time, utc=True)
            end_time_utc = pd.to_datetime(end_time, utc=True) if end_time else None
            
            # Filter by time range
            mask = df['timestamp'] >= start_time_utc
            if end_time_utc:
                mask = mask & (df['timestamp'] <= end_time_utc)
                
            df = df.loc[mask].copy()
            
            # Sort by timestamp
            df = df.sort_values(by='timestamp')
            
            # Handle duplicate timestamps (keep the last one deterministically)
            if df['timestamp'].duplicated().any():
                logger.warning("Found duplicate timestamps in %s. Keeping the last entry.", file_path)
                df = df.drop_duplicates(subset=['timestamp'], keep='last')
                
            # Convert rows to MarketBar objects
            bars = []
            for _, row in df.iterrows():
                try:
                    bar = MarketBar(
                        symbol=symbol,
                        timestamp=row['timestamp'].to_pydatetime(),
                        open=float(row['open']),
                        high=float(row['high']),
                        low=float(row['low']),
                        close=float(row['close']),
                        volume=float(row['volume'])
                    )
                    bars.append(bar)
                except ValueError as ve:
                    logger.warning("Invalid data for %s at %s: %s", symbol, row['timestamp'], ve)
                except Exception as e:
                    # Skip rows that fail validation (e.g. negative prices caught by Pydantic)
                    logger.warning("Failed to create MarketBar for %s at %s: %s", symbol, row['timestamp'], e)
                    
            return bars
            
        except Exception as e:
            logger.exception("Error reading historical data from %s: %s", file_path, e)
            return []
