import pytest
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, FalsificationState
from app.research.replication.models import ResearchReplicationResult, ReplicationAssessment, EvidenceStrengthLevel
from app.research.revalidation.models import RevalidationAssessment, DecayState
from app.research.consensus.service import ConsensusService
from app.research.consensus.models import ConsensusState, ConflictType, ResolutionState

@pytest.fixture
def consensus_service():
    s = ConsensusService()
    s.repo._init_db()
    s.graph_repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_consensus_results")
    with s.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return s

def test_consensus_supported(consensus_service):
    t = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t, as_of=t)
    
    consensus_service.graph_repo.save_node(n1)
    consensus_service.graph_repo.save_node(fn)
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t, created_at=t
    )
    
    res = consensus_service.evaluate("hyp_1", "id1", val, as_of=t)
    assert res.state == ConsensusState.CONSENSUS_SUPPORTED
    assert res.independent_support_count == 1
    assert res.independent_contradict_count == 0

def test_conflicted_consensus(consensus_service):
    t = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t, metadata={})
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t, as_of=t)
    
    consensus_service.graph_repo.save_node(n1)
    consensus_service.graph_repo.save_node(n2)
    consensus_service.graph_repo.save_node(fn)
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e2", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k2"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t, created_at=t
    )
    
    res = consensus_service.evaluate("hyp_1", "id1", val, as_of=t)
    assert res.state == ConsensusState.CONFLICTED
    assert res.independent_support_count == 1
    assert res.independent_contradict_count == 1
    assert res.conflicts[0].conflict_type == ConflictType.UNKNOWN_CONFLICT
    assert res.conflicts[0].resolution == ResolutionState.UNRESOLVED

def test_conditional_consensus_regime(consensus_service):
    t = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t, metadata={"regime": "TREND"})
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t, metadata={"regime": "RANGE"})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t, as_of=t)
    
    consensus_service.graph_repo.save_node(n1)
    consensus_service.graph_repo.save_node(n2)
    consensus_service.graph_repo.save_node(fn)
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e2", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k2"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t, created_at=t
    )
    
    res = consensus_service.evaluate("hyp_1", "id1", val, as_of=t)
    assert res.state == ConsensusState.CONDITIONAL_CONSENSUS
    assert res.conflicts[0].conflict_type == ConflictType.REGIME_CONFLICT
    assert res.conflicts[0].resolution == ResolutionState.RESOLVED_BY_CONDITION

def test_falsification_overrides_consensus(consensus_service):
    t = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t, as_of=t)
    
    consensus_service.graph_repo.save_node(n1)
    consensus_service.graph_repo.save_node(fn)
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], falsification_triggered=FalsificationState.TRIGGERED,
        as_of=t, created_at=t
    )
    
    res = consensus_service.evaluate("hyp_1", "id1", val, as_of=t)
    assert res.state == ConsensusState.CONFLICTED
    assert res.falsification_triggered == True
    assert res.conflicts[0].conflict_type == ConflictType.FALSIFICATION_CONFLICT

def test_as_of_exclusion(consensus_service):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc)
    
    n1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t_past, as_of=t_past, metadata={})
    n2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t_future, as_of=t_future, metadata={})
    fn = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="f1", source_type="t", identity_hash="id1", created_at=t_past, as_of=t_past)
    
    consensus_service.graph_repo.save_node(n1)
    consensus_service.graph_repo.save_node(n2)
    consensus_service.graph_repo.save_node(fn)
    
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id="exp_1", target_node_id="focal_1", relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="test", created_at=t_past, as_of=t_past, deterministic_key="k1"))
    # Future contradiction should be hidden when querying at t_past
    consensus_service.graph_repo.save_edge(EvidenceEdge(edge_id="e2", source_node_id="exp_2", target_node_id="focal_1", relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="test", created_at=t_future, as_of=t_future, deterministic_key="k2"))
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        supporting_evidence_ids=["exp_1"], as_of=t_past, created_at=t_past
    )
    
    res = consensus_service.evaluate("hyp_1", "id1", val, as_of=t_past)
    assert res.state == ConsensusState.CONSENSUS_SUPPORTED
    assert res.independent_support_count == 1
    assert res.independent_contradict_count == 0
