import pytest
from app.strategies.replication import ResearchReplicationService, ReplicatedStrategyCandidate

def test_valid_replication_candidate_creation():
    service = ResearchReplicationService()
    params = {"lookback_period": 20, "threshold_multiplier": 1.5}
    candidate = service.create_candidate(
        base_strategy="BreakoutStrategy",
        parameters=params,
        description="Variant of Breakout with 20-period lookback"
    )
    
    assert candidate.base_strategy == "BreakoutStrategy"
    assert candidate.parameters == params
    assert candidate.status == "RESEARCH_ONLY"
    assert service.get_candidate(candidate.candidate_id) == candidate

def test_invalid_candidate_rejection():
    service = ResearchReplicationService()
    
    # Invalid base strategy
    with pytest.raises(ValueError) as exc_info:
        service.create_candidate("UnsafeStrategy", {"period": 10}, "Invalid")
    assert "Invalid base strategy" in str(exc_info.value)
    
    # Dunder key parameter
    with pytest.raises(ValueError) as exc_info2:
        service.create_candidate("BreakoutStrategy", {"__code__": "malicious"}, "Invalid key")
    assert "Invalid parameter key" in str(exc_info2.value)

def test_offline_only_isolation():
    service = ResearchReplicationService()
    candidate = service.create_candidate(
        base_strategy="TrendFollowingStrategy",
        parameters={"sma_fast": 10, "sma_slow": 30},
        description="Trend following variant"
    )
    assert candidate.status == "RESEARCH_ONLY"
    
    # Confirm candidate is stored in offline list
    candidates = service.list_candidates()
    assert len(candidates) == 1
    assert candidates[0].candidate_id == candidate.candidate_id

def test_no_execution_or_risk_bypass():
    service = ResearchReplicationService()
    
    with pytest.raises(PermissionError) as exc_info:
        service.execute_live()
    assert "restricted strictly to offline research" in str(exc_info.value)
    
    with pytest.raises(PermissionError) as exc_info2:
        service.place_order()
    assert "restricted strictly to offline research" in str(exc_info2.value)
