from app.research.discrepancy_isolation.models import DiscrepancyIsolationPlan, IsolationApprovalState

class ApprovalService:
    
    @staticmethod
    def approve_plan(plan: DiscrepancyIsolationPlan) -> DiscrepancyIsolationPlan:
        if plan.approval_state != IsolationApprovalState.REVIEW_REQUIRED:
            raise ValueError("Plan must be in REVIEW_REQUIRED state to be approved.")
        
        # Hard stop enforcement
        # Humans must interact with this via CLI or Dashboard
        plan.approval_state = IsolationApprovalState.APPROVED_FOR_RESEARCH
        return plan
