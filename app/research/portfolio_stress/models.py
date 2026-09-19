from enum import Enum
from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
import uuid
from datetime import datetime

class PortfolioStressScenarioType(str, Enum):
    BASELINE = "BASELINE"
    CORRELATED_FAILURE = "CORRELATED_FAILURE"
    SYNCHRONIZED_DRAWDOWN = "SYNCHRONIZED_DRAWDOWN"
    REGIME_SHOCK = "REGIME_SHOCK"
    COST_SHOCK = "COST_SHOCK"
    SLIPPAGE_SHOCK = "SLIPPAGE_SHOCK"
    COMMISSION_SHOCK = "COMMISSION_SHOCK"
    MISSING_CANDIDATE = "MISSING_CANDIDATE"
    CANDIDATE_DEGRADATION = "CANDIDATE_DEGRADATION"
    TIMEFRAME_FAILURE = "TIMEFRAME_FAILURE"
    TEMPORAL_BREAK = "TEMPORAL_BREAK"
    DATA_GAP = "DATA_GAP"
    CONCENTRATION_SHOCK = "CONCENTRATION_SHOCK"
    COMBINED_STRESS = "COMBINED_STRESS"

class StressSeverity(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class PortfolioFailureAssessment(str, Enum):
    NO_MATERIAL_FAILURE_DETECTED = "NO_MATERIAL_FAILURE_DETECTED"
    CORRELATED_FAILURE = "CORRELATED_FAILURE"
    SYNCHRONIZED_DOWNSIDE = "SYNCHRONIZED_DOWNSIDE"
    REGIME_FRAGILITY = "REGIME_FRAGILITY"
    COST_FRAGILITY = "COST_FRAGILITY"
    SINGLE_CANDIDATE_DEPENDENCY = "SINGLE_CANDIDATE_DEPENDENCY"
    TIMEFRAME_CONCENTRATION = "TIMEFRAME_CONCENTRATION"
    TEMPORAL_INSTABILITY = "TEMPORAL_INSTABILITY"
    DATA_INTEGRITY_FAILURE = "DATA_INTEGRITY_FAILURE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    MULTIPLE_FAILURE_MODES = "MULTIPLE_FAILURE_MODES"

class PortfolioResilienceAssessment(str, Enum):
    ROBUST_UNDER_TESTED_SCENARIOS = "ROBUST_UNDER_TESTED_SCENARIOS"
    CONDITIONALLY_RESILIENT = "CONDITIONALLY_RESILIENT"
    FRAGILE = "FRAGILE"
    HIGHLY_FRAGILE = "HIGHLY_FRAGILE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

class PortfolioStressScenario(BaseModel):
    scenario_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    scenario_type: PortfolioStressScenarioType
    scenario_parameters: Dict[str, Any]
    dataset_identity: str
    time_boundary_start: datetime
    time_boundary_end: datetime
    cost_model: dict
    risk_model: dict
    methodology_version: str = "v1"
    seed: int = 42
    as_of: datetime
    is_synthetic: bool = True

class PortfolioStressResult(BaseModel):
    result_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    portfolio_id: str
    scenario_id: str
    scenario_type: PortfolioStressScenarioType
    baseline_reference_id: str
    stress_assessment: PortfolioFailureAssessment
    severity: StressSeverity
    resilience: PortfolioResilienceAssessment
    
    affected_candidates: List[str]
    drawdown_metrics: Dict[str, float]
    correlation_metrics: Dict[str, float]
    cost_metrics: Dict[str, float]
    
    sample_size: int
    limitations: List[str]
    as_of: datetime
    methodology_version: str = "v1"
    created_at: datetime = Field(default_factory=datetime.utcnow)
