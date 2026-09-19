from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
from datetime import datetime

class RejectionReason(str, Enum):
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NO_STRATEGY_SIGNAL = "NO_STRATEGY_SIGNAL"
    STRATEGY_CONFLICT = "STRATEGY_CONFLICT"
    REGIME_VETO = "REGIME_VETO"
    NEGATIVE_NEWS_FILTER = "NEGATIVE_NEWS_FILTER"
    ANOMALY_FILTER = "ANOMALY_FILTER"
    FAKEOUT_FILTER = "FAKEOUT_FILTER"
    LOW_SIGNAL_SCORE = "LOW_SIGNAL_SCORE"
    MISSING_SL_OR_ENTRY = "MISSING_SL_OR_ENTRY"
    RISK_LIMIT = "RISK_LIMIT"
    DAILY_LOSS_LIMIT = "DAILY_LOSS_LIMIT"
    LOSS_STREAK_COOLDOWN = "LOSS_STREAK_COOLDOWN"
    POSITION_LIMIT = "POSITION_LIMIT"
    INSUFFICIENT_CAPITAL = "INSUFFICIENT_CAPITAL"
    PORTFOLIO_EXPOSURE_LIMIT = "PORTFOLIO_EXPOSURE_LIMIT"
    SYMBOL_EXPOSURE_LIMIT = "SYMBOL_EXPOSURE_LIMIT"
    STRATEGY_EXPOSURE_LIMIT = "STRATEGY_EXPOSURE_LIMIT"
    AGGREGATE_RISK_LIMIT = "AGGREGATE_RISK_LIMIT"
    INSUFFICIENT_CORRELATION_DATA = "INSUFFICIENT_CORRELATION_DATA"
    OTHER = "OTHER"

class SignalAuditRecord(BaseModel):
    timestamp: datetime
    symbol: str
    regime: str
    strategy_votes: Dict[str, str] = {}  # e.g., {"TrendFollowing": "LONG", "Breakout": "HOLD"}
    ensemble_decision: Optional[str] = None
    signal_score: Optional[float] = None
    sentiment: Optional[str] = None
    fakeout_risk: Optional[str] = None
    final_decision: str
    rejection_reason: Optional[RejectionReason] = None
