from typing import List, Dict, Optional
from datetime import datetime
import hashlib

from app.research.meta_analysis.models import (
    MetaEvidenceUnit, MetaResearchConclusion, MetaResearchStatus,
    IndependenceClassification, MultipleTestingState, SelectionBiasState,
    EvidenceCoverageReport
)
from app.research.meta_analysis.independence import IndependenceClassifier

class MetaAnalysisEngine:

    @staticmethod
    def _generate_statement(status: MetaResearchStatus, positive: int, total: int, ind_count: int, gap: str = "") -> str:
        if status == MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE:
            return f"Evidence strongly supports the hypothesis across {ind_count} independent datasets/periods without major contradiction."
        elif status == MetaResearchStatus.SUPPORTED_BUT_CONDITIONAL:
            return f"Evidence supports the hypothesis but is conditional on regime, timeframe, or specific parameter boundaries."
        elif status == MetaResearchStatus.PROMISING_BUT_FRAGILE:
            return f"Initial evidence is positive ({positive}/{total}), but independent sample size is too fragile ({ind_count}) or cost-sensitive."
        elif status == MetaResearchStatus.CONFLICTED:
            return f"Evidence is fundamentally conflicted. Contradictions exist between independent datasets or methodologies."
        elif status == MetaResearchStatus.FALSIFIED_WITHIN_TESTED_SCOPE:
            return f"Evidence structurally rejects the hypothesis in the tested bounds."
        elif status == MetaResearchStatus.NOT_POOLABLE:
            return f"Provided evidence spans incompatible metrics or regimes and cannot be pooled safely."
        else:
            return f"Insufficient evidence to form a systemic conclusion. {gap}"

    @staticmethod
    def synthesize(
        research_identity_hash: str,
        units: List[MetaEvidenceUnit],
        as_of: datetime,
        causal_limitation: str = "CAUSAL_IDENTIFICATION_LIMITED"
    ) -> MetaResearchConclusion:
        
        # Filter strict As_Of
        valid_units = [u for u in units if u.as_of <= as_of]
        
        ind_count, mt_state, sb_state = IndependenceClassifier.assess_corpus(valid_units)
        
        total = len(valid_units)
        positives = [u for u in valid_units if u.result_direction == "POSITIVE"]
        negatives = [u for u in valid_units if u.result_direction == "NEGATIVE"]
        contradictions = [u for u in valid_units if u.contradiction_state == "CONTRADICTS"]
        stale = [u for u in valid_units if u.revalidation_state == "STALE"]
        
        supporting_ids = [u.evidence_id for u in positives]
        contradicting_ids = [u.evidence_id for u in contradictions]
        
        status = MetaResearchStatus.INSUFFICIENT_EVIDENCE
        confidence = "LOW"
        unresolved = []
        
        if total == 0:
            status = MetaResearchStatus.INSUFFICIENT_EVIDENCE
        elif len(contradictions) >= max(1, total * 0.2) or (len(positives) > 0 and len(negatives) > 0 and ind_count >= 2 and len(negatives) >= len(positives)*0.3):
            # Significant contradictions found
            status = MetaResearchStatus.CONFLICTED
            confidence = "LOW"
            unresolved.append("METHODOLOGY_CONFLICT_GAP")
        elif len(stale) == total and total > 0:
            status = MetaResearchStatus.REQUIRES_REVALIDATION
            unresolved.append("EVIDENCE_DECAY_GAP")
        elif ind_count >= 3 and len(positives) == total:
            status = MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE
            confidence = "HIGH"
        elif ind_count >= 2 and len(positives) >= total * 0.8:
            status = MetaResearchStatus.SUPPORTED_BUT_CONDITIONAL
            confidence = "MODERATE"
        elif ind_count < 2 and len(positives) > 0:
            status = MetaResearchStatus.PROMISING_BUT_FRAGILE
            confidence = "LOW"
            unresolved.append("INDEPENDENT_REPLICATION_GAP")
        elif ind_count >= 2 and len(negatives) == total:
            status = MetaResearchStatus.FALSIFIED_WITHIN_TESTED_SCOPE
            confidence = "HIGH"
        
        statement = MetaAnalysisEngine._generate_statement(status, len(positives), total, ind_count)
        
        # Causal limitation forces confidence caps and explicit statements
        causal_state = causal_limitation
        limitations = ["Meta-analysis cannot upgrade correlational findings to causality."]
        if causal_state == "CAUSAL_IDENTIFICATION_LIMITED" and status == MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE:
            limitations.append("ESTABLISHED_WITHIN_TESTED_SCOPE does not guarantee causal mechanisms or future profitability.")
            
        if mt_state != MultipleTestingState.NO_RISK_DETECTED:
            limitations.append(f"Multiple-testing risk detected: {mt_state.value}")
        if sb_state != SelectionBiasState.NO_BIAS_DETECTED:
            limitations.append("Selection bias risk detected. Negative results may be missing.")
            
        return MetaResearchConclusion(
            research_identity_hash=research_identity_hash,
            statement=statement,
            evidence_state=status,
            confidence_state=confidence,
            independent_evidence_count=ind_count,
            total_evidence_count=total,
            contradiction_count=len(contradictions),
            stale_count=len(stale),
            replication_count=total - 1 if total > 0 else 0, # Raw
            generalization_state="PARTIAL" if ind_count >= 2 else "UNKNOWN",
            causal_state=causal_state,
            selection_bias_state=sb_state,
            multiple_testing_state=mt_state,
            limitations=limitations,
            supporting_evidence_ids=supporting_ids,
            contradicting_evidence_ids=contradicting_ids,
            unresolved_questions=unresolved,
            as_of=as_of
        )
