import pytest
from datetime import datetime, timezone
from app.research.knowledge_intelligence.models import (
    KnowledgeState, ResearchKnowledgeClaim, KnowledgePattern, PatternFamily, KnowledgeGap
)
from app.research.knowledge_intelligence.service import KnowledgeIntelligenceService
from app.research.synthesis.models import KnowledgeSynthesis
from app.research.revalidation.models import RevalidationAssessment, RevalidationAssessmentState
from app.research.evidence_graph.models import EvidenceNode, NodeType

svc = KnowledgeIntelligenceService()
syn = KnowledgeSynthesis(
    synthesis_id="s1", research_identity="hyp_123", topic="t", as_of=datetime(2023,1,1, tzinfo=timezone.utc),
    confidence_state="SUPPORTED", supporting_evidence=["e1", "e2", "e3"]
)
svc.synthesizer.syn_repo.save_synthesis(syn)

rev = RevalidationAssessment(
    assessment_id="r1", hypothesis_id="h1", validation_id="v1", research_identity="hyp_123",
    assessment_state=RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL,
    as_of=datetime(2023,1,1, tzinfo=timezone.utc), created_at=datetime.now(timezone.utc)
)
svc.synthesizer.rev_repo.save_result(rev)

print("Syntheses:", len(svc.synthesizer.syn_repo.get_all_syntheses()))
print("Revalidations:", len(svc.synthesizer.rev_repo.get_all_results()))
