import json
import logging
import ssl
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

INTERVAL_MAP = {
    "1H": "1h",
    "4H": "4h",
    "1D": "1d"
}

INTERVAL_SECONDS = {
    "1H": 3600,
    "4H": 14400,
    "1D": 86400
}


def sanitize_symbol(symbol: str) -> str:
    """Sanitizes symbol for filename (e.g. BTC/USDT -> BTC_USDT)."""
    return symbol.replace("/", "_").replace("\\", "_")


def format_binance_symbol(symbol: str) -> str:
    """Formats symbol for Binance API query (e.g. BTC/USDT -> BTCUSDT)."""
    return symbol.replace("/", "").replace("_", "").replace("-", "").upper()


def _get_secure_ssl_context() -> ssl.SSLContext:
    """Returns a secure, fully verified default SSLContext using certifi CA bundle if available."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def fetch_binance_klines(
    symbol: str, 
    timeframe: str, 
    limit: int = 1000, 
    start_ms: Optional[int] = None,
    base_url: str = "https://data-api.binance.vision/api/v3/klines"
) -> List[list]:
    """
    Fetches raw public OHLCV klines from Binance public data endpoint with secure HTTPS certificate verification.
    No credentials or API keys required.
    """
    binance_symbol = format_binance_symbol(symbol)
    binance_interval = INTERVAL_MAP.get(timeframe, timeframe.lower())
    
    url = f"{base_url}?symbol={binance_symbol}&interval={binance_interval}&limit={limit}"
    if start_ms is not None:
        url += f"&startTime={start_ms}"
        
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    )
    
    ssl_context = _get_secure_ssl_context()
    
    try:
        with urllib.request.urlopen(req, timeout=10, context=ssl_context) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                if isinstance(data, list):
                    return data
                logger.error(f"Unexpected response format for {symbol} {timeframe}: {type(data)}")
                return []
            else:
                logger.error(f"HTTP error {resp.status} for {symbol} {timeframe}")
                return []
    except urllib.error.URLError as e:
        logger.error(f"Network error fetching klines for {symbol} {timeframe}: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected exception fetching klines for {symbol} {timeframe}: {e}")
        return []


def clean_and_validate_klines(
    raw_klines: List[list], 
    symbol: str, 
    timeframe: str
) -> pd.DataFrame:
    """
    Normalizes, cleans, and validates raw kline data into a standardized OHLCV DataFrame.
    """
    if not raw_klines:
        logger.warning(f"Empty raw klines response for {symbol} {timeframe}")
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        
    rows = []
    for k in raw_klines:
        if len(k) < 6:
            continue
        try:
            open_time_ms = int(k[0])
            open_p = float(k[1])
            high_p = float(k[2])
            low_p = float(k[3])
            close_p = float(k[4])
            vol = float(k[5])
            
            dt = datetime.fromtimestamp(open_time_ms / 1000.0, tz=timezone.utc)
            rows.append({
                "timestamp": dt,
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol
            })
        except (ValueError, TypeError) as e:
            logger.warning(f"Skipping malformed kline entry for {symbol}: {k} ({e})")
            continue
            
    if not rows:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])
        
    df = pd.DataFrame(rows)
    
    # 1. Drop NaNs
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    
    # 2. Validate numeric boundaries
    valid_mask = (
        (df["open"] > 0) & 
        (df["high"] > 0) & 
        (df["low"] > 0) & 
        (df["close"] > 0) & 
        (df["volume"] >= 0) & 
        (df["high"] >= df["low"]) & 
        (df["high"] >= df["open"]) & 
        (df["high"] >= df["close"]) & 
        (df["low"] <= df["open"]) & 
        (df["low"] <= df["close"])
    )
    invalid_count = (~valid_mask).sum()
    if invalid_count > 0:
        logger.warning(f"Dropped {invalid_count} invalid OHLCV rows for {symbol} {timeframe}")
        df = df[valid_mask].copy()
        
    # 3. Sort by timestamp and drop duplicates (keep last)
    df = df.sort_values(by="timestamp")
    dupes_count = df.duplicated(subset=["timestamp"]).sum()
    if dupes_count > 0:
        logger.warning(f"Found {dupes_count} duplicate timestamps for {symbol} {timeframe}. Keeping last.")
        df = df.drop_duplicates(subset=["timestamp"], keep="last")
        
    # 4. Check for missing bars
    if len(df) > 1 and timeframe in INTERVAL_SECONDS:
        step_sec = INTERVAL_SECONDS[timeframe]
        time_diffs = df["timestamp"].diff().dt.total_seconds()
        gaps = (time_diffs > step_sec * 1.5).sum()
        if gaps > 0:
            logger.warning(f"Detected {gaps} missing bar gap(s) in {symbol} {timeframe} data")
            
    # Format timestamp as standard string for CSV output
    df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
    return df


import time

def fetch_binance_klines_paginated(
    symbol: str, 
    timeframe: str, 
    target_rows: int = 3000, 
    start_ms: Optional[int] = None,
    base_url: str = "https://data-api.binance.vision/api/v3/klines"
) -> List[list]:
    """
    Fetches raw public OHLCV klines from Binance public data endpoint with secure HTTPS certificate verification,
    paginating using startTime until target_rows or available history is reached.
    """
    all_klines = []
    step_ms = INTERVAL_SECONDS.get(timeframe, 3600) * 1000
    if start_ms is None and target_rows > 1000:
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        current_start = max(0, now_ms - (target_rows * step_ms))
    else:
        current_start = start_ms
    batch_limit = 1000
    
    while len(all_klines) < target_rows:
        fetch_count = min(batch_limit, target_rows - len(all_klines))
        
        batch = None
        for attempt in range(3):
            batch = fetch_binance_klines(
                symbol=symbol,
                timeframe=timeframe,
                limit=fetch_count,
                start_ms=current_start,
                base_url=base_url
            )
            if batch:
                break
            time.sleep(0.5 * (attempt + 1))
            
        if not batch:
            logger.warning(f"No further klines returned for {symbol} {timeframe} at start_ms={current_start}")
            break
            
        all_klines.extend(batch)
        
        if len(batch) < fetch_count:
            break
            
        last_open_time = int(batch[-1][0])
        current_start = last_open_time + step_ms
        time.sleep(0.05)
        
    return all_klines


def ingest_historical_ohlcv(
    symbols: List[str] = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"],
    timeframes: List[str] = ["1H", "4H", "1D"],
    data_dir: str = "data/historical",
    limit: int = 3000,
    start_ms: Optional[int] = None
) -> Dict[str, Any]:
    """
    Ingests public OHLCV data for given symbols and timeframes, saving as CSV.
    """
    out_dir = Path(data_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    summary = {}
    for sym in symbols:
        for tf in timeframes:
            safe_sym = sanitize_symbol(sym)
            file_path = out_dir / f"{safe_sym}_{tf}.csv"
            
            raw = fetch_binance_klines_paginated(sym, tf, target_rows=limit, start_ms=start_ms)
            df = clean_and_validate_klines(raw, sym, tf)
            
            if not df.empty:
                df.to_csv(file_path, index=False)
                summary[f"{safe_sym}_{tf}"] = {
                    "status": "SUCCESS",
                    "path": str(file_path),
                    "rows": len(df),
                    "start": df["timestamp"].iloc[0],
                    "end": df["timestamp"].iloc[-1]
                }
                logger.info(f"Ingested {len(df)} rows to {file_path}")
            else:
                summary[f"{safe_sym}_{tf}"] = {
                    "status": "FAILED",
                    "path": str(file_path),
                    "rows": 0,
                    "error": "Empty or invalid response"
                }
                logger.error(f"Failed to ingest {sym} {tf}")
                
    return summary

