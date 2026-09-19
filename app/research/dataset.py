import math
import random
from typing import List, Dict
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar

def generate_synthetic_data(
    symbols: List[str], 
    num_bars: int = 2000, 
    seed: int = 42,
    start_time: datetime = datetime(2022, 1, 1, tzinfo=timezone.utc),
    timeframe_minutes: int = 60
) -> Dict[str, List[MarketBar]]:
    """
    Generates a deterministic synthetic research dataset containing multiple regimes.
    Regimes generated via combined sine waves and noise.
    """
    random.seed(seed)
    
    datasets = {}
    for symbol in symbols:
        bars = []
        current_price = 100.0
        
        # Each symbol gets a slightly different phase and volatility
        phase_shift = random.uniform(0, math.pi * 2)
        base_volatility = random.uniform(0.005, 0.02)
        
        for i in range(num_bars):
            timestamp = start_time + timedelta(minutes=timeframe_minutes * i)
            
            # Create a macro trend (slow sine)
            macro_trend = math.sin(i / 400.0 + phase_shift) * 0.001
            
            # Create a micro cycle (fast sine)
            micro_cycle = math.cos(i / 50.0 + phase_shift) * 0.002
            
            # Dynamic volatility regime
            # High volatility in the middle of the dataset
            vol_multiplier = 1.0 + math.sin(i / 200.0) * 0.5 
            current_vol = base_volatility * max(0.2, vol_multiplier)
            
            noise = random.gauss(0, current_vol)
            
            # Price step
            drift = macro_trend + micro_cycle + noise
            
            open_price = current_price
            close_price = open_price * (1.0 + drift)
            
            # Ensure high and low bound the open and close appropriately
            high_price = max(open_price, close_price) * (1.0 + abs(random.gauss(0, current_vol * 0.5)))
            low_price = min(open_price, close_price) * (1.0 - abs(random.gauss(0, current_vol * 0.5)))
            
            volume = max(100.0, random.gauss(5000, 2000) * (1.0 + abs(drift) * 10))
            
            bars.append(MarketBar(
                symbol=symbol,
                timestamp=timestamp,
                open=open_price,
                high=high_price,
                low=low_price,
                close=close_price,
                volume=volume
            ))
            
            current_price = close_price
            
        datasets[symbol] = bars
        
    return datasets

def generate_regime_dataset(
    regime_type: str,
    symbol: str = "REGIME_TEST",
    num_bars: int = 1000,
    seed: int = 42,
    start_time: datetime = datetime(2022, 1, 1, tzinfo=timezone.utc),
    timeframe_minutes: int = 60
) -> List[MarketBar]:
    """
    Generates a deterministic dataset for a specific market regime.
    Supported: TRENDING_UP, TRENDING_DOWN, RANGE_BOUND, HIGH_VOLATILITY, LOW_VOLATILITY
    """
    random.seed(seed)
    bars = []
    current_price = 100.0
    
    # Configuration based on regime
    trend_drift = 0.0
    volatility = 0.01
    
    if regime_type == "TRENDING_UP":
        trend_drift = 0.002
    elif regime_type == "TRENDING_DOWN":
        trend_drift = -0.002
    elif regime_type == "RANGE_BOUND":
        trend_drift = 0.0
        volatility = 0.008
    elif regime_type == "HIGH_VOLATILITY":
        trend_drift = 0.0
        volatility = 0.04
    elif regime_type == "LOW_VOLATILITY":
        trend_drift = 0.0
        volatility = 0.003
        
    for i in range(num_bars):
        timestamp = start_time + timedelta(minutes=timeframe_minutes * i)
        
        if regime_type == "RANGE_BOUND":
            # Add a sine wave reverting to 100
            reversion = (100.0 - current_price) * 0.05
        else:
            reversion = 0.0
            
        step = current_price * (trend_drift + reversion + random.gauss(0, volatility))
        
        open_p = max(0.1, current_price)
        close_p = max(0.1, current_price + step)
        high_p = max(open_p, close_p) + (open_p * abs(random.gauss(0, volatility * 0.5)))
        low_p = min(open_p, close_p) - (open_p * abs(random.gauss(0, volatility * 0.5)))
        low_p = max(0.01, low_p) # Ensure low is strictly > 0
        volume = random.uniform(1000, 5000) * (2.0 if regime_type == "HIGH_VOLATILITY" else 1.0)
        
        bars.append(MarketBar(
            symbol=symbol,
            timestamp=timestamp,
            open=round(open_p, 4),
            high=round(high_p, 4),
            low=round(low_p, 4),
            close=round(close_p, 4),
            volume=round(volume, 2)
        ))
        current_price = close_p
        
    return bars
