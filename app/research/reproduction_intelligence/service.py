from typing import List
from app.research.reproduction.models import IndependentVerificationResult
from app.research.governance.change_detection import ChangeCategory
from app.research.reproduction_intelligence.models import (
    ReproductionDiscrepancyAnalysis, DiscrepancyResearchPriority
)
from app.research.reproduction_intelligence.attribution import AttributionEngine
from app.research.reproduction_intelligence.impact import ImpactAnalyzer
from app.research.governance.models import GovernanceState

class DiscrepancyIntelligenceService:
    
    @staticmethod
    def analyze_discrepancy(
        verification_result: IndependentVerificationResult,
        detected_changes: List[ChangeCategory]
    ) -> ReproductionDiscrepancyAnalysis:
        
        # 1. Attribute Root Causes
        discrepancy_cats = [d.category for d in verification_result.discrepancies]
        root_causes = AttributionEngine.attribute(detected_changes, discrepancy_cats)
        
        # 2. Assess Impact
        impact = ImpactAnalyzer.analyze(verification_result)
        
        # 3. Determine Priority (Phase 32 Integration)
        priority = DiscrepancyResearchPriority.NO_ACTION_REQUIRED
        if impact.governance_impact in [GovernanceState.REVALIDATION_REQUIRED, GovernanceState.CONCLUSION_CONFLICT]:
            priority = DiscrepancyResearchPriority.CRITICAL_REVALIDATION
        elif impact.governance_impact == GovernanceState.INSUFFICIENT_AUDIT_TRAIL:
            priority = DiscrepancyResearchPriority.HIGH_PRIORITY_GAP
            
        return ReproductionDiscrepancyAnalysis(
            reproduction_id=verification_result.reproduction_id,
            manifest_id=verification_result.manifest_id,
            status="ANALYZED",
            root_causes=root_causes,
            impact=impact,
            research_priority=priority,
            limitations=["Analysis cannot definitively rule out hidden interactions between multiple isolated variables."]
        )
