from typing import List
import pandas as pd
from app.core.models import MarketBar
from app.analysis.indicators import calculate_atr

def assess_breakout_quality(bars: List[MarketBar], direction: str, entry_price: float, lookback: int = 14) -> str:
    """
    Evaluates real-time breakout quality using ONLY data available up to time T.
    Does NOT use future price movement.
    """
    if len(bars) < lookback + 1:
        return "INSUFFICIENT_DATA"
        
    closes = [b.close for b in bars]
    highs = [b.high for b in bars]
    lows = [b.low for b in bars]
    volumes = [b.volume for b in bars]
    
    # Calculate ATR for volatility context
    df = pd.DataFrame({'high': highs, 'low': lows, 'close': closes})
    atr_series = calculate_atr(df['high'], df['low'], df['close'], period=lookback)
    current_atr = atr_series.iloc[-1]
    
    avg_volume = pd.Series(volumes).iloc[-lookback-1:-1].mean()
    current_volume = volumes[-1]
    
    # Check volume confirmation
    if current_volume < avg_volume * 0.8:
        return "POSSIBLE_FAKEOUT" # Breakout on low volume
        
    # Check breakout distance (is it extending too far too fast?)
    current_close = closes[-1]
    
    if direction == "LONG":
        distance = current_close - entry_price
        if distance > current_atr * 2.0:
            return "POSSIBLE_FAKEOUT" # Exhaustion risk
    elif direction == "SHORT":
        distance = entry_price - current_close
        if distance > current_atr * 2.0:
            return "POSSIBLE_FAKEOUT" # Exhaustion risk
            
    return "HIGH_QUALITY"
