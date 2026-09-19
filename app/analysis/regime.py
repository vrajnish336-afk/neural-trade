import pandas as pd
from typing import List
from app.core.models import MarketBar, MarketRegimeResult
from app.strategies.base import bars_to_dataframe
from app.analysis.indicators import calculate_sma, calculate_volatility

def detect_market_regime(bars: List[MarketBar], lookback: int = 20, atr_period: int = 14) -> MarketRegimeResult:
    """
    Deterministic market regime detector based on price action and dynamic volatility.
    """
    dyn_lookback = 90
    if len(bars) < lookback + dyn_lookback:
        return MarketRegimeResult(regime="INSUFFICIENT_DATA", confidence=0.0)
        
    df = bars_to_dataframe(bars)
    
    close_series = df['close']
    sma = calculate_sma(close_series, lookback)
    volatility = calculate_volatility(close_series, lookback)
    
    current_close = close_series.iloc[-1]
    current_sma = sma.iloc[-1]
    prev_sma = sma.iloc[-2]
    current_volatility = volatility.iloc[-1]
    
    # Dynamic volatility threshold: 90th percentile of rolling 90-day volatility
    dyn_threshold = volatility.rolling(window=dyn_lookback, min_periods=dyn_lookback).quantile(0.90).iloc[-1]
    
    # Calculate a simple trend slope percentage
    if prev_sma != 0:
        sma_slope_pct = (current_sma - prev_sma) / prev_sma * 100
    else:
        sma_slope_pct = 0.0
        
    # Volatility check
    is_high_volatility = current_volatility > dyn_threshold if not pd.isna(dyn_threshold) else False
    
    if is_high_volatility:
        return MarketRegimeResult(regime="HIGH_VOLATILITY", confidence=0.8)
        
    # Trend thresholds
    trend_threshold = 0.05 # 0.05% slope per period
    
    if sma_slope_pct > trend_threshold and current_close > current_sma:
        return MarketRegimeResult(regime="TRENDING_UP", confidence=0.7)
        
    elif sma_slope_pct < -trend_threshold and current_close < current_sma:
        return MarketRegimeResult(regime="TRENDING_DOWN", confidence=0.7)
        
    else:
        return MarketRegimeResult(regime="RANGE_BOUND", confidence=0.6)
