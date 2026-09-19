import pytest
from datetime import datetime, timezone, timedelta
import uuid
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.knowledge_intelligence.models import ResearchKnowledgeClaim, KnowledgeState, KnowledgeScope
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.governance.service import GovernanceService
from app.research.reasoning.service import ReasoningService
from app.research.reasoning.models import ConclusionType, ReasoningUncertainty, ReasoningStrength

def test_rule_001_independent_support():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = ReasoningService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    uid1 = uuid.uuid4().hex[:8]
    uid2 = uuid.uuid4().hex[:8]
    
    c1 = ResearchKnowledgeClaim(
        claim_id=f"c1_{uid1}", canonical_statement="Claim 1",
        knowledge_state=KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY,
        scope=KnowledgeScope(), as_of=as_of, created_at=as_of
    )
    c2 = ResearchKnowledgeClaim(
        claim_id=f"c2_{uid2}", canonical_statement="Claim 2",
        knowledge_state=KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY,
        scope=KnowledgeScope(), as_of=as_of, created_at=as_of
    )
    
    # Mocking graph neighborhood dynamically to satisfy ReasoningEngine 
    # Usually builder puts them in. Here we just manually store the nodes & edges
    n1 = EvidenceNode(node_id=c1.claim_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=c1.claim_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of, metadata={"state": c1.knowledge_state.value})
    n2 = EvidenceNode(node_id=c2.claim_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=c2.claim_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of, metadata={"state": c2.knowledge_state.value})
    repo.save_node(n1)
    repo.save_node(n2)
    
    # Fake edge to make them in the same neighborhood
    e = EvidenceEdge(edge_id=f"e_{uid1}", source_node_id=c1.claim_id, target_node_id=c2.claim_id, relationship_type=EdgeRelationship.ASSOCIATED_WITH, evidence_basis="test", as_of=as_of, created_at=as_of, deterministic_key="test")
    repo.save_edge(e)
    
    results = svc.reason_over_claim(c1, as_of)
    assert any(r.conclusion_type == ConclusionType.CONDITIONAL_INFERENCE for r in results)

def test_rule_003_conflicted_evidence():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = ReasoningService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    c1 = ResearchKnowledgeClaim(
        claim_id=f"c_{uid}", canonical_statement="Claim",
        knowledge_state=KnowledgeState.CONFLICTED,
        scope=KnowledgeScope(), as_of=as_of, created_at=as_of
    )
    n1 = EvidenceNode(node_id=c1.claim_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=c1.claim_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of, metadata={"state": c1.knowledge_state.value})
    repo.save_node(n1)
    
    e = EvidenceEdge(edge_id=f"e_conf_{uid}", source_node_id=c1.claim_id, target_node_id=f"other_{uid}", relationship_type=EdgeRelationship.CONTRADICTS, evidence_basis="test", as_of=as_of, created_at=as_of, deterministic_key="test")
    repo.save_edge(e)
    
    results = svc.reason_over_claim(c1, as_of)
    assert any(r.conclusion_type == ConclusionType.CONFLICTED_INFERENCE for r in results)

def test_reasoning_generates_phase_32_questions():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = ReasoningService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    c1 = ResearchKnowledgeClaim(
        claim_id=f"c_weak_{uid}", canonical_statement="Claim",
        knowledge_state=KnowledgeState.WEAKENED,
        scope=KnowledgeScope(), as_of=as_of, created_at=as_of
    )
    n1 = EvidenceNode(node_id=c1.claim_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=c1.claim_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of, metadata={"state": c1.knowledge_state.value})
    repo.save_node(n1)
    
    # Rule 004 targets WEAKENED claims and generates REQUIRES_REVALIDATION gaps -> Phase 32 questions
    svc.reason_over_claim(c1, as_of)
    q = svc.get_questions_for_review()
    
    assert len(q) >= 1
    assert any("REQUIRES_REVALIDATION" in qn.research_question for qn in q)

def test_idempotency_and_future_leakage():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = ReasoningService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    c1 = ResearchKnowledgeClaim(
        claim_id=f"c_leak_{uid}", canonical_statement="Claim",
        knowledge_state=KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY,
        scope=KnowledgeScope(), as_of=as_of + timedelta(days=10), created_at=as_of + timedelta(days=10)
    )
    n1 = EvidenceNode(node_id=c1.claim_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=c1.claim_id, source_type="KnowledgeClaim", as_of=c1.as_of, created_at=c1.as_of, metadata={"state": c1.knowledge_state.value})
    repo.save_node(n1)
    
    # Query with past timestamp -> should yield no claims/reasoning
    res = svc.reason_over_claim(c1, as_of)
    assert len(res) == 0

