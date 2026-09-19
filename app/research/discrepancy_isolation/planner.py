from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from app.research.reproduction.models import FrozenResearchSpecification
from app.research.discrepancy_isolation.models import (
    DiscrepancyIsolationPlan, IsolationExperiment, IsolationApprovalState
)

class IsolationPlanner:
    
    @staticmethod
    def create_plan(
        analysis_id: str,
        reproduction_id: str,
        baseline: FrozenResearchSpecification,
        candidate_factors: Dict[str, Any]
    ) -> DiscrepancyIsolationPlan:
        
        plan = DiscrepancyIsolationPlan(
            source_reproduction_id=reproduction_id,
            source_discrepancy_analysis_id=analysis_id,
            baseline_specification=baseline,
            as_of=baseline.as_of,
            candidate_factors=list(candidate_factors.keys())
        )
        
        for factor, changed_val in candidate_factors.items():
            baseline_val = getattr(baseline, factor, "UNKNOWN")
            
            # Future bounds check
            if factor == "as_of" and isinstance(changed_val, datetime):
                if changed_val > baseline.as_of:
                    raise ValueError("FUTURE_INFORMATION_VIOLATION")
            
            exp = IsolationExperiment(
                plan_id=plan.plan_id,
                target_factor=factor,
                baseline_value=str(baseline_val),
                changed_value=str(changed_val),
                frozen_inputs_fingerprint="mock_frozen", # In real system, rehash without target
                changed_inputs_fingerprint="mock_changed"
            )
            plan.experiments.append(exp)
            
        plan.approval_state = IsolationApprovalState.REVIEW_REQUIRED
        return plan

    @staticmethod
    def validate_ofat(baseline: FrozenResearchSpecification, experiment_spec: FrozenResearchSpecification, target_factor: str) -> bool:
        """
        Validates exactly ONE factor changed between baseline and experiment,
        and it must be the target_factor.
        """
        b_dict = baseline.dict(exclude={"specification_id", "manifest_id"})
        e_dict = experiment_spec.dict(exclude={"specification_id", "manifest_id"})
        
        diff_count = 0
        diff_keys = []
        for k, v in b_dict.items():
            if e_dict.get(k) != v:
                diff_count += 1
                diff_keys.append(k)
                
        if diff_count == 0:
            return False # INVALID_ISOLATION_EXPERIMENT
            
        if diff_count > 1:
            return False # MULTI_FACTOR_ISOLATION_FORBIDDEN / ISOLATION_BASELINE_VIOLATION
            
        return diff_keys[0] == target_factor
