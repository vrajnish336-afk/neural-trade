import os
import glob
import pandas as pd
from datetime import datetime, timezone
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from app.data.ingestion import fetch_binance_klines_paginated, clean_and_validate_klines

def expand_data():
    files = glob.glob('data/historical/*_1H.csv')
    
    start_dt_str = "2024-01-01 00:00:00+00:00"
    start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d %H:%M:%S+00:00").replace(tzinfo=timezone.utc)
    start_ms = int(start_dt.timestamp() * 1000)
    
    for f in files:
        df_existing = pd.read_csv(f)
        df_existing['timestamp'] = pd.to_datetime(df_existing['timestamp'], format="ISO8601", utc=True)
        
        current_min_dt = df_existing['timestamp'].min()
        end_ms = int(current_min_dt.timestamp() * 1000) - 1
        
        # fix:
        base_name = os.path.basename(f).replace("_1H.csv", "")
        # e.g. BTC_USDT
        if "_" in base_name:
            symbol_usdt = base_name.split("_")[0] + "/USDT"
        else:
            symbol_usdt = base_name + "/USDT"
        
        print(f"Fetching older data for {symbol_usdt} from {start_dt_str} to before {current_min_dt}")
        
        total_seconds = (end_ms - start_ms) / 1000
        target_rows = int(total_seconds / 3600) + 10
        print(f"Target rows to fetch: {target_rows}")
        
        raw = fetch_binance_klines_paginated(
            symbol=symbol_usdt,
            timeframe="1H",
            target_rows=target_rows,
            start_ms=start_ms
        )
        
        df_new = clean_and_validate_klines(raw, symbol_usdt, "1H")
        if not df_new.empty:
            df_new['timestamp'] = pd.to_datetime(df_new['timestamp'], format="ISO8601", utc=True)
            df_new = df_new[df_new['timestamp'] < current_min_dt]
            print(f"Fetched {len(df_new)} older rows")
            
            df_combined = pd.concat([df_new, df_existing], ignore_index=True)
            df_combined = df_combined.drop_duplicates(subset=["timestamp"], keep="last")
            df_combined = df_combined.sort_values(by="timestamp")
            
            df_combined['timestamp'] = df_combined['timestamp'].dt.strftime("%Y-%m-%d %H:%M:%S+00:00")
            
            df_combined.to_csv(f, index=False)
            print(f"Saved {f}, total rows: {len(df_combined)}, range: {df_combined['timestamp'].iloc[0]} to {df_combined['timestamp'].iloc[-1]}")
        else:
            print(f"Failed to fetch new data for {symbol_usdt}")

if __name__ == "__main__":
    expand_data()
