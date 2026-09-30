import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ALLOWED_BASE_STRATEGIES = {"BreakoutStrategy", "TrendFollowingStrategy", "MeanReversionStrategy"}

class ReplicatedStrategyCandidate(BaseModel):
    """
    Offline research candidate representation for a replicated strategy variant.
    """
    candidate_id: str
    base_strategy: str
    parameters: Dict[str, Any]
    description: str
    status: str = Field("RESEARCH_ONLY", description="Always RESEARCH_ONLY; never deployed to live or paper brokers")
    created_at: datetime


class ResearchReplicationService:
    """
    Service for generating and validating offline strategy replication variants 
    within isolated research boundaries.
    """
    
    def __init__(self):
        self._candidates: Dict[str, ReplicatedStrategyCandidate] = {}

    def create_candidate(
        self,
        base_strategy: str,
        parameters: Dict[str, Any],
        description: str
    ) -> ReplicatedStrategyCandidate:
        """
        Creates and validates a new offline research strategy candidate.
        """
        if base_strategy not in ALLOWED_BASE_STRATEGIES:
            raise ValueError(f"Invalid base strategy '{base_strategy}'. Allowed: {ALLOWED_BASE_STRATEGIES}")

        if not isinstance(parameters, dict):
            raise ValueError("Parameters must be a dictionary of configuration key-values.")

        # Validate parameter safety
        for k, v in parameters.items():
            if not isinstance(k, str) or k.startswith("__"):
                raise ValueError(f"Invalid parameter key '{k}'.")
            if not isinstance(v, (int, float, str, bool, list)):
                raise ValueError(f"Unsupported parameter type for key '{k}': {type(v)}")

        cid = f"rep_{base_strategy.lower()}_{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        
        candidate = ReplicatedStrategyCandidate(
            candidate_id=cid,
            base_strategy=base_strategy,
            parameters=parameters,
            description=description,
            status="RESEARCH_ONLY",
            created_at=now
        )
        
        self._candidates[cid] = candidate
        logger.info(f"Registered offline research strategy candidate: {cid}")
        return candidate

    def get_candidate(self, candidate_id: str) -> Optional[ReplicatedStrategyCandidate]:
        """Retrieves a registered research candidate by ID."""
        return self._candidates.get(candidate_id)

    def list_candidates(self) -> List[ReplicatedStrategyCandidate]:
        """Returns all registered research candidates."""
        return list(self._candidates.values())

    def execute_live(self, *args, **kwargs) -> None:
        """Explicit safety barrier blocking any live order execution."""
        raise PermissionError("Replicated strategies are restricted strictly to offline research graphs and cannot execute live trades.")

    def place_order(self, *args, **kwargs) -> None:
        """Explicit safety barrier blocking any order placement."""
        raise PermissionError("Replicated strategies are restricted strictly to offline research graphs and cannot place orders.")
