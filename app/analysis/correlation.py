import pandas as pd
from typing import List, Dict
from app.core.models import MarketBar

def calculate_historical_correlation(symbol_data: Dict[str, List[MarketBar]], min_periods: int = 30) -> pd.DataFrame:
    """
    Calculate historical return correlation between symbols up to the current available data.
    """
    if len(symbol_data) < 2:
        return pd.DataFrame()
        
    series_dict = {}
    for symbol, bars in symbol_data.items():
        if len(bars) < min_periods:
            continue
        # Use timestamp as index
        df = pd.DataFrame([{'timestamp': b.timestamp, 'close': b.close} for b in bars])
        df.set_index('timestamp', inplace=True)
        # Calculate returns
        series_dict[symbol] = df['close'].pct_change().dropna()
        
    if len(series_dict) < 2:
        return pd.DataFrame()
        
    # Combine into a single dataframe
    combined_df = pd.DataFrame(series_dict)
    
    # Calculate correlation matrix
    return combined_df.corr()

def get_correlation_status(correlation_matrix: pd.DataFrame, symbol1: str, symbol2: str, threshold: float = 0.7) -> str:
    """
    Check if two symbols are highly correlated based on the matrix.
    Returns: 'HIGH_CORRELATION', 'LOW_CORRELATION', or 'INSUFFICIENT_DATA'
    """
    if correlation_matrix.empty:
        return "INSUFFICIENT_DATA"
        
    if symbol1 not in correlation_matrix.columns or symbol2 not in correlation_matrix.columns:
        return "INSUFFICIENT_DATA"
        
    corr_value = correlation_matrix.loc[symbol1, symbol2]
    if pd.isna(corr_value):
        return "INSUFFICIENT_DATA"
        
    if abs(corr_value) > threshold:
        return "HIGH_CORRELATION"
        
    return "LOW_CORRELATION"
