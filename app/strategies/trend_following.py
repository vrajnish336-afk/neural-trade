from typing import List, Optional
import pandas as pd
from app.core.models import MarketBar, TradingSignal
from app.strategies.base import Strategy, bars_to_dataframe
from app.analysis.indicators import calculate_sma, calculate_atr

class TrendFollowingStrategy(Strategy):
    """
    A simple deterministic moving-average crossover strategy.
    """
    
    def __init__(self, fast_period: int = 10, slow_period: int = 30):
        self.fast_period = fast_period
        self.slow_period = slow_period
        
    @property
    def name(self) -> str:
        return f"TrendFollowing_{self.fast_period}_{self.slow_period}"

    def get_parameters(self) -> dict:
        return {
            "fast_period": self.fast_period,
            "slow_period": self.slow_period
        }

    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        if len(historical_bars) < self.slow_period:
            return None
            
        df = bars_to_dataframe(historical_bars)
        fast_sma = calculate_sma(df['close'], self.fast_period)
        slow_sma = calculate_sma(df['close'], self.slow_period)
        
        atr = calculate_atr(df['high'], df['low'], df['close'], 14)
        current_atr = atr.iloc[-1]
        
        current_fast = fast_sma.iloc[-1]
        current_slow = slow_sma.iloc[-1]
        prev_fast = fast_sma.iloc[-2]
        prev_slow = slow_sma.iloc[-2]
        
        if pd.isna(current_fast) or pd.isna(current_slow) or pd.isna(current_atr):
            return None
            
        last_bar = historical_bars[-1]
        
        # Golden Cross -> LONG
        if current_fast > current_slow and prev_fast <= prev_slow:
            sl = max(0.01, last_bar.close - (current_atr * 2))
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="LONG",
                strategy=self.name,
                confidence=0.8,
                entry_price=last_bar.close,
                stop_loss=sl,
                take_profit=last_bar.close + (current_atr * 4),
                reason="Fast SMA crossed above Slow SMA"
            )
            
        # Death Cross -> SHORT
        if current_fast < current_slow and prev_fast >= prev_slow:
            tp = max(0.01, last_bar.close - (current_atr * 4))
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="SHORT",
                strategy=self.name,
                confidence=0.8,
                entry_price=last_bar.close,
                stop_loss=last_bar.close + (current_atr * 2),
                take_profit=tp,
                reason="Fast SMA crossed below Slow SMA"
            )
            
        return None
