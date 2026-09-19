import hashlib
import logging
from datetime import datetime, timezone
from typing import List, Dict, Optional
from app.research.causality.models import CausalAssessment
from app.research.causal_experiments.models import CausalExperimentDesign, ExperimentApprovalStatus

logger = logging.getLogger(__name__)

class ExperimentDesigner:
    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def design_experiments(self, assessment: CausalAssessment) -> List[CausalExperimentDesign]:
        designs = []
        as_of = datetime.now(timezone.utc)
        
        # 1. Target Confounders (Phase 38)
        for conf in assessment.confounders:
            # Create a design isolating one variable while controlling the others
            if len(conf.overlapping_variables) >= 2:
                focal = conf.overlapping_variables[0]
                controls = {v: "TARGET_CONTROL" for v in conf.overlapping_variables[1:]}
                
                exp_id = self._deterministic_hash(f"design_{assessment.hypothesis_id}_{focal}_{list(controls.keys())[0]}")
                
                design = CausalExperimentDesign(
                    experiment_id=exp_id,
                    hypothesis_id=assessment.hypothesis_id,
                    causal_gap_id=conf.risk_id,
                    research_question=f"Does the mechanism hold when {focal} varies but {list(controls.keys())[0]} is constant?",
                    focal_variable=focal,
                    outcome_variable="strategy_return",
                    candidate_mechanism=assessment.mechanisms[0].description if assessment.mechanisms else "General Association",
                    control_variables=controls,
                    alternative_explanations=[a.description for a in assessment.alternatives],
                    dataset_identity="historical_market_data",
                    historical_start=datetime(2020, 1, 1, tzinfo=timezone.utc),  # Default mock bound
                    historical_end=assessment.as_of,
                    status=ExperimentApprovalStatus.DRAFT,
                    as_of=as_of,
                    created_at=datetime.now(timezone.utc),
                    lineage=assessment.assessment_id
                )
                designs.append(design)
                
        # 2. Target Missing Temporal Ordering or Independent Support
        if not assessment.temporal_ordering_verified or assessment.causal_level.value == "NO_RELATIONSHIP_EVIDENCE":
            exp_id = self._deterministic_hash(f"design_temporal_{assessment.hypothesis_id}")
            
            design = CausalExperimentDesign(
                experiment_id=exp_id,
                hypothesis_id=assessment.hypothesis_id,
                causal_gap_id="gap_temporal_ordering",
                research_question="Does the potential cause chronologically precede the outcome over a verified unseen period?",
                focal_variable="time_precedence",
                outcome_variable="strategy_return",
                candidate_mechanism=assessment.mechanisms[0].description if assessment.mechanisms else "General Association",
                control_variables={"methodology_version": assessment.methodology_version},
                alternative_explanations=[],
                dataset_identity="unseen_forward_data",
                historical_start=assessment.as_of,
                historical_end=as_of, # Simulating a forward step from the original bound
                status=ExperimentApprovalStatus.DRAFT,
                as_of=as_of,
                created_at=datetime.now(timezone.utc),
                lineage=assessment.assessment_id
            )
            designs.append(design)
            
        return designs
