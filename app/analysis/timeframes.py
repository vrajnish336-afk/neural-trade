import pandas as pd
from typing import List, Optional
from pandas.tseries.frequencies import to_offset
from app.core.models import MarketBar
from app.strategies.base import bars_to_dataframe

def resample_bars(bars: List[MarketBar], rule: str, drop_incomplete: bool = True) -> pd.DataFrame:
    """
    Resamples a list of MarketBars to a higher timeframe.
    
    IMPORTANT: To strictly prevent look-ahead bias, incomplete future candles MUST NOT influence the decision.
    This function uses pandas resample with closed='left' and label='left'.
    When drop_incomplete=True (default), it strictly drops the trailing still-forming bucket,
    returning only completed higher-timeframe candles.
    
    :param bars: List of historical MarketBars
    :param rule: Pandas offset string (e.g. '1h', '4h', '1d', '15m')
    :param drop_incomplete: If True, drops the final bucket if it is not yet completed.
    :return: Resampled DataFrame containing only completed higher-timeframe candles
    """
    if not bars:
        return pd.DataFrame()
        
    df = bars_to_dataframe(bars)
    if df.empty:
        return df
        
    # Standardize rule formatting (e.g. '1H' -> '1h', '4H' -> '4h', '1D' -> '1d')
    resample_rule = rule.lower() if rule.lower() in ("1h", "4h", "1d", "15m", "30m", "2h", "6h", "8h", "12h") else rule
    
    # Resample with left-closed, left-labeled intervals
    resampled = df.resample(resample_rule, closed='left', label='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Drop rows where any required OHLCV element is NaN
    resampled.dropna(subset=['open', 'high', 'low', 'close', 'volume'], inplace=True)
    if resampled.empty:
        return resampled

    # Drop the trailing still-forming bucket if incomplete
    if drop_incomplete and len(resampled) > 0:
        try:
            offset = to_offset(resample_rule)
            last_bucket_start = resampled.index[-1]
            bucket_end = last_bucket_start + offset
            
            # Determine coverage of the input data
            if len(df) >= 2:
                deltas = df.index.to_series().diff().dropna()
                positive_deltas = deltas[deltas > pd.Timedelta(0)]
                min_step = positive_deltas.min() if not positive_deltas.empty else pd.Timedelta(hours=1)
                data_end = df.index[-1] + min_step
            else:
                data_end = df.index[-1]
                
            # If the data does not reach bucket_end, the bucket is still forming and must be dropped
            if data_end < bucket_end:
                resampled = resampled.iloc[:-1].copy()
        except Exception:
            pass
            
    return resampled


def resample_to_market_bars(bars: List[MarketBar], rule: str, drop_incomplete: bool = True) -> List[MarketBar]:
    """
    Resamples a list of MarketBars to a higher timeframe and returns a list of completed MarketBars.
    """
    df = resample_bars(bars, rule, drop_incomplete=drop_incomplete)
    if df.empty:
        return []
    symbol = bars[0].symbol if bars else "UNKNOWN"
    result = []
    for ts, row in df.iterrows():
        if pd.isna(row['open']) or pd.isna(row['close']) or row['open'] <= 0 or row['close'] <= 0:
            continue
        dt = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts
        result.append(MarketBar(
            symbol=symbol,
            timestamp=dt,
            open=float(row['open']),
            high=float(row['high']),
            low=float(row['low']),
            close=float(row['close']),
            volume=float(row['volume'])
        ))
    return result
