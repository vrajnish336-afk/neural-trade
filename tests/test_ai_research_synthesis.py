import pytest
from datetime import datetime, timezone, timedelta
import json
from app.research.synthesis.models import KnowledgeState, HypothesisStatus, HypothesisType
from app.research.synthesis.synthesizer import ResearchKnowledgeSynthesizer
from app.research.synthesis.hypothesis import HypothesisGenerator
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.synthesis.repository import SynthesisRepository

@pytest.fixture
def synthesizer():
    s = ResearchKnowledgeSynthesizer()
    s.repo._init_db()
    s.graph_repo._init_db()
    
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_syntheses")
        conn.execute("DELETE FROM research_hypotheses")
    with s.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
        conn.execute("DELETE FROM research_evidence_edges")
    return s

@pytest.fixture
def hypothesis_gen():
    h = HypothesisGenerator()
    return h

def test_synthesis_creation_and_evidence_aggregation(synthesizer):
    t = datetime.now(timezone.utc)
    # Create focal node
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(focal)
    
    # Create 4 supporting experiments
    for i in range(4):
        exp = EvidenceNode(node_id=f"exp_{i}", node_type=NodeType.EXPERIMENT, source_id=f"e{i}", source_type="t", created_at=t, as_of=t)
        synthesizer.graph_repo.save_node(exp)
        synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id=f"ee_{i}", source_node_id=exp.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=t, as_of=t, deterministic_key=f"k{i}"))
        
    syn = synthesizer.synthesize("idh1", as_of=t)
    assert syn is not None
    assert len(syn.supporting_evidence) == 4
    assert len(syn.contradictory_evidence) == 0
    assert syn.confidence_state == KnowledgeState.SUPPORTED

def test_synthesis_conflict_driven(synthesizer):
    t = datetime.now(timezone.utc)
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(focal)
    
    exp1 = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="e1", source_type="t", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(exp1)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_1", source_node_id=exp1.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=t, as_of=t, deterministic_key="k1"))
    
    exp2 = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="e2", source_type="t", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(exp2)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_2", source_node_id=exp2.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="conflict", created_at=t, as_of=t, deterministic_key="k2"))
    
    syn = synthesizer.synthesize("idh1", as_of=t)
    assert syn.confidence_state == KnowledgeState.CONFLICTED
    assert len(syn.contradictory_evidence) == 1

def test_historical_as_of(synthesizer):
    t1 = datetime.now(timezone.utc) - timedelta(days=10)
    t2 = datetime.now(timezone.utc)
    
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t1, as_of=t1)
    synthesizer.graph_repo.save_node(focal)
    
    exp_future = EvidenceNode(node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="e2", source_type="t", created_at=t2, as_of=t2)
    synthesizer.graph_repo.save_node(exp_future)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_2", source_node_id=exp_future.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=t2, as_of=t2, deterministic_key="k2"))
    
    syn = synthesizer.synthesize("idh1", as_of=t1)
    assert syn.confidence_state == KnowledgeState.INSUFFICIENT_EVIDENCE
    assert len(syn.supporting_evidence) == 0 # Future exp not included
    
    syn2 = synthesizer.synthesize("idh1", as_of=t2)
    assert syn2.confidence_state == KnowledgeState.EMERGING
    assert len(syn2.supporting_evidence) == 1

def test_hypothesis_generation(synthesizer, hypothesis_gen):
    t = datetime.now(timezone.utc)
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(focal)
    
    gap = EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="g1", source_type="t", created_at=t, as_of=t, metadata={"gap_type": "robustness"})
    synthesizer.graph_repo.save_node(gap)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_g", source_node_id=gap.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.RELATED_TO, evidence_basis="gap", created_at=t, as_of=t, deterministic_key="kg"))
    
    syn = synthesizer.synthesize("idh1", as_of=t)
    hyps = hypothesis_gen.generate_from_synthesis(syn, as_of=t)
    
    assert len(hyps) == 1
    h = hyps[0]
    assert h.hypothesis_type == HypothesisType.ROBUSTNESS_HYPOTHESIS
    assert h.falsification_condition != ""
    assert h.status == HypothesisStatus.TESTABLE
    assert h.hypothesis_id is not None
    assert h.originating_synthesis_id == syn.synthesis_id

def test_deterministic_hypothesis_identity(synthesizer, hypothesis_gen):
    t = datetime.now(timezone.utc)
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(focal)
    gap = EvidenceNode(node_id="gap_1", node_type=NodeType.EVIDENCE_GAP, source_id="g1", source_type="t", created_at=t, as_of=t, metadata={"gap_type": "robustness"})
    synthesizer.graph_repo.save_node(gap)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_g", source_node_id=gap.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.RELATED_TO, evidence_basis="gap", created_at=t, as_of=t, deterministic_key="kg"))
    
    syn = synthesizer.synthesize("idh1", as_of=t)
    hyps1 = hypothesis_gen.generate_from_synthesis(syn, as_of=t)
    assert len(hyps1) == 1
    
    # Generate again
    hyps2 = hypothesis_gen.generate_from_synthesis(syn, as_of=t)
    assert len(hyps2) == 0 # DB deduplication prevents yielding duplicate

def test_staleness_and_insufficient_evidence(synthesizer):
    t = datetime.now(timezone.utc)
    old_t = t - timedelta(days=100)
    
    focal = EvidenceNode(node_id="focal_1", node_type=NodeType.RESEARCH_QUESTION, source_id="1", source_type="t", identity_hash="idh1", created_at=t, as_of=t)
    synthesizer.graph_repo.save_node(focal)
    
    exp = EvidenceNode(node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="e1", source_type="t", created_at=old_t, as_of=old_t)
    synthesizer.graph_repo.save_node(exp)
    synthesizer.graph_repo.save_edge(EvidenceEdge(edge_id="ee_1", source_node_id=exp.node_id, target_node_id=focal.node_id, relationship_type=EdgeRelationship.SUPPORTS, evidence_basis="support", created_at=old_t, as_of=old_t, deterministic_key="k1"))
    
    syn = synthesizer.synthesize("idh1", as_of=t)
    assert syn.confidence_state == KnowledgeState.STALE
