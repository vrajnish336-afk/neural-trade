import pytest
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.core.models import MarketBar
from app.decision.models import TraderDecision
from app.risk.portfolio import PortfolioState
from app.broker.interfaces import IMarketDataEngine, IOrderExecutionAdapter

class DummyMarketDataEngine:
    def get_latest_bar(self, symbol: str) -> Optional[MarketBar]:
        return None
        
    def get_historical_bars(
        self, 
        symbol: str, 
        timeframe: str, 
        start_time: datetime, 
        end_time: Optional[datetime] = None
    ) -> List[MarketBar]:
        return []

class DummyOrderExecutionAdapter:
    def execute_decision(self, decision: TraderDecision) -> Optional[Dict[str, Any]]:
        return None
        
    def get_portfolio_state(self) -> PortfolioState:
        return PortfolioState()

class IncompleteEngine:
    pass

def test_market_data_engine_protocol():
    engine = DummyMarketDataEngine()
    assert isinstance(engine, IMarketDataEngine)
    assert not isinstance(IncompleteEngine(), IMarketDataEngine)

def test_order_execution_adapter_protocol():
    adapter = DummyOrderExecutionAdapter()
    assert isinstance(adapter, IOrderExecutionAdapter)
    assert not isinstance(IncompleteEngine(), IOrderExecutionAdapter)
