import pytest
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, FalsificationState, EvidenceClassification
from app.research.replication.models import ResearchReplicationResult, ReplicationAssessment, GeneralizationState, EvidenceStrengthLevel
from app.research.revalidation.service import RevalidationService
from app.research.revalidation.models import DecayState, RevalidationReason

@pytest.fixture
def reval_service():
    s = RevalidationService()
    s.repo._init_db()
    s.graph_repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_revalidation_results")
    with s.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return s

def test_fresh_evidence_classification(reval_service):
    t = datetime.now(timezone.utc)
    # Evidence created 10 days ago -> FRESH
    t_base = t - timedelta(days=10)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_base, as_of=t_base, metadata={})
    reval_service.graph_repo.save_node(n1)
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_base, created_at=t_base
    )
    
    rep = ResearchReplicationResult(
        assessment_id="rep_1", hypothesis_id="hyp_1", validation_id="val_1", research_identity="id1",
        replication=ReplicationAssessment(total_independent_units=3),
        evidence_strength=EvidenceStrengthLevel.STRONG, as_of=t_base, created_at=t_base
    )
    
    res = reval_service.evaluate(val, rep, as_of=t)
    assert res.decay_state == DecayState.FRESH
    assert res.current_evidence_strength == EvidenceStrengthLevel.STRONG
    assert res.revalidation_required == False

def test_stale_evidence_classification(reval_service):
    t = datetime.now(timezone.utc)
    # Evidence created 100 days ago -> STALE
    t_base = t - timedelta(days=100)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_base, as_of=t_base, metadata={})
    reval_service.graph_repo.save_node(n1)
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_base, created_at=t_base
    )
    
    rep = ResearchReplicationResult(
        assessment_id="rep_1", hypothesis_id="hyp_1", validation_id="val_1", research_identity="id1",
        replication=ReplicationAssessment(total_independent_units=3),
        evidence_strength=EvidenceStrengthLevel.STRONG, as_of=t_base, created_at=t_base
    )
    
    res = reval_service.evaluate(val, rep, as_of=t)
    assert res.decay_state == DecayState.STALE
    assert res.current_evidence_strength == EvidenceStrengthLevel.STALE
    assert RevalidationReason.EVIDENCE_TOO_OLD in res.revalidation_reasons
    assert res.revalidation_required == True

def test_regime_drift_detection(reval_service):
    t = datetime.now(timezone.utc)
    t_base = t - timedelta(days=10)
    
    # Original validation regime: TREND
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_base, as_of=t_base, metadata={"regime": "TREND"})
    
    # Newer experiment post validation: RANGE
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t, metadata={"regime": "RANGE"})
    
    # Focal node
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_base, as_of=t_base)
    
    reval_service.graph_repo.save_node(n1)
    reval_service.graph_repo.save_node(n2)
    reval_service.graph_repo.save_node(fn)
    reval_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_base, created_at=t_base
    )
    
    rep = ResearchReplicationResult(
        assessment_id="rep_1", hypothesis_id="hyp_1", validation_id="val_1", research_identity="id1",
        replication=ReplicationAssessment(total_independent_units=3),
        evidence_strength=EvidenceStrengthLevel.STRONG, as_of=t_base, created_at=t_base
    )
    
    res = reval_service.evaluate(val, rep, as_of=t)
    assert "REGIME_SHIFT" in res.drift_flags
    assert RevalidationReason.NEW_REGIME in res.revalidation_reasons
    assert res.current_evidence_strength == EvidenceStrengthLevel.FRAGILE
    assert res.revalidation_required == True

def test_new_contradiction_drift(reval_service):
    t = datetime.now(timezone.utc)
    t_base = t - timedelta(days=10)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_base, as_of=t_base, metadata={})
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_base, as_of=t_base)
    
    reval_service.graph_repo.save_node(n1)
    reval_service.graph_repo.save_node(n2)
    reval_service.graph_repo.save_node(fn)
    reval_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_base, created_at=t_base
    )
    
    rep = ResearchReplicationResult(
        assessment_id="rep_1", hypothesis_id="hyp_1", validation_id="val_1", research_identity="id1",
        replication=ReplicationAssessment(total_independent_units=3),
        evidence_strength=EvidenceStrengthLevel.STRONG, as_of=t_base, created_at=t_base
    )
    
    res = reval_service.evaluate(val, rep, as_of=t)
    assert RevalidationReason.NEW_CONTRADICTION in res.revalidation_reasons
    assert res.current_evidence_strength == EvidenceStrengthLevel.MODERATE
    assert res.revalidation_required == True

def test_as_of_excludes_future_evidence(reval_service):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_past, as_of=t_past, metadata={"regime": "TREND"})
    # Future regime drift that MUST NOT be seen
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t_future, as_of=t_future, metadata={"regime": "RANGE"})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_past, as_of=t_past)
    
    reval_service.graph_repo.save_node(n1)
    reval_service.graph_repo.save_node(n2)
    reval_service.graph_repo.save_node(fn)
    reval_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_future, as_of=t_future, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_past, created_at=t_past
    )
    
    rep = ResearchReplicationResult(
        assessment_id="rep_1", hypothesis_id="hyp_1", validation_id="val_1", research_identity="id1",
        replication=ReplicationAssessment(total_independent_units=3),
        evidence_strength=EvidenceStrengthLevel.STRONG, as_of=t_past, created_at=t_past
    )
    
    res = reval_service.evaluate(val, rep, as_of=t_past)
    assert len(res.drift_flags) == 0
    assert res.decay_state == DecayState.FRESH
    assert res.current_evidence_strength == EvidenceStrengthLevel.STRONG
