import logging
from typing import List, Optional, Any, Dict
from datetime import datetime, timezone
from app.core.models import MarketBar
from app.decision.models import TraderDecision
from app.risk.portfolio import PortfolioState
from app.execution.streaming_paper_broker import StreamingPaperBroker
from app.broker.interfaces import IMarketDataEngine, IOrderExecutionAdapter

logger = logging.getLogger(__name__)

class ReadOnlyLiveMarketDataAdapter(IMarketDataEngine):
    """
    Read-only market data adapter that wraps underlying data providers (CSV/CCXT).
    Guarantees zero order execution or capital mutation capabilities.
    """
    
    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider
        
    def get_latest_bar(self, symbol: str) -> Optional[MarketBar]:
        """Fetch the most recent complete market bar for a symbol."""
        if not self.provider:
            logger.warning("No data provider configured for ReadOnlyLiveMarketDataAdapter.")
            return None
        try:
            # 1. Native get_latest_bar
            if hasattr(self.provider, "get_latest_bar"):
                return self.provider.get_latest_bar(symbol)
                
            # 2. CCXT support
            elif hasattr(self.provider, "fetch_ohlcv"):
                ohlcv = self.provider.fetch_ohlcv(symbol, '1h', limit=1)
                if not ohlcv or len(ohlcv) == 0:
                    return None
                
                b = ohlcv[-1]
                if len(b) < 6:
                    raise ValueError(f"Malformed OHLCV data from CCXT for {symbol}")
                    
                ts = datetime.fromtimestamp(b[0] / 1000.0, tz=timezone.utc)
                return MarketBar(
                    symbol=symbol,
                    timestamp=ts,
                    open=float(b[1]),
                    high=float(b[2]),
                    low=float(b[3]),
                    close=float(b[4]),
                    volume=float(b[5])
                )
                
            # 3. Fallback to historical
            elif hasattr(self.provider, "get_historical_bars"):
                bars = self.provider.get_historical_bars(
                    symbol=symbol, 
                    timeframe="1h", 
                    start_time=datetime.min.replace(tzinfo=timezone.utc)
                )
                return bars[-1] if bars else None
        except Exception as e:
            logger.error(f"Error fetching latest bar for {symbol}: {e}")
            return None
            
        return None

    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        """Fetch historical market bars for a symbol and timeframe."""
        if not self.provider:
            logger.warning("No data provider configured for ReadOnlyLiveMarketDataAdapter.")
            return []
        try:
            # 1. CCXT support
            if hasattr(self.provider, "fetch_ohlcv"):
                since = int(start_time.timestamp() * 1000)
                ohlcv = self.provider.fetch_ohlcv(symbol, timeframe, since=since, limit=1000)
                
                if not isinstance(ohlcv, list):
                    raise ValueError(f"Expected list of OHLCV data, got {type(ohlcv)}")
                
                bars = []
                for b in ohlcv:
                    if len(b) < 6:
                        raise ValueError(f"Malformed OHLCV data from CCXT for {symbol}: {b}")
                    
                    ts = datetime.fromtimestamp(b[0] / 1000.0, tz=timezone.utc)
                    if end_time and ts > end_time:
                        continue
                    bars.append(MarketBar(
                        symbol=symbol,
                        timestamp=ts,
                        open=float(b[1]),
                        high=float(b[2]),
                        low=float(b[3]),
                        close=float(b[4]),
                        volume=float(b[5])
                    ))
                return bars
                
            # 2. Existing internal provider support
            elif hasattr(self.provider, "get_historical_bars"):
                return self.provider.get_historical_bars(
                    symbol=symbol, 
                    timeframe=timeframe, 
                    start_time=start_time, 
                    end_time=end_time
                )
        except Exception as e:
            logger.error(f"Error fetching historical bars for {symbol}: {e}")
            return []
            
        return []

    def place_order(self, *args, **kwargs) -> None:
        """Explicit safety gate blocking any order placement attempts."""
        raise PermissionError("ReadOnlyLiveMarketDataAdapter is strictly read-only and prohibits order execution.")

    def submit_order(self, *args, **kwargs) -> None:
        """Explicit safety gate blocking any order submission attempts."""
        raise PermissionError("ReadOnlyLiveMarketDataAdapter is strictly read-only and prohibits order submission.")
        
    def cancel_order(self, *args, **kwargs) -> None:
        """Explicit safety gate blocking any order cancellation attempts."""
        raise PermissionError("ReadOnlyLiveMarketDataAdapter is strictly read-only and prohibits order cancellation.")

class PaperExecutionAdapter(IOrderExecutionAdapter):
    """
    Paper execution adapter delegating strictly to StreamingPaperBroker.
    Preserves paper simulation rules, RiskEngine authority, and idempotency.
    """
    
    def __init__(self, streaming_broker: StreamingPaperBroker):
        self.streaming_broker = streaming_broker
        
    def execute_decision(
        self, 
        decision: TraderDecision, 
        position_size: float = 1.0, 
        stop_loss: Optional[float] = None, 
        take_profit: Optional[float] = None
    ) -> bool:
        """Delegate decision execution safely to StreamingPaperBroker."""
        return self.streaming_broker.execute_decision(
            decision, 
            position_size=position_size, 
            stop_loss=stop_loss, 
            take_profit=take_profit
        )
        
    def get_portfolio_state(self) -> PortfolioState:
        """Delegate portfolio state retrieval to StreamingPaperBroker."""
        return self.streaming_broker.get_realtime_portfolio()
