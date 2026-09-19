from datetime import datetime
from app.research.meta_analysis.models import MetaEvidenceUnit

class MetaNormalizer:
    
    @staticmethod
    def normalize_portfolio_stress(stress_result) -> MetaEvidenceUnit:
        # Pseudo-coercion based on typical stress_result structure from Phase 43
        is_positive = "NEGATIVE"
        if stress_result.resilience.value in ["ROBUST_UNDER_TESTED_SCENARIOS", "CONDITIONALLY_RESILIENT"]:
            is_positive = "POSITIVE"
            
        return MetaEvidenceUnit(
            research_identity_hash=stress_result.portfolio_id,
            source_type="PORTFOLIO_STRESS",
            source_id=stress_result.result_id,
            dataset_identity="UNKNOWN",
            observed_at=stress_result.as_of,
            as_of=stress_result.as_of,
            portfolio_identity=stress_result.portfolio_id,
            sample_size=getattr(stress_result, "sample_size", 0),
            result_direction=is_positive
        )
