from datetime import datetime
from typing import Optional, List, Dict
from pydantic import BaseModel, Field

class ScenarioAnalysis(BaseModel):
    """Explains potential market scenarios bounded by evidence."""
    bullish_scenario: str = Field(description="Bullish continuation or reversal conditions")
    bearish_scenario: str = Field(description="Bearish continuation or reversal conditions")
    neutral_scenario: str = Field(description="Range-bound or high-volatility sideways conditions")

class TraderDecision(BaseModel):
    """
    Deterministic, explainable decision model representing the final output 
    of the Trader Decision Loop.
    """
    symbol: str
    timestamp: datetime
    data_freshness: str = Field(description="FRESH, STALE, or INSUFFICIENT")
    regime: str
    trend_context: str
    volatility_context: str
    multi_timeframe_alignment: str
    portfolio_correlation: str = "UNKNOWN"
    strategy_signals: List[Dict[str, str]]
    forecast_direction: str
    forecast_uncertainty: float
    world_context: str
    scenario_analysis: ScenarioAnalysis
    main_risks: List[str]
    invalidation_conditions: List[str]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)
    decision: str = Field(description="LONG, SHORT, WAIT, or NO TRADE")
    evaluated_price: float = Field(description="The exact price of the asset at the evaluated timestamp")
    risk_gate_approved: bool
    risk_gate_reason: Optional[str] = None
    paper_execution_eligible: bool
    strategy_weighting_audit: Optional[Dict[str, dict]] = None
