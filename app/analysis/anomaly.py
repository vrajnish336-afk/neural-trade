from typing import List
import pandas as pd
from app.core.models import MarketBar

def detect_anomalies(bars: List[MarketBar], zscore_threshold: float = 2.5, lookback: int = 20) -> List[str]:
    """
    Detects unusual market behavior.
    Does NOT predict price direction. Purely statistical anomaly detection.
    """
    if len(bars) < lookback + 1:
        return ["INSUFFICIENT_DATA"]
        
    flags = []
    
    # Extract series
    closes = pd.Series([b.close for b in bars])
    volumes = pd.Series([b.volume for b in bars])
    
    # 1. Unusual Volume
    vol_mean = volumes.iloc[-lookback-1:-1].mean()
    vol_std = volumes.iloc[-lookback-1:-1].std()
    
    current_vol = volumes.iloc[-1]
    
    if vol_std > 0:
        vol_z = (current_vol - vol_mean) / vol_std
        if vol_z > zscore_threshold:
            flags.append("UNUSUAL_VOLUME")
    
    # 2. Unusual Price Movement (Return Z-Score)
    returns = closes.pct_change().dropna()
    if len(returns) >= lookback:
        ret_mean = returns.iloc[-lookback-1:-1].mean()
        ret_std = returns.iloc[-lookback-1:-1].std()
        current_ret = returns.iloc[-1]
        
        if ret_std > 0:
            ret_z = abs(current_ret - ret_mean) / ret_std
            if ret_z > zscore_threshold:
                flags.append("ABNORMAL_PRICE_MOVE")
                
    # 3. Low Liquidity
    if vol_mean == 0 or current_vol == 0:
        flags.append("LOW_LIQUIDITY")
        
    return flags
