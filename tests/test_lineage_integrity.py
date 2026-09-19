import pytest
import uuid
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.governance.models import ResearchAuditEvent
from app.research.governance.service import GovernanceService
from app.research.reasoning.models import ResearchReasoningResult, ConclusionType
from app.research.reasoning.service import ReasoningService
from app.research.planner.models import ResearchQuestionCandidate, ResearchDecisionState
from app.research.planner.planner import ResearchDecisionPlanner
from app.research.lineage_integrity.models import IntegrityFindingType, IntegritySeverity
from app.research.lineage_integrity.service import IntegrityService

def test_lineage_orphaned_knowledge():
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    graph_repo = EvidenceGraphRepository()
    svc = IntegrityService(graph_repo=graph_repo)
    
    # Create an orphaned knowledge claim
    k_id = f"know_orph_{uid}"
    node = EvidenceNode(node_id=k_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=k_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of)
    graph_repo.save_node(node)
    
    report = svc.generate_report(as_of)
    
    # Find the orphaned knowledge finding
    findings = [f for f in report.findings if f.canonical_object_id == k_id]
    assert len(findings) > 0
    assert any(f.finding_type == IntegrityFindingType.ORPHANED_KNOWLEDGE for f in findings)
    assert any(f.severity == IntegritySeverity.HIGH for f in findings)

def test_lineage_future_violation():
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    graph_repo = EvidenceGraphRepository()
    svc = IntegrityService(graph_repo=graph_repo)
    
    k_id = f"know_fut_{uid}"
    ev_id = f"ev_fut_{uid}"
    
    # Knowledge claim at as_of
    k_node = EvidenceNode(node_id=k_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=k_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of)
    graph_repo.save_node(k_node)
    
    # Evidence from the future
    future_time = as_of + timedelta(days=1)
    ev_node = EvidenceNode(node_id=ev_id, node_type=NodeType.OBSERVATION, source_id=ev_id, source_type="Obs", as_of=future_time, created_at=future_time)
    graph_repo.save_node(ev_node)
    
    # Valid edge backwards (created historically but points to a future node logically)
    # Wait, the edge as_of must be <= as_of to be picked up in historical trace
    e = EvidenceEdge(edge_id=f"e_fut_{uid}", source_node_id=ev_id, target_node_id=k_id, relationship_type=EdgeRelationship.ASSOCIATED_WITH, evidence_basis="test", as_of=as_of, created_at=as_of, deterministic_key="test")
    graph_repo.save_edge(e)
    
    report = svc.generate_report(as_of)
    findings = [f for f in report.findings if f.canonical_object_id == k_id]
    
    assert any(f.finding_type == IntegrityFindingType.FUTURE_INFORMATION_VIOLATION for f in findings)
    assert any(f.severity == IntegritySeverity.CRITICAL for f in findings)

def test_temporal_order_violation():
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    graph_repo = EvidenceGraphRepository()
    svc = IntegrityService(graph_repo=graph_repo)
    
    k_id = f"know_temp_{uid}"
    ev_id = f"ev_temp_{uid}"
    
    # Knowledge claim at as_of
    k_node = EvidenceNode(node_id=k_id, node_type=NodeType.KNOWLEDGE_CLAIM, source_id=k_id, source_type="KnowledgeClaim", as_of=as_of, created_at=as_of)
    graph_repo.save_node(k_node)
    
    # Evidence from the past
    past_time = as_of - timedelta(days=1)
    ev_node = EvidenceNode(node_id=ev_id, node_type=NodeType.OBSERVATION, source_id=ev_id, source_type="Obs", as_of=past_time, created_at=past_time)
    graph_repo.save_node(ev_node)
    
    # Edge created after the knowledge claim, pointing back
    # But we run report at edge's time
    edge_time = as_of + timedelta(hours=1)
    e = EvidenceEdge(edge_id=f"e_temp_{uid}", source_node_id=ev_id, target_node_id=k_id, relationship_type=EdgeRelationship.ASSOCIATED_WITH, evidence_basis="test", as_of=edge_time, created_at=edge_time, deterministic_key="test")
    graph_repo.save_edge(e)
    
    report = svc.generate_report(edge_time)
    findings = [f for f in report.findings if f.canonical_object_id == k_id]
    
    assert any(f.finding_type == IntegrityFindingType.TEMPORAL_ORDER_VIOLATION for f in findings)
    assert any(f.severity == IntegritySeverity.HIGH for f in findings)

def test_lineage_orphaned_reasoning():
    as_of = datetime.now(timezone.utc)
    uid = uuid.uuid4().hex[:8]
    
    graph_repo = EvidenceGraphRepository()
    reasoning_svc = ReasoningService(graph_repo)
    gov_svc = GovernanceService()
    svc = IntegrityService(graph_repo=graph_repo, reasoning_svc=reasoning_svc, gov_svc=gov_svc)
    
    r_id = f"reason_orph_{uid}"
    res = ResearchReasoningResult(
        reasoning_id=r_id,
        as_of=as_of,
        rule_id="RULE_001",
        canonical_statement="Test",
        conclusion_type=ConclusionType.SUPPORTED_INFERENCE,
        source_claim_ids=[],  # Empty, orphaned!
        reasoning_strength="STRONG",
        uncertainty_state="LOW_UNCERTAINTY",
        created_at=as_of
    )
    reasoning_svc._persisted_results[r_id] = res
    
    report = svc.generate_report(as_of)
    findings = [f for f in report.findings if f.canonical_object_id == r_id]
    
    assert len(findings) >= 2
    assert any(f.finding_type == IntegrityFindingType.ORPHANED_REASONING for f in findings)
    assert any(f.finding_type == IntegrityFindingType.GOVERNANCE_LINEAGE_GAP for f in findings)
