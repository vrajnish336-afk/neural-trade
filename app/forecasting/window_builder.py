from typing import List, Tuple
from app.core.models import MarketBar

class WindowBuilder:
    """Deterministically slices data, guaranteeing zero look-ahead."""
    
    @staticmethod
    def build_input_window(bars: List[MarketBar], window_size: int) -> List[MarketBar]:
        """
        Extracts exactly `window_size` bars up to the most recent observation.
        Raises ValueError if insufficient data or out of order.
        """
        if len(bars) < window_size:
            raise ValueError(f"Insufficient data. Required {window_size}, got {len(bars)}.")
            
        window = bars[-window_size:]
        
        # Validate chronologically sorted
        for i in range(1, len(window)):
            if window[i].timestamp <= window[i-1].timestamp:
                raise ValueError("Bars are not strictly chronologically sorted.")
                
            if window[i].close <= 0:
                raise ValueError("Invalid negative or zero close price detected.")
                
        return window
        
    @staticmethod
    def split_for_evaluation(bars: List[MarketBar], forecast_start_idx: int, horizon: int) -> Tuple[List[MarketBar], List[MarketBar]]:
        """
        Safely splits a list of bars into history and strict future.
        Used for backtesting/evaluating the forecaster.
        """
        history = bars[:forecast_start_idx]
        future = bars[forecast_start_idx:forecast_start_idx + horizon]
        return history, future
