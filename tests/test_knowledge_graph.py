import pytest
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.knowledge_intelligence.models import (
    ResearchKnowledgeClaim, KnowledgeState, KnowledgeScope, KnowledgePattern, PatternFamily, KnowledgeGap
)
from app.research.governance.service import GovernanceService
from app.research.knowledge_graph.service import KnowledgeGraphService
from app.research.evidence_graph.models import EvidenceNode, NodeType, EdgeRelationship

def test_knowledge_graph_builder_idempotency():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = KnowledgeGraphService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    
    import uuid
    uid = str(uuid.uuid4())
    claim = ResearchKnowledgeClaim(
        claim_id=f"test_claim_kg_{uid}",
        canonical_statement="Test KG Claim",
        knowledge_state=KnowledgeState.CONFLICTED,
        scope=KnowledgeScope(dataset_scope=["D1"], regime_scope=["R1"]),
        contradicting_evidence_ids=[f"ev_{uid}"],
        as_of=as_of - timedelta(days=1),
        created_at=as_of - timedelta(days=1)
    )
    
    # Mock evidence node
    ev = EvidenceNode(node_id=f"ev_{uid}", node_type=NodeType.EXPERIMENT, source_id=f"ev_{uid}", source_type="Experiment",
                      as_of=as_of - timedelta(days=1), created_at=as_of - timedelta(days=1))
    repo.save_node(ev)
    
    # First build
    c1 = svc.ingest_knowledge([claim], [], [], as_of)
    assert c1 > 0
    
    # Second build (should be idempotent)
    c2 = svc.ingest_knowledge([claim], [], [], as_of)
    assert c2 == 0
    
    summary = svc.get_summary(as_of)
    assert summary.conflicted_relationships >= 1
    assert summary.conditional_relationships >= 2

def test_future_leakage_rejection():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = KnowledgeGraphService(repo, gov)
    
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    
    claim = ResearchKnowledgeClaim(
        claim_id="future_claim",
        canonical_statement="Future Claim",
        knowledge_state=KnowledgeState.SUPPORTED,
        scope=KnowledgeScope(),
        as_of=base_time + timedelta(days=10),
        created_at=base_time + timedelta(days=10)
    )
    
    # Should not build because the claim is from the future relative to base_time
    count = svc.ingest_knowledge([claim], [], [], base_time)
    assert count == 0

def test_graph_queries_and_clusters():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = KnowledgeGraphService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    
    import uuid
    uid = str(uuid.uuid4())
    pattern = KnowledgePattern(
        pattern_id=f"pat_kg_{uid}",
        pattern_family=PatternFamily.DATASET,
        description="Dataset divergence",
        independent_evidence_count=3,
        supporting_evidence_units=0,
        contradicting_evidence_units=3,
        datasets_involved=["D2"],
        as_of=as_of,
        created_at=as_of
    )
    
    svc.ingest_knowledge([], [pattern], [], as_of)
    
    clusters = svc.identify_structural_failures(as_of)
    assert len(clusters) >= 1
    assert any("DATASET" in c.cluster_name for c in clusters)

def test_trace_claim_relationships():
    repo = EvidenceGraphRepository()
    gov = GovernanceService()
    svc = KnowledgeGraphService(repo, gov)
    
    as_of = datetime.now(timezone.utc)
    
    import uuid
    uid = str(uuid.uuid4())
    claim = ResearchKnowledgeClaim(
        claim_id=f"test_claim_trace_{uid}",
        canonical_statement="Test Trace",
        knowledge_state=KnowledgeState.CONFLICTED,
        scope=KnowledgeScope(dataset_scope=["D3"]),
        as_of=as_of,
        created_at=as_of
    )
    
    svc.ingest_knowledge([claim], [], [], as_of)
    
    paths = svc.trace_claim_relationships(f"test_claim_trace_{uid}", as_of)
    assert len(paths) > 0
    assert paths[0].source_node.node_id == f"test_claim_trace_{uid}"

