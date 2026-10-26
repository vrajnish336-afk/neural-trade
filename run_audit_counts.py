import logging
from datetime import datetime, timezone
from typing import List, Dict
from app.data.csv_provider import CsvHistoricalDataProvider
from app.config import config

def run():
    provider = CsvHistoricalDataProvider(data_dir="data/historical")
    assets = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]
    timeframes = ["1H", "4H"]
    start_time = datetime(2010, 1, 1, tzinfo=timezone.utc)
    
    total = 0
    for symbol in assets:
        for tf in timeframes:
            bars = provider.get_historical_bars(symbol=symbol, timeframe=tf, start_time=start_time)
            c = len(bars) if bars else 0
            total += c
            print(f"{symbol} {tf}: {c}")
            
    print(f"TOTAL EVALUATIONS: {total}")
    print(f"MR QUARANTINE: {getattr(config, 'QUARANTINE_MEAN_REVERSION', 'Unknown')}")
    print(f"KRONOS VETO: {getattr(config, 'KRONOS_STRONG_VETO_ENABLED', 'Unknown')}")

if __name__ == "__main__":
    run()
