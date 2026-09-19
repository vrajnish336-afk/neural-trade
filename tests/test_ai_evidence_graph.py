import pytest
from datetime import datetime, timedelta
import uuid
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship, ConclusionState
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.builder import GraphBuilder
from app.research.evidence_graph.queries import GraphQueries

@pytest.fixture
def repo():
    r = EvidenceGraphRepository()
    r._init_db()
    with r._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_edges")
        conn.execute("DELETE FROM research_evidence_nodes")
    return r

@pytest.fixture
def builder():
    return GraphBuilder()

@pytest.fixture
def queries():
    return GraphQueries()

def test_node_and_edge_creation(repo):
    n1 = EvidenceNode(
        node_id="n1",
        node_type=NodeType.EXPERIMENT,
        source_id="exp1",
        source_type="test",
        created_at=datetime.utcnow(),
        as_of=datetime.utcnow()
    )
    repo.save_node(n1)
    
    assert repo.get_node("n1").source_id == "exp1"

def test_as_of_filtering(repo, queries):
    base_time = datetime.utcnow()
    n_old = EvidenceNode(
        node_id="old",
        node_type=NodeType.EXPERIMENT,
        source_id="exp_old",
        source_type="test",
        created_at=base_time - timedelta(days=2),
        as_of=base_time - timedelta(days=2)
    )
    n_new = EvidenceNode(
        node_id="new",
        node_type=NodeType.EXPERIMENT,
        source_id="exp_new",
        source_type="test",
        created_at=base_time,
        as_of=base_time
    )
    repo.save_node(n_old)
    repo.save_node(n_new)
    
    nodes_past = repo.get_nodes(as_of=base_time - timedelta(days=1))
    assert len(nodes_past) == 1
    assert nodes_past[0].node_id == "old"
    
    nodes_now = repo.get_nodes(as_of=base_time + timedelta(days=1))
    assert len(nodes_now) == 2

def test_duplicate_edge_prevention(repo):
    e = EvidenceEdge(
        edge_id="e1",
        source_node_id="n1",
        target_node_id="n2",
        relationship_type=EdgeRelationship.SUPPORTS,
        evidence_basis="test",
        created_at=datetime.utcnow(),
        as_of=datetime.utcnow(),
        deterministic_key="det_key_1"
    )
    repo.save_edge(e)
    repo.save_edge(e) # Should ignore duplicate due to deterministic_key constraint
    assert len(repo.get_edges()) == 1

def test_evidence_chain(repo, queries):
    t = datetime.utcnow()
    repo.save_node(EvidenceNode(node_id="n1", node_type=NodeType.EXPERIMENT, source_id="s1", source_type="t", created_at=t, as_of=t))
    repo.save_node(EvidenceNode(node_id="n2", node_type=NodeType.EVOLUTION_PROPOSAL, source_id="s2", source_type="t", created_at=t, as_of=t))
    
    repo.save_edge(EvidenceEdge(
        edge_id="e1", source_node_id="n2", target_node_id="n1",
        relationship_type=EdgeRelationship.DERIVED_FROM,
        evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"
    ))
    
    chain = queries.get_evidence_chain("n2")
    assert len(chain) == 2
    assert chain[0].node_id == "n2"
    assert chain[1].node_id == "n1"

def test_graph_validation(repo, queries):
    t = datetime.utcnow()
    repo.save_node(EvidenceNode(node_id="n1", node_type=NodeType.EXPERIMENT, source_id="s1", source_type="t", created_at=t, as_of=t))
    
    repo.save_edge(EvidenceEdge(
        edge_id="e1", source_node_id="n1", target_node_id="missing_node",
        relationship_type=EdgeRelationship.SUPPORTS,
        evidence_basis="test", created_at=t, as_of=t, deterministic_key="k1"
    ))
    
    res = queries.validate_graph()
    assert res["status"] == "INVALID"
    assert res["missing_targets"] == 1
