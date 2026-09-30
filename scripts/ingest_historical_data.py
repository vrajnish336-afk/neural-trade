import sys
import logging
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from app.data.ingestion import ingest_historical_ohlcv

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("=== STARTING HISTORICAL OHLCV DATA INGESTION ===")
    
    symbols = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT"]
    timeframes = ["1H", "4H", "1D"]
    
    results = ingest_historical_ohlcv(symbols=symbols, timeframes=timeframes, limit=3000)
    
    print("\n=== INGESTION SUMMARY ===")
    for key, info in results.items():
        if info["status"] == "SUCCESS":
            print(f"  [PASS] {key}: {info['rows']} rows saved to {info['path']} ({info['start']} -> {info['end']})")
        else:
            print(f"  [FAIL] {key}: {info['error']}")
            
    print("\nIngestion task completed safely.")

if __name__ == "__main__":
    main()
