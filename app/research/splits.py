from typing import List, Tuple
from app.core.models import MarketBar
from app.research.models import DataSplit

def split_research_windows(
    bars: List[MarketBar],
    train_pct: float = 0.5,
    val_pct: float = 0.25,
    test_pct: float = 0.25
) -> Tuple[List[MarketBar], List[MarketBar], List[MarketBar], DataSplit, DataSplit, DataSplit]:
    """
    Chronological Train -> Validation -> Test split for out-of-sample testing.
    """
    assert abs(train_pct + val_pct + test_pct - 1.0) < 1e-5, "Percentages must sum to 1.0"
    
    total = len(bars)
    train_end = int(total * train_pct)
    val_end = train_end + int(total * val_pct)
    
    train_bars = bars[:train_end]
    val_bars = bars[train_end:val_end]
    test_bars = bars[val_end:]
    
    symbol = bars[0].symbol if bars else "UNKNOWN"
    
    train_split = DataSplit(
        name="TRAIN", symbol=symbol, 
        start_time=train_bars[0].timestamp if train_bars else None,
        end_time=train_bars[-1].timestamp if train_bars else None,
        row_count=len(train_bars)
    )
    
    val_split = DataSplit(
        name="VALIDATION", symbol=symbol, 
        start_time=val_bars[0].timestamp if val_bars else None,
        end_time=val_bars[-1].timestamp if val_bars else None,
        row_count=len(val_bars)
    )
    
    test_split = DataSplit(
        name="TEST", symbol=symbol, 
        start_time=test_bars[0].timestamp if test_bars else None,
        end_time=test_bars[-1].timestamp if test_bars else None,
        row_count=len(test_bars)
    )
    
    return train_bars, val_bars, test_bars, train_split, val_split, test_split
