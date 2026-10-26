import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def generate_synthetic_data(filename="data/sample/synthetic_test_data.csv"):
    """
    Generates synthetic OHLCV data designed to test baseline strategies.
    TEST FIXTURES ONLY. NOT REAL MARKET DATA.
    """
    np.random.seed(42) # Deterministic
    
    dates = [datetime(2023, 1, 1) + timedelta(days=i) for i in range(100)]
    
    # Create a base trend, a sudden breakout, and mean reversion noise
    base_price = 100.0
    prices = []
    
    for i in range(100):
        if i < 30:
            # Flat/slight trend
            base_price += np.random.normal(0, 1)
        elif i < 40:
            # Breakout up
            base_price += np.random.normal(3, 1)
        elif i < 60:
            # Mean reversion (drop back down)
            base_price -= np.random.normal(2, 1)
        else:
            # Trend up
            base_price += np.random.normal(1, 1.5)
            
        prices.append(base_price)
        
    df = pd.DataFrame({'timestamp': dates})
    df['open'] = prices
    df['high'] = df['open'] + np.abs(np.random.normal(2, 1, 100))
    df['low'] = df['open'] - np.abs(np.random.normal(2, 1, 100))
    df['close'] = df['open'] + np.random.normal(0, 1, 100)
    
    # Ensure High is highest, Low is lowest
    df['high'] = df[['open', 'high', 'close']].max(axis=1)
    df['low'] = df[['open', 'low', 'close']].min(axis=1)
    
    df['volume'] = np.abs(np.random.normal(1000, 200, 100))
    
    # Format
    df['timestamp'] = df['timestamp'].dt.strftime('%Y-%m-%dT%H:%M:%SZ')
    df['open'] = df['open'].round(2)
    df['high'] = df['high'].round(2)
    df['low'] = df['low'].round(2)
    df['close'] = df['close'].round(2)
    df['volume'] = df['volume'].round(0)
    
    df.to_csv(filename, index=False)
    print(f"Created {filename}")

if __name__ == "__main__":
    generate_synthetic_data()
