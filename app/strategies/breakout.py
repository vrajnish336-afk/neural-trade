from typing import List, Optional
import pandas as pd
from app.core.models import MarketBar, TradingSignal
from app.strategies.base import Strategy, bars_to_dataframe
from app.analysis.indicators import calculate_average_volume, calculate_atr

class BreakoutStrategy(Strategy):
    """
    Historical rolling high/low breakout strategy.
    """
    def __init__(self, lookback_period: int = 20, volume_period: int = 20):
        self.lookback_period = lookback_period
        self.volume_period = volume_period
        
    @property
    def name(self) -> str:
        return f"Breakout_{self.lookback_period}"

    def get_parameters(self) -> dict:
        return {
            "lookback_period": self.lookback_period,
            "volume_period": self.volume_period
        }

    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        min_bars = max(self.lookback_period, self.volume_period, 14) + 1
        if len(historical_bars) < min_bars:
            return None
            
        df = bars_to_dataframe(historical_bars)
        
        rolling_high = df['high'].shift(1).rolling(window=self.lookback_period).max()
        rolling_low = df['low'].shift(1).rolling(window=self.lookback_period).min()
        avg_volume = calculate_average_volume(df['volume'].shift(1), self.volume_period)
        atr = calculate_atr(df['high'], df['low'], df['close'], 14)
        
        last_bar = historical_bars[-1]
        current_close = last_bar.close
        current_volume = last_bar.volume
        
        prev_high = rolling_high.iloc[-1]
        prev_low = rolling_low.iloc[-1]
        prev_avg_vol = avg_volume.iloc[-1]
        current_atr = atr.iloc[-1]
        
        if pd.isna(prev_high) or pd.isna(prev_low) or pd.isna(prev_avg_vol) or pd.isna(current_atr):
            return None
            
        if current_close > prev_high and current_volume > prev_avg_vol:
            sl = max(0.01, current_close - (current_atr * 2))
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="LONG",
                strategy=self.name,
                confidence=0.7,
                entry_price=current_close,
                stop_loss=sl,
                take_profit=current_close + (current_atr * 4),
                reason="Price broke above previous high with volume"
            )
            
        # SHORT Breakout
        elif current_close < prev_low and current_volume > prev_avg_vol:
            tp = max(0.01, current_close - (current_atr * 4))
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="SHORT",
                strategy=self.name,
                confidence=0.7,
                entry_price=current_close,
                stop_loss=current_close + (current_atr * 2),
                take_profit=tp,
                reason="Price broke below previous low with volume"
            )
            
        return None
