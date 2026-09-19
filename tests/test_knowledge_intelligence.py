import pytest
from datetime import datetime, timezone
from app.research.knowledge_intelligence.models import (
    KnowledgeState, ResearchKnowledgeClaim, KnowledgePattern, PatternFamily, KnowledgeGap
)
from app.research.knowledge_intelligence.service import KnowledgeIntelligenceService
from app.research.synthesis.models import KnowledgeSynthesis
from app.research.revalidation.models import RevalidationAssessment, RevalidationAssessmentState
from app.research.evidence_graph.models import EvidenceNode, NodeType
from app.research.replication.models import EvidenceStrengthLevel

def test_knowledge_synthesis_insufficient_evidence():
    svc = KnowledgeIntelligenceService()
    claim = svc.run_synthesis("hyp_missing_12345", datetime.now(timezone.utc))
    assert claim is None

def test_knowledge_synthesis_revalidation_integration():
    svc = KnowledgeIntelligenceService()
    
    # Mock Phase 33
    syn = KnowledgeSynthesis(
        synthesis_id="s1", research_identity="hyp_123", topic="t", as_of=datetime(2023,1,1, tzinfo=timezone.utc),
        confidence_state="SUPPORTED", supporting_evidence=["e1", "e2", "e3"]
    )
    svc.synthesizer.syn_repo.save_synthesis(syn)
    
    # Mock Phase 50
    rev = RevalidationAssessment(
        assessment_id="r1", hypothesis_id="h1", validation_id="v1", research_identity="hyp_123",
        assessment_state=RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL,
        as_of=datetime(2023,1,1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    svc.synthesizer.rev_repo.save_result(rev)
    svc.synthesizer.syn_repo.get_all_syntheses = lambda: [syn]
    svc.synthesizer.rev_repo.get_all_results = lambda: [rev]
    
    # Needs some graph nodes to avoid crash in normalizer
    svc.synthesizer.graph_repo.save_node(EvidenceNode(
        node_id="hyp_node", identity_hash="hyp_123", node_type=NodeType.HYPOTHESIS,
        source_id="mock", source_type="hypothesis",
        created_at=datetime(2022,1,1, tzinfo=timezone.utc), as_of=datetime(2022,1,1, tzinfo=timezone.utc)
    ))
    
    claim = svc.run_synthesis("hyp_123", datetime(2023,1,2, tzinfo=timezone.utc))
    assert claim.knowledge_state == KnowledgeState.WEAKENED
    assert "weakened by revalidation" in claim.canonical_statement

def test_pattern_detection():
    svc = KnowledgeIntelligenceService()
    
    # Create claims with dataset issues
    for i in range(4):
        c = ResearchKnowledgeClaim(
            claim_id=f"c{i}", canonical_statement="t", knowledge_state=KnowledgeState.WEAKENED,
            scope={"dataset_scope": ["TEST_DATA"], "timeframe_scope": [], "regime_scope": [], "cost_scope": [], "methodology_scope": []},
            as_of=datetime(2023,1,1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
        )
        svc.claims.append(c)
        
    patterns = svc.detect_global_patterns(datetime(2023,1,2, tzinfo=timezone.utc))
    assert len(patterns) == 1
    assert patterns[0].pattern_family == PatternFamily.DATASET
    assert "TEST_DATA" in patterns[0].datasets_involved
    
def test_gap_generation():
    svc = KnowledgeIntelligenceService()
    c = ResearchKnowledgeClaim(
        claim_id="c1", canonical_statement="t", knowledge_state=KnowledgeState.INCONCLUSIVE,
        scope={"dataset_scope": [], "timeframe_scope": [], "regime_scope": [], "cost_scope": [], "methodology_scope": []},
        as_of=datetime(2023,1,1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
    )
    svc.claims.append(c)
    
    gaps = svc.generate_strategic_gaps(datetime(2023,1,2, tzinfo=timezone.utc))
    assert len(gaps) == 1
    assert gaps[0].required_evidence_type == "INDEPENDENT_DATASET_TEST"

def test_governance_audit():
    svc = KnowledgeIntelligenceService()
    syn = KnowledgeSynthesis(
        synthesis_id="s1", research_identity="hyp_test_gov", topic="t", as_of=datetime(2023,1,1, tzinfo=timezone.utc),
        confidence_state="SUPPORTED", supporting_evidence=["e1"]
    )
    svc.synthesizer.syn_repo.save_synthesis(syn)
    
    svc.synthesizer.graph_repo.save_node(EvidenceNode(
        node_id="hyp_node", identity_hash="hyp_test_gov", node_type=NodeType.HYPOTHESIS,
        source_id="mock", source_type="hypothesis",
        created_at=datetime(2022,1,1, tzinfo=timezone.utc), as_of=datetime(2022,1,1, tzinfo=timezone.utc)
    ))
    
    claim = svc.run_synthesis("hyp_test_gov", datetime(2023,1,2, tzinfo=timezone.utc))
    
    assert len(svc.governance_service.audits) == 1
    assert svc.governance_service.audits[0].event_type == "KNOWLEDGE_SYNTHESIS_CREATED"
