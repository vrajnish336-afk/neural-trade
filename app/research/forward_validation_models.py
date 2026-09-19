from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import json
import hashlib

class ForwardValidationState(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    BLOCKED = "BLOCKED"

class ForwardDriftState(str, Enum):
    STABLE = "STABLE"
    DEGRADED = "DEGRADED"
    SIGNIFICANTLY_DEGRADED = "SIGNIFICANTLY_DEGRADED"
    INSUFFICIENT_COMPARISON = "INSUFFICIENT_COMPARISON"
    UNRESOLVED = "UNRESOLVED"

class FrozenSpecification(BaseModel):
    """Immutable representation of the exact configuration to be validated."""
    strategy: str
    symbols: List[str]
    timeframe: str
    historical_end: datetime
    configuration: str = "default" # Placeholder for future dynamic param grids
    cost_config: Dict[str, float] = Field(default_factory=lambda: {"commission_rate": 0.001, "slippage_rate": 0.0005})
    starting_capital: float = 10000.0
    random_seed: int = 42

    def get_hash(self) -> str:
        """Deterministic hash of the frozen spec."""
        # Sort symbols for stability
        sorted_symbols = sorted(self.symbols)
        # Create a stable string representation
        data = f"{self.strategy}|{','.join(sorted_symbols)}|{self.timeframe}|{self.historical_end.isoformat()}|{self.configuration}|{self.cost_config['commission_rate']}|{self.cost_config['slippage_rate']}|{self.starting_capital}|{self.random_seed}"
        return hashlib.sha256(data.encode('utf-8')).hexdigest()

class ForwardValidationRun(BaseModel):
    validation_id: str
    identity_hash: str
    reference_experiment_id: str
    
    frozen_specification: FrozenSpecification
    dataset_identity: Optional[Dict[str, Any]] = None
    
    forward_start: Optional[datetime] = None
    forward_end: Optional[datetime] = None
    
    state: ForwardValidationState = ForwardValidationState.CREATED
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    result_experiment_id: Optional[str] = None
    failure_reason: Optional[str] = None
    drift_state: Optional[ForwardDriftState] = None
