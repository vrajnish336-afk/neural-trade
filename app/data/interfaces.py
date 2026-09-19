from typing import Protocol, List, Optional
from datetime import datetime
from app.core.models import MarketBar

class HistoricalDataProvider(Protocol):
    """Protocol for fetching historical market data."""
    
    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        """Fetch historical OHLCV bars for a given symbol and timeframe."""
        ...


class LiveMarketDataProvider(Protocol):
    """Protocol for subscribing to and receiving live market data."""
    
    def subscribe(self, symbol: str) -> None:
        """Subscribe to live updates for a symbol."""
        ...
        
    def unsubscribe(self, symbol: str) -> None:
        """Unsubscribe from live updates for a symbol."""
        ...
        
    def get_latest_bar(self, symbol: str) -> Optional[MarketBar]:
        """Get the most recent complete market bar for a symbol."""
        ...
