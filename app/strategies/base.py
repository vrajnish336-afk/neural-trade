from typing import List, Protocol, Optional
import pandas as pd
from app.core.models import MarketBar, TradingSignal

class Strategy(Protocol):
    """Protocol defining a standard trading strategy."""
    
    @property
    def name(self) -> str:
        """Name of the strategy."""
        ...
        
    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        """
        Analyzes historical data and potentially generates a trading signal.
        Should never use future data.
        Returns None if no signal is generated.
        """
        ...
        
    def get_parameters(self) -> dict:
        """Returns the actual instantiated strategy configuration parameters."""
        ...
        
def bars_to_dataframe(bars: List[MarketBar]) -> pd.DataFrame:
    """Helper to convert bars to pandas DataFrame for vectorized analysis."""
    if not bars:
        return pd.DataFrame()
        
    df = pd.DataFrame([{
        "timestamp": b.timestamp,
        "open": b.open,
        "high": b.high,
        "low": b.low,
        "close": b.close,
        "volume": b.volume
    } for b in bars])
    
    df.set_index("timestamp", inplace=True)
    return df
