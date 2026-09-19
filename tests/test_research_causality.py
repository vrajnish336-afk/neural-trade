import pytest
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, FalsificationState
from app.research.consensus.models import ConsensusAssessment, ConsensusState
from app.research.causality.service import CausalService
from app.research.causality.models import CausalEvidenceLevel, CausalAssessmentState

@pytest.fixture
def causal_service():
    s = CausalService()
    s.repo._init_db()
    s.graph_repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_causal_results")
    with s.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return s

def test_causal_temporal_association(causal_service):
    t_past = datetime.now(timezone.utc) - timedelta(days=5)
    t_now = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_past, as_of=t_past, observed_at=t_past, metadata={"regime": "TREND"})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_now, as_of=t_now)
    
    causal_service.graph_repo.save_node(n1)
    causal_service.graph_repo.save_node(fn)
    causal_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_past, as_of=t_past, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_now, created_at=t_now
    )
    
    con = ConsensusAssessment(
        assessment_id="con_1", hypothesis_id="hyp_1", research_identity="id1", state=ConsensusState.CONSENSUS_SUPPORTED,
        independent_support_count=1, as_of=t_now, created_at=t_now
    )
    
    res = causal_service.evaluate("hyp_1", "id1", val, con, as_of=t_now)
    # 1 support is not enough for structural support, but temporal ordering is verified.
    assert res.temporal_ordering_verified == True
    assert res.causal_level == CausalEvidenceLevel.TEMPORAL_ASSOCIATION
    assert res.assessment_state == CausalAssessmentState.CAUSAL_EVIDENCE_WEAK

def test_causal_confounding_risk(causal_service):
    t_now = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_now, as_of=t_now, metadata={"regime": "TREND", "cost_scenario": "HIGH"})
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t_now, as_of=t_now, metadata={"regime": "TREND", "cost_scenario": "HIGH"})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_now, as_of=t_now)
    
    causal_service.graph_repo.save_node(n1)
    causal_service.graph_repo.save_node(n2)
    causal_service.graph_repo.save_node(fn)
    causal_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_now, as_of=t_now, deterministic_key="k1"))
    causal_service.graph_repo.save_edge(EvidenceEdge(edge_id="e2", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_now, as_of=t_now, deterministic_key="k2"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1", "exp_2"], as_of=t_now, created_at=t_now
    )
    
    con = ConsensusAssessment(
        assessment_id="con_1", hypothesis_id="hyp_1", research_identity="id1", state=ConsensusState.CONSENSUS_SUPPORTED,
        independent_support_count=2, as_of=t_now, created_at=t_now
    )
    
    res = causal_service.evaluate("hyp_1", "id1", val, con, as_of=t_now)
    # Even though there are 2 independent supports, they perfectly overlap on regime and cost, creating confounding.
    assert len(res.confounders) == 1
    assert "regime" in res.confounders[0].overlapping_variables
    assert len(res.alternatives) == 1
    assert res.assessment_state == CausalAssessmentState.CAUSAL_IDENTIFICATION_LIMITED

def test_causal_falsification_override(causal_service):
    t_now = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_now, as_of=t_now, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_now, as_of=t_now)
    
    causal_service.graph_repo.save_node(n1)
    causal_service.graph_repo.save_node(fn)
    causal_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_now, as_of=t_now, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], falsification_triggered=FalsificationState.TRIGGERED,
        as_of=t_now, created_at=t_now
    )
    
    con = ConsensusAssessment(
        assessment_id="con_1", hypothesis_id="hyp_1", research_identity="id1", state=ConsensusState.CONFLICTED,
        independent_support_count=1, as_of=t_now, created_at=t_now
    )
    
    res = causal_service.evaluate("hyp_1", "id1", val, con, as_of=t_now)
    assert res.causal_level == CausalEvidenceLevel.NO_RELATIONSHIP_EVIDENCE
    assert res.assessment_state == CausalAssessmentState.CONFLICTED

def test_causal_future_data_exclusion(causal_service):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_future, as_of=t_future, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_past, as_of=t_past)
    
    causal_service.graph_repo.save_node(n1)
    causal_service.graph_repo.save_node(fn)
    
    # Val is from past. We cannot pass future validation.
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_future, created_at=t_future
    )
    con = ConsensusAssessment(
        assessment_id="con_1", hypothesis_id="hyp_1", research_identity="id1", state=ConsensusState.CONSENSUS_SUPPORTED,
        as_of=t_future, created_at=t_future
    )
    
    with pytest.raises(ValueError):
        causal_service.evaluate("hyp_1", "id1", val, con, as_of=t_past)
