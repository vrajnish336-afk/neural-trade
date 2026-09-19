import pytest
from datetime import datetime, timezone
from app.research.reproduction.models import FrozenResearchSpecification
from app.research.discrepancy_isolation.planner import IsolationPlanner
from app.research.discrepancy_isolation.models import IsolationApprovalState, IsolationStatus
from app.research.discrepancy_isolation.approval import ApprovalService
from app.research.discrepancy_isolation.service import IsolationService

def test_ofat_validation():
    b = FrozenResearchSpecification(manifest_id="m1", dataset_identity="A", dataset_version="v1", research_identity_hash="h1", as_of=datetime.now(timezone.utc))
    e1 = FrozenResearchSpecification(manifest_id="m1", dataset_identity="B", dataset_version="v1", research_identity_hash="h1", as_of=b.as_of) # 1 change
    e2 = FrozenResearchSpecification(manifest_id="m1", dataset_identity="B", dataset_version="v1", research_identity_hash="h2", as_of=b.as_of) # 2 changes
    
    assert IsolationPlanner.validate_ofat(b, e1, "dataset_identity") == True
    assert IsolationPlanner.validate_ofat(b, e2, "dataset_identity") == False
    assert IsolationPlanner.validate_ofat(b, b, "dataset_identity") == False

def test_future_data_rejection():
    b = FrozenResearchSpecification(manifest_id="m1", dataset_identity="A", dataset_version="v1", research_identity_hash="h1", as_of=datetime(2023, 1, 1, tzinfo=timezone.utc))
    
    with pytest.raises(ValueError, match="FUTURE_INFORMATION_VIOLATION"):
        IsolationPlanner.create_plan(
            "a1", "r1", b, {"as_of": datetime(2024, 1, 1, tzinfo=timezone.utc)}
        )

def test_approval_gate():
    b = FrozenResearchSpecification(manifest_id="m1", dataset_identity="A", dataset_version="v1", research_identity_hash="h1", as_of=datetime.now(timezone.utc))
    plan = IsolationPlanner.create_plan("a1", "r1", b, {"dataset_identity": "B"})
    
    # Must start in REVIEW_REQUIRED
    assert plan.approval_state == IsolationApprovalState.REVIEW_REQUIRED
    
    # Cannot execute yet
    with pytest.raises(ValueError):
        IsolationService.execute_plan(plan)
        
    # Approve
    plan = ApprovalService.approve_plan(plan)
    assert plan.approval_state == IsolationApprovalState.APPROVED_FOR_RESEARCH
    
    # Can execute now
    plan = IsolationService.execute_plan(plan)
    assert plan.status == IsolationStatus.COMPLETED

def test_bounded_execution():
    b = FrozenResearchSpecification(manifest_id="m1", dataset_identity="A", dataset_version="v1", research_identity_hash="h1", as_of=datetime.now(timezone.utc))
    # Test boundary limits
    factors = {f"f{i}": str(i) for i in range(10)}
    plan = IsolationPlanner.create_plan("a1", "r1", b, factors)
    plan.max_experiments = 5
    plan = ApprovalService.approve_plan(plan)
    
    plan = IsolationService.execute_plan(plan)
    assert plan.status == IsolationStatus.ISOLATION_BOUNDED
