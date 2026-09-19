from typing import List
from datetime import datetime
from app.research.meta_analysis.models import MetaEvidenceUnit, MetaResearchConclusion
from app.research.meta_analysis.synthesis import MetaAnalysisEngine

class MetaAnalysisService:
    def synthesize_evidence(self, identity_hash: str, units: List[MetaEvidenceUnit], as_of: datetime) -> MetaResearchConclusion:
        return MetaAnalysisEngine.synthesize(identity_hash, units, as_of)
