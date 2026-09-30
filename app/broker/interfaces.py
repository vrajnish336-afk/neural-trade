from typing import Protocol, runtime_checkable, List, Optional, Dict, Any
from datetime import datetime
from app.core.models import MarketBar
from app.decision.models import TraderDecision
from app.risk.portfolio import PortfolioState

@runtime_checkable
class IMarketDataEngine(Protocol):
    """Protocol for market-data retrieval abstractions."""
    
    def get_latest_bar(self, symbol: str) -> Optional[MarketBar]:
        """Fetch the most recent complete market bar for a symbol."""
        ...
        
    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        """Fetch historical market bars for a symbol and timeframe."""
        ...


@runtime_checkable
class IOrderExecutionAdapter(Protocol):
    """Protocol for paper-order execution and portfolio state abstractions."""
    
    def execute_decision(self, decision: TraderDecision) -> Optional[Dict[str, Any]]:
        """Process a TraderDecision under paper simulation rules."""
        ...
        
    def get_portfolio_state(self) -> PortfolioState:
        """Retrieve the current paper portfolio state."""
        ...
