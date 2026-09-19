import hashlib
from datetime import datetime, timezone
from typing import List, Optional
import logging
from app.research.synthesis.models import KnowledgeSynthesis, ResearchHypothesis, HypothesisStatus, HypothesisType, HypothesisQualityProfile, KnowledgeState
from app.research.synthesis.repository import SynthesisRepository
from app.research.evidence_graph.repository import EvidenceGraphRepository

logger = logging.getLogger(__name__)

class HypothesisGenerator:
    def __init__(self):
        self.repo = SynthesisRepository()
        self.graph_repo = EvidenceGraphRepository()

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def generate_from_synthesis(self, synthesis: KnowledgeSynthesis, as_of: Optional[datetime] = None) -> List[ResearchHypothesis]:
        if not as_of:
            as_of = datetime.now(timezone.utc)
            
        hypotheses = []
        
        # We generate hypotheses deterministically based on gaps and conflicts found in the synthesis
        
        # 1. Conflict Resolution Hypothesis
        if synthesis.confidence_state == KnowledgeState.CONFLICTED:
            h_id = self._deterministic_hash(f"hyp_conflict_{synthesis.synthesis_id}")
            if not self.repo.get_hypothesis(h_id):
                quality = HypothesisQualityProfile(
                    evidence_support=float(len(synthesis.supporting_evidence)),
                    contradiction_level=float(len(synthesis.contradictory_evidence)),
                    testability=1.0, # Deterministically testable if we have a conflict
                    falsifiability=1.0,
                    explanation="Generated to resolve observed conflicts in existing evidence."
                )
                hyp = ResearchHypothesis(
                    hypothesis_id=h_id,
                    research_identity=synthesis.research_identity,
                    hypothesis_text=f"The contradictory evidence in {synthesis.research_identity} can be isolated by separating regime contexts.",
                    hypothesis_type=HypothesisType.CONFLICT_RESOLUTION_HYPOTHESIS,
                    originating_synthesis_id=synthesis.synthesis_id,
                    supporting_node_ids=synthesis.supporting_evidence,
                    contradicting_node_ids=synthesis.contradictory_evidence,
                    expected_observation="Performance will bifurcate cleanly when segregated by volatility regime.",
                    falsification_condition="Performance remains statistically indistinguishable across regimes.",
                    quality_profile=quality,
                    generated_at=as_of,
                    as_of=as_of,
                    status=HypothesisStatus.TESTABLE
                )
                self.repo.save_hypothesis(hyp)
                hypotheses.append(hyp)
                
        # 2. Gap-driven Hypothesis
        for gap_id in synthesis.evidence_gaps:
            gap_node = self.graph_repo.get_node(gap_id)
            if not gap_node: continue
            
            gap_type = gap_node.metadata.get("gap_type", "")
            htype = HypothesisType.GENERALIZATION_HYPOTHESIS
            if "robustness" in gap_type.lower():
                htype = HypothesisType.ROBUSTNESS_HYPOTHESIS
            elif "sample" in gap_type.lower():
                htype = HypothesisType.REPLICATION_HYPOTHESIS
                
            h_id = self._deterministic_hash(f"hyp_gap_{gap_id}_{synthesis.synthesis_id}")
            if not self.repo.get_hypothesis(h_id):
                quality = HypothesisQualityProfile(
                    evidence_support=float(len(synthesis.supporting_evidence)),
                    falsifiability=1.0,
                    testability=1.0,
                    explanation=f"Generated from explicit evidence gap: {gap_type}"
                )
                hyp = ResearchHypothesis(
                    hypothesis_id=h_id,
                    research_identity=synthesis.research_identity,
                    hypothesis_text=f"The findings for {synthesis.research_identity} will hold true when tested against the conditions specified in gap {gap_type}.",
                    hypothesis_type=htype,
                    originating_synthesis_id=synthesis.synthesis_id,
                    originating_gap_ids=[gap_id],
                    supporting_node_ids=synthesis.supporting_evidence,
                    expected_observation="Performance metrics will remain consistent with prior samples.",
                    falsification_condition="Performance degrades below statistical significance thresholds in new sample.",
                    quality_profile=quality,
                    generated_at=as_of,
                    as_of=as_of,
                    status=HypothesisStatus.TESTABLE
                )
                self.repo.save_hypothesis(hyp)
                hypotheses.append(hyp)
                
        return hypotheses
