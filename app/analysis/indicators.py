import pandas as pd
import numpy as np

def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average."""
    if period <= 0:
        return pd.Series(np.nan, index=series.index)
    return series.rolling(window=period, min_periods=period).mean()

def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    if period <= 0:
        return pd.Series(np.nan, index=series.index)
    return series.ewm(span=period, adjust=False, min_periods=period).mean()

def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Relative Strength Index."""
    if period <= 0:
        return pd.Series(np.nan, index=series.index)
        
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    
    # Standard RSI uses smoothed moving average (similar to Wilder's original)
    avg_gain = gain.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero where avg_loss is 0
    rsi[avg_loss == 0] = 100
    rsi[avg_gain == 0] = 0
    
    return rsi

def calculate_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> pd.Series:
    """Calculates Average True Range."""
    if period <= 0:
        return pd.Series(np.nan, index=high.index)
        
    prev_close = close.shift(1)
    
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    
    # Wilder's smoothing
    atr = tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    return atr

def calculate_volatility(series: pd.Series, period: int) -> pd.Series:
    """Calculates rolling volatility (standard deviation of returns)."""
    if period <= 1:
        return pd.Series(np.nan, index=series.index)
    returns = series.pct_change()
    return returns.rolling(window=period, min_periods=period).std()

def calculate_average_volume(series: pd.Series, period: int) -> pd.Series:
    """Calculates simple moving average of volume."""
    return calculate_sma(series, period)

def calculate_roc(series: pd.Series, period: int) -> pd.Series:
    """Calculates Rate of Change (percentage change from period ago)."""
    if period <= 0:
        return pd.Series(np.nan, index=series.index)
    return series.pct_change(periods=period) * 100
