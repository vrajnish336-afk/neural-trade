from typing import List, Optional
import pandas as pd
from app.core.models import MarketBar, TradingSignal
from app.strategies.base import Strategy, bars_to_dataframe
from app.analysis.indicators import calculate_sma, calculate_volatility, calculate_atr

class MeanReversionStrategy(Strategy):
    """
    Mean-reversion baseline using deviation from a moving average.
    """
    def __init__(self, sma_period: int = 20, deviation_multiplier: float = 2.0):
        self.sma_period = sma_period
        self.deviation_multiplier = deviation_multiplier
        
    @property
    def name(self) -> str:
        return f"MeanReversion_{self.sma_period}"

    def get_parameters(self) -> dict:
        return {
            "sma_period": self.sma_period,
            "deviation_multiplier": self.deviation_multiplier
        }

    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        if len(historical_bars) < max(self.sma_period, 14):
            return None
            
        df = bars_to_dataframe(historical_bars)
        sma = calculate_sma(df['close'], self.sma_period)
        
        std_dev = df['close'].rolling(window=self.sma_period).std()
        atr = calculate_atr(df['high'], df['low'], df['close'], 14)
        
        last_bar = historical_bars[-1]
        current_close = last_bar.close
        
        current_sma = sma.iloc[-1]
        current_std = std_dev.iloc[-1]
        current_atr = atr.iloc[-1]
        
        if pd.isna(current_sma) or pd.isna(current_std) or current_std == 0 or pd.isna(current_atr):
            return None
            
        upper_band = current_sma + (self.deviation_multiplier * current_std)
        lower_band = current_sma - (self.deviation_multiplier * current_std)
        
        if current_close < lower_band:
            sl = max(0.01, current_close - (current_atr * 1.5))
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="LONG",
                strategy=self.name,
                confidence=0.7,
                entry_price=current_close,
                stop_loss=sl,
                take_profit=current_sma,
                reason="Price is significantly below mean"
            )
            
        if current_close > upper_band:
            return TradingSignal(
                symbol=last_bar.symbol,
                timestamp=last_bar.timestamp,
                direction="SHORT",
                strategy=self.name,
                confidence=0.6,
                entry_price=current_close,
                stop_loss=current_close + (current_atr * 1.5),
                take_profit=current_sma,
                reason="Price is significantly above mean"
            )
            
        return None
