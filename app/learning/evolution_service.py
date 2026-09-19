import uuid
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.learning.models import ParameterProposal, ProposalState, ResearchLesson
from app.learning.repository import LearningRepository
from app.research.forward_validation_service import ForwardValidationService
from app.cli.commands.helpers import get_strategy_class

logger = logging.getLogger(__name__)

class EvolutionService:
    """Safely proposes and validates parameter changes based on ranked lessons."""
    
    def __init__(self):
        self.repo = LearningRepository()
        self.validation_svc = ForwardValidationService()
        
    def _validate_safety(self, strategy_name: str, baseline: Dict[str, Any], proposed: Dict[str, Any]) -> bool:
        """
        Safety Gate.
        1. No new parameters.
        2. Types must match.
        3. Simple bounds (e.g., periods > 0).
        """
        for k, v in proposed.items():
            if k not in baseline:
                logger.warning(f"Safety rejected: unknown parameter {k}")
                return False
            if type(v) != type(baseline[k]):
                logger.warning(f"Safety rejected: type mismatch for {k}")
                return False
            
            # Simple bounds check for numericals
            if isinstance(v, (int, float)):
                if v <= 0:  # Assuming most strategy params like periods must be positive
                    logger.warning(f"Safety rejected: non-positive parameter {k}")
                    return False
        return True
        
    def propose_change(self, identity_hash: str, strategy_name: str, proposed_params: Dict[str, Any], supporting_lessons: List[ResearchLesson], reason: str) -> Optional[ParameterProposal]:
        """Propose a parameter change safely. DOES NOT MUTATE ACTIVE PRODUCTION."""
        try:
            strat_cls = get_strategy_class(strategy_name)
            strat_instance = strat_cls()
            baseline = strat_instance.get_parameters()
        except Exception as e:
            logger.error(f"Failed to load strategy {strategy_name}: {e}")
            return None
            
        if not self._validate_safety(strategy_name, baseline, proposed_params):
            return None
            
        proposal = ParameterProposal(
            proposal_id=str(uuid.uuid4()),
            identity_hash=identity_hash,
            strategy=strategy_name,
            baseline_parameters_json=json.dumps(baseline),
            proposed_parameters_json=json.dumps(proposed_params),
            supporting_lesson_ids=[l.lesson_id for l in supporting_lessons],
            reason=reason,
            state=ProposalState.PROPOSED,
            created_at=datetime.utcnow()
        )
        
        self.repo.save_proposal(proposal)
        return proposal
        
    def initiate_validation(self, proposal_id: str, reference_experiment_id: str) -> bool:
        """Initiates a forward validation run for the proposed parameters."""
        proposals = [p for p in self.repo.get_proposals() if p.proposal_id == proposal_id]
        if not proposals: return False
        
        proposal = proposals[0]
        if proposal.state != ProposalState.PROPOSED:
            return False
            
        from app.research.forward_validation_models import FrozenSpecification
        # We need to construct a FrozenSpecification with the overridden configuration
        # For this prototype, we'll dummy some required fields, in production we would 
        # extract them from the baseline or reference experiment.
        frozen_spec = FrozenSpecification(
            strategy=proposal.strategy,
            symbols=["TEST"],  # Typically extracted from original spec
            timeframe="1D",
            historical_end=datetime.utcnow(),
            configuration=proposal.proposed_parameters_json
        )
            
        # Freeze and Validate
        run = self.validation_svc.create_validation_request(
            identity_hash=proposal.identity_hash,
            reference_experiment_id=reference_experiment_id,
            frozen_spec=frozen_spec
        )
        
        if run:
            proposal.state = ProposalState.UNDER_VALIDATION
            proposal.validation_run_id = run.validation_id
            self.repo.save_proposal(proposal)
            return True
            
        return False
