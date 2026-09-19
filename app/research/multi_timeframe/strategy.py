import logging
from typing import List, Optional, Callable
from datetime import datetime

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence
from app.strategies.base import Strategy
from app.research.multi_timeframe.models import TimeframeHierarchy, MultiTimeframeContext
from app.research.multi_timeframe.builder import MultiTimeframeContextBuilder

logger = logging.getLogger(__name__)

class MultiTimeframeStrategy(Strategy):
    """
    Composite strategy that enforces HTF -> MTF -> LTF cascading logic.
    Uses the builder to strictly prevent lookahead.
    """
    def __init__(
        self,
        name: str,
        hierarchy: TimeframeHierarchy,
        dataset_identity: str,
        as_of: datetime,
        htf_logic: Callable[[MultiTimeframeContext, List[MarketBar]], bool],
        mtf_logic: Optional[Callable[[MultiTimeframeContext, List[MarketBar]], bool]] = None,
        ltf_logic: Optional[Callable[[MultiTimeframeContext, List[MarketBar]], Optional[TradingSignal]]] = None,
        parameters: Optional[dict] = None
    ):
        self._name = name
        self.hierarchy = hierarchy
        self.builder = MultiTimeframeContextBuilder(hierarchy, dataset_identity, as_of)
        self.htf_logic = htf_logic
        self.mtf_logic = mtf_logic
        self.ltf_logic = ltf_logic
        self.parameters = parameters or {}
        
    @property
    def name(self) -> str:
        return self._name
        
    def get_parameters(self) -> dict:
        return self.parameters

    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        # Standard signature for backwards compatibility. Regime and intelligence are ignored directly here 
        # unless passed down. The Engine ensemble expects evaluate() to be called.
        pass

    def evaluate(self, historical_bars: List[MarketBar], regime: Optional[MarketRegimeResult] = None, intelligence: Optional[MarketIntelligence] = None) -> Optional[TradingSignal]:
        if not historical_bars:
            return None
            
        context = self.builder.build_context(historical_bars)
        if not context:
            return None
            
        # HTF Check
        if not self.htf_logic(context, historical_bars):
            return None
            
        # MTF Check
        if self.mtf_logic:
            if not context.mtf_state:
                return None
            if not self.mtf_logic(context, historical_bars):
                return None
                
        # LTF / Final Signal Generation
        if self.ltf_logic:
            signal = self.ltf_logic(context, historical_bars)
            if signal:
                signal.regime = regime
                signal.intelligence = intelligence
                signal.strategy = self.name
            return signal
            
        return None
