from typing import List, Optional
from datetime import datetime

from app.core.models import MarketBar, TradingSignal, SignalScore
from app.strategies.base import Strategy
from app.strategies.kronos.engine import KronosEngineWrapper, is_kronos_available
from app.strategies.kronos.config import kronos_config

class KronosStrategy(Strategy):
    """
    Implements the Neural Trade Strategy interface using the Kronos AI model.
    """
    def __init__(self, threshold: float = 0.05, mode: str = "normal"):
        self.threshold = threshold
        self.mode = mode
        self.is_available = is_kronos_available()
        if self.is_available:
            self.engine = KronosEngineWrapper()
        else:
            self.engine = None
        
    @property
    def name(self) -> str:
        return f"Kronos_{self.mode}_{self.threshold}"
        
    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        if not self.is_available or self.engine is None:
            raise RuntimeError("Kronos strategy cannot generate signals because the external Kronos repository is unavailable.")
            
        if len(historical_bars) < kronos_config.lookback:
            return None
            
        predicted_return = self.engine.predict(historical_bars, pred_len=kronos_config.prediction_horizon)
        
        if abs(predicted_return) < self.threshold:
            return None
            
        if self.mode == "normal":
            direction = "LONG" if predicted_return > 0 else "SHORT"
        else: # contrarian
            direction = "SHORT" if predicted_return > 0 else "LONG"
            
        # Neural Trade requires a 0-100 score. Map absolute return to a pseudo-confidence.
        # Here we just supply 100 for a signal that cleared the threshold.
        score = SignalScore(score=100.0, components={"predicted_return": predicted_return})
        
        return TradingSignal(
            symbol=historical_bars[-1].symbol,
            timestamp=historical_bars[-1].timestamp, # The time the signal is generated
            direction=direction,
            strategy=self.name,
            confidence=1.0,
            reason=f"Kronos predicted {predicted_return:.3f}% return (Mode: {self.mode})",
            score=score
        )
        
    def get_parameters(self) -> dict:
        return {
            "threshold": self.threshold,
            "mode": self.mode,
            "lookback": kronos_config.lookback,
            "prediction_horizon": kronos_config.prediction_horizon
        }
