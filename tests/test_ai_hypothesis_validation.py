import pytest
from datetime import datetime, timezone, timedelta
import json
from app.research.hypothesis_validation.models import ValidationState, EvidenceClassification, FalsificationState
from app.research.hypothesis_validation.validator import HypothesisValidator
from app.research.hypothesis_validation.falsification import FalsificationEngine
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.synthesis.models import ResearchHypothesis, HypothesisStatus, HypothesisType

@pytest.fixture
def validator():
    v = HypothesisValidator()
    v.repo._init_db()
    v.graph_repo._init_db()
    
    with v.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_hypothesis_validations")
    with v.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return v

def test_eligibility_missing_fields(validator):
    t = datetime.now(timezone.utc)
    h = ResearchHypothesis(
        hypothesis_id="h1",
        research_identity="idh1",
        hypothesis_text="Hypothesis 1",
        hypothesis_type=HypothesisType.REGIME_HYPOTHESIS,
        falsification_condition="", # Missing
        expected_observation="Expected obs",
        generated_at=t,
        as_of=t,
        status=HypothesisStatus.TESTABLE
    )
    res = validator.validate(h, as_of=t)
    assert res.status == ValidationState.NOT_ELIGIBLE_FOR_VALIDATION
    assert "Missing falsification_condition" in res.explanation

def test_eligibility_future_boundary(validator):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc) + timedelta(days=10)
    
    h = ResearchHypothesis(
        hypothesis_id="h1",
        research_identity="idh1",
        hypothesis_text="Hypothesis 1",
        hypothesis_type=HypothesisType.REGIME_HYPOTHESIS,
        falsification_condition="some condition",
        expected_observation="some observation",
        generated_at=t_future,
        as_of=t_future,
        status=HypothesisStatus.TESTABLE
    )
    res = validator.validate(h, as_of=t_past)
    assert res.status == ValidationState.NOT_ELIGIBLE_FOR_VALIDATION
    assert "Hypothesis generated after as_of boundary" in res.explanation

def test_supported_validation(validator):
    t = datetime.now(timezone.utc)
    h = ResearchHypothesis(
        hypothesis_id="h1",
        research_identity="idh1",
        hypothesis_text="Hypothesis 1",
        hypothesis_type=HypothesisType.REGIME_HYPOTHESIS,
        falsification_condition="degrades in trending up",
        expected_observation="consistent returns",
        generated_at=t,
        as_of=t,
        status=HypothesisStatus.TESTABLE
    )
    
    # Setup graph
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    validator.graph_repo.save_node(focal)
    
    # Add 4 supporting nodes to reach SUPPORTED state
    for i in range(4):
        exp = EvidenceNode(node_id=f"exp_{i}", node_type=NodeType.EXPERIMENT, source_id=f"e{i}", source_type="t", created_at=t, as_of=t)
        validator.graph_repo.save_node(exp)
        validator.graph_repo.save_edge(EvidenceEdge(edge_id=f"ee_{i}", source_node_id=exp.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=t, as_of=t, deterministic_key=f"k{i}"))
        
    res = validator.validate(h, as_of=t)
    assert res.status == ValidationState.SUPPORTED
    assert res.falsification_triggered == FalsificationState.NOT_TRIGGERED

def test_falsification_triggered(validator):
    t = datetime.now(timezone.utc)
    h = ResearchHypothesis(
        hypothesis_id="h1",
        research_identity="idh1",
        hypothesis_text="Hypothesis 1",
        hypothesis_type=HypothesisType.REGIME_HYPOTHESIS,
        falsification_condition="performance degrades below statistical significance",
        expected_observation="consistent returns",
        generated_at=t,
        as_of=t,
        status=HypothesisStatus.TESTABLE
    )
    
    # Setup graph
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    validator.graph_repo.save_node(focal)
    
    exp = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="e1", source_type="t", created_at=t, as_of=t, metadata={"performance": "degraded significantly"})
    validator.graph_repo.save_node(exp)
    validator.graph_repo.save_edge(EvidenceEdge(edge_id="ee_1", source_node_id=exp.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="conflict", created_at=t, as_of=t, deterministic_key="k1"))
    
    res = validator.validate(h, as_of=t)
    assert res.falsification_triggered == FalsificationState.TRIGGERED
    assert res.status == ValidationState.REJECTED

def test_historical_as_of_barrier(validator):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc)
    
    h = ResearchHypothesis(
        hypothesis_id="h1",
        research_identity="idh1",
        hypothesis_text="Hypothesis 1",
        hypothesis_type=HypothesisType.REGIME_HYPOTHESIS,
        falsification_condition="degrades",
        expected_observation="consistent returns",
        generated_at=t_past,
        as_of=t_past,
        status=HypothesisStatus.TESTABLE
    )
    
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t_past, as_of=t_past)
    validator.graph_repo.save_node(focal)
    
    exp_future = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="e2", source_type="t", created_at=t_future, as_of=t_future)
    validator.graph_repo.save_node(exp_future)
    validator.graph_repo.save_edge(EvidenceEdge(edge_id="ee_2", source_node_id=exp_future.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="conflict", created_at=t_future, as_of=t_future, deterministic_key="k2"))
    
    # If validating exactly at t_past, future node should not be seen
    res_past = validator.validate(h, as_of=t_past)
    assert res_past.status == ValidationState.INSUFFICIENT_EVIDENCE
    assert res_past.falsification_triggered == FalsificationState.NOT_TRIGGERED
    
    # Validating at t_future will see the contradiction and falsify it
    res_future = validator.validate(h, as_of=t_future)
    assert res_future.status == ValidationState.REJECTED
    assert res_future.falsification_triggered == FalsificationState.TRIGGERED
