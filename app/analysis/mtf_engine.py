from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel, Field
from app.core.models import MarketBar

class MultiTimeframeContext(BaseModel):
    """
    Deterministic context representing multi-timeframe alignment across 1H, 4H, and 1D.
    """
    symbol: str
    as_of_timestamp: datetime
    alignment: str = Field(..., description="ALIGNED_BULLISH, ALIGNED_BEARISH, NEUTRAL, or INSUFFICIENT_DATA")
    h1_trend: str = "UNKNOWN"
    h4_trend: str = "UNKNOWN"
    d1_trend: str = "UNKNOWN"
    is_fresh: bool = True


class MultiTimeframeEngine:
    """
    Engine for synchronizing and aligning 1H, 4H, and 1D market bars 
    without look-ahead bias.
    """

    def _ensure_utc(self, dt: datetime) -> datetime:
        """Converts naive datetime to UTC timezone-aware or returns UTC datetime."""
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def _get_trend(self, bars: List[MarketBar]) -> str:
        """Calculates SMA20 vs SMA50 trend for a given bar series."""
        if len(bars) < 20:
            return "UNKNOWN"
        sma20 = sum(b.close for b in bars[-20:]) / 20.0
        if len(bars) >= 50:
            sma50 = sum(b.close for b in bars[-50:]) / 50.0
            if sma20 > sma50 * 1.01:
                return "BULLISH"
            elif sma20 < sma50 * 0.99:
                return "BEARISH"
            else:
                return "NEUTRAL"
        else:
            # Fallback for shorter series using recent slope
            return "BULLISH" if bars[-1].close > sma20 else "BEARISH"

    def align_timeframes(
        self,
        symbol: str,
        current_timestamp: datetime,
        h1_bars: List[MarketBar],
        h4_bars: Optional[List[MarketBar]] = None,
        d1_bars: Optional[List[MarketBar]] = None
    ) -> MultiTimeframeContext:
        """
        Synchronizes 1H, 4H, and 1D bars strictly as-of current_timestamp.
        Guarantees zero look-ahead data leakage from incomplete/future higher-timeframe bars.
        """
        utc_as_of = self._ensure_utc(current_timestamp)

        # Strict as-of filtering: bar.timestamp <= utc_as_of
        valid_h1 = [b for b in h1_bars if self._ensure_utc(b.timestamp) <= utc_as_of] if h1_bars else []
        valid_h4 = [b for b in h4_bars if self._ensure_utc(b.timestamp) <= utc_as_of] if h4_bars else []
        valid_d1 = [b for b in d1_bars if self._ensure_utc(b.timestamp) <= utc_as_of] if d1_bars else []

        if not valid_h1:
            return MultiTimeframeContext(
                symbol=symbol,
                as_of_timestamp=utc_as_of,
                alignment="INSUFFICIENT_DATA",
                h1_trend="UNKNOWN",
                h4_trend="UNKNOWN",
                d1_trend="UNKNOWN",
                is_fresh=False
            )

        h1_trend = self._get_trend(valid_h1)
        h4_trend = self._get_trend(valid_h4) if valid_h4 else "UNKNOWN"
        d1_trend = self._get_trend(valid_d1) if valid_d1 else "UNKNOWN"

        # Determine alignment
        if h1_trend == "UNKNOWN" and h4_trend == "UNKNOWN" and d1_trend == "UNKNOWN":
            alignment = "INSUFFICIENT_DATA"
        elif h1_trend == "BULLISH" and h4_trend in ("BULLISH", "UNKNOWN") and d1_trend in ("BULLISH", "UNKNOWN"):
            alignment = "ALIGNED_BULLISH"
        elif h1_trend == "BEARISH" and h4_trend in ("BEARISH", "UNKNOWN") and d1_trend in ("BEARISH", "UNKNOWN"):
            alignment = "ALIGNED_BEARISH"
        elif h4_trend == "BULLISH" and d1_trend == "BULLISH":
            alignment = "ALIGNED_BULLISH"
        elif h4_trend == "BEARISH" and d1_trend == "BEARISH":
            alignment = "ALIGNED_BEARISH"
        else:
            alignment = "NEUTRAL"

        return MultiTimeframeContext(
            symbol=symbol,
            as_of_timestamp=utc_as_of,
            alignment=alignment,
            h1_trend=h1_trend,
            h4_trend=h4_trend,
            d1_trend=d1_trend,
            is_fresh=True
        )
