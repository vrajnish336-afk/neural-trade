import logging
from datetime import datetime, timezone
import warnings

print("Start script")
from app.config import config
print("Imported config")
from app.data.csv_provider import CsvHistoricalDataProvider
print("Imported CsvHistoricalDataProvider")
from app.database.schema import init_db
print("Imported init_db")
from app.research.robustness.runner import create_engine_factory
print("Imported create_engine_factory")

def run():
    print("Init DB...")
    init_db()
    print("DB Init Done.")
    
    print("Init Provider...")
    provider = CsvHistoricalDataProvider(data_dir="data/historical")
    
    assets = ["BTC_USDT", "ETH_USDT", "SOL_USDT", "BNB_USDT"]
    timeframes = ["1H", "4H"]
    
    all_bars = []
    start_time = datetime(2010, 1, 1, tzinfo=timezone.utc)
    
    for symbol in assets:
        for tf in timeframes:
            print(f"Loading {symbol} {tf}...")
            bars = provider.get_historical_bars(
                symbol=symbol, 
                timeframe=tf,
                start_time=start_time
            )
            if bars:
                all_bars.extend(bars)
                print(f"  Loaded {len(bars)} bars")
                
    # Sort all bars strictly by chronological order
    print("Sorting bars...")
    all_bars.sort(key=lambda b: b.timestamp)
    print("Sorting done.")
    
    # Engine uses current corrected config
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    
    print("Creating engine...")
    engine = create_engine_factory(use_adaptive=True, breakout_period=20)
    
    print("Running engine...")
    result = engine.run(all_bars)
    
    print(f"DONE. Trades: {result.number_of_trades}")
    
if __name__ == "__main__":
    run()
