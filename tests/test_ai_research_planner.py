import pytest
from datetime import datetime, timezone, timedelta
import json
from app.research.planner.models import ResearchDecisionState, ResearchAction
from app.research.planner.planner import ResearchDecisionPlanner
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship

@pytest.fixture
def planner():
    p = ResearchDecisionPlanner()
    p.repo._init_db()
    p.graph_repo._init_db()
    
    with p.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_decisions")
        conn.execute("DELETE FROM research_question_candidates")
    with p.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return p

def test_planner_deterministic_identity(planner):
    t = datetime.now(timezone.utc)
    gap1 = EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    planner.graph_repo.save_node(gap1)
    
    decisions = planner.generate_plan(as_of=t)
    assert len(decisions) == 1
    d1 = decisions[0]
    
    # Generate again
    decisions2 = planner.generate_plan(as_of=t)
    assert len(decisions2) == 1
    assert decisions2[0].created_at == d1.created_at # Not recreated

def test_planner_evidence_gap_extraction(planner):
    t = datetime.now(timezone.utc)
    gap1 = EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t, metadata={"gap_type": "robustness"})
    planner.graph_repo.save_node(gap1)
    
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.priority_breakdown.evidence_gap_weight == 2.0
    assert "Robustness" in d.priority_breakdown.explanation

def test_planner_conflict_prioritization(planner):
    t = datetime.now(timezone.utc)
    gap_node = EvidenceNode(node_id="gap_456", node_type=NodeType.EVIDENCE_GAP, source_id="456", source_type="test", identity_hash="idh1", created_at=t, as_of=t, metadata={"gap_type": "sample"})
    planner.graph_repo.save_node(gap_node)
    
    comp_node = EvidenceNode(node_id="comp_1", node_type=NodeType.EXPERIMENT_COMPARISON, source_id="c1", source_type="test", created_at=t, as_of=t, metadata={"status": "NOT_SUPPORTED"})
    planner.graph_repo.save_node(comp_node)
    
    planner.graph_repo.save_edge(EvidenceEdge(edge_id="e1", source_node_id=comp_node.node_id, target_node_id=gap_node.node_id, relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="conflict", created_at=t, as_of=t, deterministic_key="k1"))
    
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.priority_breakdown.conflict_weight == 2.5
    assert d.recommended_action == ResearchAction.RESOLVE_CONFLICT

def test_planner_research_saturation(planner):
    t = datetime.now(timezone.utc)
    gap_node = EvidenceNode(node_id="gap_sat", node_type=NodeType.EVIDENCE_GAP, source_id="sat", source_type="test", identity_hash="idh_sat", created_at=t, as_of=t)
    planner.graph_repo.save_node(gap_node)
    
    for i in range(8):
        exp = EvidenceNode(node_id=f"exp_{i}", node_type=NodeType.EXPERIMENT, source_id=f"e{i}", source_type="test", created_at=t, as_of=t)
        planner.graph_repo.save_node(exp)
        planner.graph_repo.save_edge(EvidenceEdge(edge_id=f"ee_{i}", source_node_id=exp.node_id, target_node_id=gap_node.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=t, as_of=t, deterministic_key=f"k_{i}"))
        
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.priority_breakdown.evidence_saturation_penalty == 3.0 # (8 - 5) * 1.0
    assert d.recommended_action == ResearchAction.ALREADY_RESEARCHED

def test_planner_staleness(planner):
    t = datetime.now(timezone.utc)
    old_t = t - timedelta(days=100)
    gap_node = EvidenceNode(node_id="gap_stale", node_type=NodeType.EVIDENCE_GAP, source_id="stale", source_type="test", identity_hash="idh_stale", created_at=t, as_of=t)
    planner.graph_repo.save_node(gap_node)
    
    exp = EvidenceNode(node_id="exp_old", node_type=NodeType.EXPERIMENT, source_id="eo", source_type="test", created_at=old_t, as_of=old_t)
    planner.graph_repo.save_node(exp)
    planner.graph_repo.save_edge(EvidenceEdge(edge_id="ee_old", source_node_id=exp.node_id, target_node_id=gap_node.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=old_t, as_of=old_t, deterministic_key="ko"))
    
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.priority_breakdown.novelty_weight == 1.5
    assert "stale" in d.priority_breakdown.explanation

def test_planner_feasibility_and_data_missing(planner):
    t = datetime.now(timezone.utc)
    gap_node = EvidenceNode(node_id="gap_f", node_type=NodeType.EVIDENCE_GAP, source_id="f", source_type="test", identity_hash="idh_f", created_at=t, as_of=t, metadata={"feasibility": "DATA_NOT_AVAILABLE"})
    planner.graph_repo.save_node(gap_node)
    
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.recommended_action == ResearchAction.COLLECT_DATA
    assert d.status == ResearchDecisionState.DATA_NOT_AVAILABLE
    assert d.priority_breakdown.feasibility_weight == -10.0

def test_planner_approval_gate(planner):
    t = datetime.now(timezone.utc)
    planner.graph_repo.save_node(EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t))
    
    decisions = planner.generate_plan(as_of=t)
    d = decisions[0]
    assert d.status == ResearchDecisionState.REVIEW_REQUIRED
    
    assert planner.approve_decision(d.decision_id) == True
    
    db_d = planner.repo.get_decision(d.decision_id)
    assert db_d.status == ResearchDecisionState.APPROVED_FOR_RESEARCH
    assert db_d.approval_timestamp is not None

def test_planner_bounded_queue(planner):
    t = datetime.now(timezone.utc)
    planner.max_queue_size = 2
    for i in range(5):
        planner.graph_repo.save_node(EvidenceNode(node_id=f"gap_{i}", node_type=NodeType.EVIDENCE_GAP, source_id=str(i), source_type="t", identity_hash=f"idh{i}", created_at=t, as_of=t))
        
    decisions = planner.generate_plan(as_of=t)
    assert len(decisions) == 2

def test_planner_historical_as_of(planner):
    t1 = datetime.now(timezone.utc) - timedelta(days=10)
    t2 = datetime.now(timezone.utc)
    
    planner.graph_repo.save_node(EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="1", source_type="t", identity_hash="idh1", created_at=t2, as_of=t2))
    
    # Should not see gap created at t2 if querying at t1
    decisions = planner.generate_plan(as_of=t1)
    assert len(decisions) == 0
    
    decisions2 = planner.generate_plan(as_of=t2)
    assert len(decisions2) == 1
    
def test_pnl_only_ranking_rejection(planner):
    # This is implicitly tested by scoring logic but we can assert no PnL field is used
    t = datetime.now(timezone.utc)
    gap_node = EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t, metadata={"pnl": 99999})
    planner.graph_repo.save_node(gap_node)
    decisions = planner.generate_plan(as_of=t)
    assert decisions[0].priority_breakdown.final_score <= 3.0 # not affected by massive PnL
