import pandas as pd
from typing import List
from app.core.models import MarketBar
from app.strategies.base import bars_to_dataframe

def resample_bars(bars: List[MarketBar], rule: str) -> pd.DataFrame:
    """
    Resamples a list of MarketBars to a higher timeframe.
    
    IMPORTANT: To strictly prevent look-ahead bias, incomplete future candles MUST NOT influence the decision.
    This function uses pandas resample with closed='left' and label='left'.
    It only returns completed higher-timeframe candles when evaluated chronologically.
    
    :param bars: List of historical MarketBars
    :param rule: Pandas offset string (e.g. '1H', '4H', '1D')
    :return: Resampled DataFrame
    """
    if not bars:
        return pd.DataFrame()
        
    df = bars_to_dataframe(bars)
    
    # Resample
    # closed='left' and label='left' are common for OHLC resampling, meaning
    # [10:00, 11:00) is aggregated into the 10:00 bucket.
    resampled = df.resample(rule, closed='left', label='left').agg({
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    })
    
    # Drop rows where all elements are NaN (periods with no data)
    resampled.dropna(how='all', inplace=True)
    
    return resampled
