from typing import List, Tuple
from app.core.models import MarketBar

def split_walk_forward_windows(
    bars: List[MarketBar], 
    num_windows: int = 3, 
    train_ratio: float = 0.7
) -> List[Tuple[str, List[MarketBar], List[MarketBar]]]:
    """
    Splits data into chronological, non-overlapping windows.
    Returns: List of (window_name, train_bars, test_bars)
    Does NOT leak future data. Each window is strictly strictly chronological.
    """
    if len(bars) < num_windows * 20: # Arbitrary minimum required size for splitting
        return []
        
    window_size = len(bars) // num_windows
    windows = []
    
    for i in range(num_windows):
        start_idx = i * window_size
        end_idx = start_idx + window_size if i < num_windows - 1 else len(bars)
        
        window_bars = bars[start_idx:end_idx]
        train_len = int(len(window_bars) * train_ratio)
        
        train_bars = window_bars[:train_len]
        test_bars = window_bars[train_len:]
        
        windows.append((f"Window {i+1}", train_bars, test_bars))
        
    return windows
