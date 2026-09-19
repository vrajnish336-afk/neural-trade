from typing import Optional
from app.research.governance.models import ResearchConclusionRevision
from app.research.governance.change_detection import ChangeCategory
from app.research.meta_analysis.models import MetaResearchStatus

class ResearchRegressionDetector:
    
    @staticmethod
    def detect_regression(old_conclusion: str, new_conclusion: str, change_context: ChangeCategory) -> bool:
        """
        If inputs remained effectively identical (NO_MATERIAL_CHANGE or AS_OF_CHANGED only)
        and the conclusion degraded heavily, it's a regression alert.
        """
        if change_context not in [ChangeCategory.NO_MATERIAL_CHANGE, ChangeCategory.AS_OF_CHANGED, ChangeCategory.SEED_CHANGED]:
            return False
            
        hierarchy = {
            MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE.value: 10,
            MetaResearchStatus.SUPPORTED_BUT_CONDITIONAL.value: 8,
            MetaResearchStatus.PROMISING_BUT_FRAGILE.value: 6,
            MetaResearchStatus.CONFLICTED.value: 4,
            MetaResearchStatus.REQUIRES_REVALIDATION.value: 3,
            MetaResearchStatus.INSUFFICIENT_EVIDENCE.value: 2,
            MetaResearchStatus.FALSIFIED_WITHIN_TESTED_SCOPE.value: 1,
            MetaResearchStatus.NOT_POOLABLE.value: 0
        }
        
        old_score = hierarchy.get(old_conclusion, 0)
        new_score = hierarchy.get(new_conclusion, 0)
        
        # A drop of 3 or more points without input change implies silent regression
        return (old_score - new_score) >= 3
