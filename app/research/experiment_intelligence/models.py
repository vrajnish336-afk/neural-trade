from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum

class CompatibilityStatus(str, Enum):
    DIRECTLY_COMPARABLE = "DIRECTLY_COMPARABLE"
    PARTIALLY_COMPARABLE = "PARTIALLY_COMPARABLE"
    NOT_COMPARABLE = "NOT_COMPARABLE"

class EvidenceStrength(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    MIXED = "MIXED"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_AVAILABLE = "NOT_AVAILABLE"

class ExperimentEvidenceProfile(BaseModel):
    experiment_id: str
    code_hash: str
    dataset_identity: str
    parameters: Dict[str, Any]
    
    # Categories
    performance_return_pct: float
    performance_drawdown_pct: float
    performance_profit_factor: float
    
    generalization_forward_return: Optional[float] = None
    
    robustness_seed_stability: EvidenceStrength
    robustness_cost_resilience: EvidenceStrength
    robustness_parameter_sensitivity: EvidenceStrength
    robustness_monte_carlo: EvidenceStrength
    
    coverage_sample_size: int
    coverage_regimes_tested: int
    coverage_is_adequate: bool
    
    reproducibility_deterministic: bool
    
    conflicts: List[str] = Field(default_factory=list)
    limitations: List[str] = Field(default_factory=list)
    
    overall_strength: EvidenceStrength
    
class ExperimentComparison(BaseModel):
    comparison_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    methodology_version: str = "v1"
    
    experiment_a_id: str
    experiment_b_id: str
    
    compatibility: CompatibilityStatus
    compatibility_notes: List[str] = Field(default_factory=list)
    
    profile_a: ExperimentEvidenceProfile
    profile_b: ExperimentEvidenceProfile
    
    robustness_winner: Optional[str] = None
    performance_winner: Optional[str] = None
    coverage_winner: Optional[str] = None
    
    final_research_assessment: EvidenceStrength
    recommendation: str
    conflicts_detected: List[str] = Field(default_factory=list)
