from typing import Dict, List
import pandas as pd

import numpy as np

class PortfolioComposer:
    
    @staticmethod
    def validate_weights(weights: Dict[str, float]) -> bool:
        """
        Validates weights are finite, non-negative, and sum to 1.0 (with small float tolerance).
        No silent normalization.
        """
        if not weights:
            return False
            
        total = 0.0
        for w in weights.values():
            if w < 0 or pd.isna(w) or np.isinf(w):
                return False
            total += w
            
        if abs(total - 1.0) > 1e-5:
            return False
            
        return True

    @staticmethod
    def align_series(series_map: Dict[str, pd.Series]) -> pd.DataFrame:
        """
        Takes a map of candidate IDs to their equity or return series and aligns them 
        on a common chronological boundary (inner join on index to avoid fabricating data).
        """
        if not series_map:
            return pd.DataFrame()
            
        common_start = max(s.index.min() for s in series_map.values())
        common_end = min(s.index.max() for s in series_map.values())
            
        df = pd.DataFrame(series_map)
        
        # Slice to strict chron boundary first
        df = df.loc[common_start:common_end]
        
        # Forward-fill any internal gaps (e.g. illiquid periods inside the common bound)
        df = df.ffill()
        df = df.dropna()
        return df

    @staticmethod
    def construct_portfolio_returns(aligned_returns: pd.DataFrame, weights: Dict[str, float]) -> pd.Series:
        """
        Computes portfolio return series given strict weights.
        Assumes return series already net of costs (to avoid double-counting).
        """
        # Ensure ordering
        cols = list(aligned_returns.columns)
        w_array = [weights[c] for c in cols]
        
        port_return = (aligned_returns * w_array).sum(axis=1)
        return port_return
