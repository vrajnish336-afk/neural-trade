from app.strategies.ensemble import StrategyEnsemble
from app.strategies.base import Strategy
from app.core.models import TradingSignal, MarketRegimeResult, MarketBar
from datetime import datetime, timezone

class MockStrategy(Strategy):
    def __init__(self, name, direction):
        self._name = name
        self.direction = direction
        
    @property
    def name(self): return self._name
    
    def generate_signal(self, bars):
        if self.direction is None:
            return None
        return TradingSignal(
            symbol="BTC", timestamp=datetime.now(timezone.utc), direction=self.direction, strategy=self.name,
            confidence=1.0, entry_price=100, reason="test", stop_loss=90, take_profit=110
        )

def test_ensemble_conflict_wait():
    s1 = MockStrategy("S1", "LONG")
    s2 = MockStrategy("S2", "SHORT")
    ensemble = StrategyEnsemble([s1, s2])
    
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    signal = ensemble.evaluate(bars, regime) 
    
    assert signal is None # Conflict -> Wait
    
def test_ensemble_agreement_and_scoring():
    s1 = MockStrategy("S1", "LONG")
    s2 = MockStrategy("S2", "LONG")
    ensemble = StrategyEnsemble([s1, s2])
    
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    signal = ensemble.evaluate(bars, regime)
    
    assert signal is not None
    assert signal.direction == "LONG"
    # Score: base (50) + TRENDING_UP LONG (40) = 90
    assert signal.score.score == 90.0
    
def test_ensemble_regime_veto():
    s1 = MockStrategy("S1", "LONG")
    ensemble = StrategyEnsemble([s1])
    
    regime = MarketRegimeResult(regime="TRENDING_DOWN", confidence=1.0)
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    signal = ensemble.evaluate(bars, regime)
    
    # LONG in TRENDING_DOWN = 0 points for regime alignment = veto
    assert signal is None
