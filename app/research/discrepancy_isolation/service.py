from typing import List
from app.research.discrepancy_isolation.models import (
    DiscrepancyIsolationPlan, IsolationApprovalState, IsolationStatus,
    IsolationComparison, RevalidationDecision, RevalidationDecisionState
)
from app.research.reproduction.models import FrozenResearchSpecification, ComparisonState

class IsolationService:
    
    @staticmethod
    def execute_plan(plan: DiscrepancyIsolationPlan) -> DiscrepancyIsolationPlan:
        if plan.approval_state != IsolationApprovalState.APPROVED_FOR_RESEARCH:
            raise ValueError("Plan must be APPROVED_FOR_RESEARCH before execution.")
            
        if len(plan.experiments) > plan.max_experiments:
            plan.status = IsolationStatus.ISOLATION_BOUNDED
            return plan
            
        plan.status = IsolationStatus.EXECUTING
        
        # In a real system, this routes through Phase 27 sandbox and Phase 47 ReproductionRunner.
        # Here we mock the bounded execution result assignment.
        for exp in plan.experiments:
            exp.status = IsolationStatus.COMPLETED
            
        plan.status = IsolationStatus.COMPLETED
        return plan

    @staticmethod
    def evaluate_revalidation(comparisons: List[IsolationComparison], plan_id: str) -> RevalidationDecision:
        for comp in comparisons:
            if comp.attribution == "ISOLATION_SUPPORTED" and comp.structural_impact == "CRITICAL_IMPACT":
                return RevalidationDecision(
                    plan_id=plan_id,
                    state=RevalidationDecisionState.RESEARCH_ARTIFACT_CHANGED,
                    explanation="Controlled OFAT confirms critical structural sensitivity."
                )
        
        return RevalidationDecision(
            plan_id=plan_id,
            state=RevalidationDecisionState.NO_REVALIDATION_REQUIRED,
            explanation="No critical factors isolated."
        )
