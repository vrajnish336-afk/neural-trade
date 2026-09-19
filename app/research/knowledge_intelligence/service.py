from datetime import datetime, timezone
from typing import List, Optional
from app.research.knowledge_intelligence.models import (
    ResearchKnowledgeClaim, KnowledgePattern, KnowledgeGap
)
from app.research.knowledge_intelligence.synthesizer import KnowledgeSynthesizer
from app.research.governance.service import GovernanceService
from app.research.governance.models import ResearchAuditEvent

class KnowledgeIntelligenceService:
    def __init__(self):
        self.synthesizer = KnowledgeSynthesizer()
        self.governance_service = GovernanceService()
        self.claims: List[ResearchKnowledgeClaim] = []
        self.patterns: List[KnowledgePattern] = []
        self.gaps: List[KnowledgeGap] = []

    def run_synthesis(self, research_identity: str, as_of: datetime) -> Optional[ResearchKnowledgeClaim]:
        """Synthesize knowledge for a specific research identity."""
        claim = self.synthesizer.synthesize_knowledge(research_identity, as_of)
        if claim:
            self.claims.append(claim)
            self._audit_claim(claim)
        return claim
        
    def detect_global_patterns(self, as_of: datetime) -> List[KnowledgePattern]:
        """Detect patterns across all currently synthesized claims."""
        new_patterns = self.synthesizer.extract_patterns(self.claims, as_of)
        self.patterns.extend(new_patterns)
        return new_patterns
        
    def generate_strategic_gaps(self, as_of: datetime) -> List[KnowledgeGap]:
        """Generate unresolved research questions/gaps."""
        new_gaps = self.synthesizer.generate_research_gaps(self.claims, self.patterns, as_of)
        self.gaps.extend(new_gaps)
        return new_gaps

    def _audit_claim(self, claim: ResearchKnowledgeClaim):
        # Register the knowledge synthesis event in Phase 46 Governance
        audit = ResearchAuditEvent(
            event_type="KNOWLEDGE_SYNTHESIS_CREATED",
            research_identity_hash=claim.claim_id, # Using claim_id as the governed entity here
            source_id="phase_51_engine",
            reason=f"Synthesized knowledge state: {claim.knowledge_state.value}",
            as_of=claim.as_of
        )
        self.governance_service.audits.append(audit)
