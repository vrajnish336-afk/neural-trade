from datetime import datetime, timezone
import hashlib
from typing import List

from app.research.planner.models import ResearchPriorityBreakdown
from app.research.portfolio_stress.models import PortfolioStressResult, PortfolioFailureAssessment, StressSeverity
from app.research.portfolio_discovery.models import (
    PortfolioResearchQuestion, PortfolioResearchQuestionState, NoveltyState
)
from app.research.portfolio_discovery.signals import PortfolioSignalExtractor

class PortfolioDiscoveryEngine:
    
    @staticmethod
    def _hash_identity(portfolio_id: str, gap: str, as_of: datetime) -> str:
        s = f"{portfolio_id}_{gap}_{as_of.date().isoformat()}"
        return hashlib.sha256(s.encode()).hexdigest()[:12]

    @staticmethod
    def evaluate(stress_result: PortfolioStressResult, existing_questions: List[PortfolioResearchQuestion] = None) -> PortfolioResearchQuestion:
        if existing_questions is None:
            existing_questions = []
            
        gap = PortfolioSignalExtractor.extract_gap(stress_result.stress_assessment)
        question_text, hypothesis, falsification = PortfolioSignalExtractor.generate_hypothesis(
            gap, stress_result.affected_candidates
        )
        
        # Calculate Information Value Heuristic
        # High severity -> more information value in fixing it.
        # But this doesn't mean allocating money, it means doing research.
        severity_score = {
            StressSeverity.LOW: 0.1,
            StressSeverity.MODERATE: 0.3,
            StressSeverity.HIGH: 0.7,
            StressSeverity.CRITICAL: 1.0,
            StressSeverity.INSUFFICIENT_EVIDENCE: 0.5
        }.get(stress_result.severity, 0.0)
        
        # Build Priority Breakdown
        pb = ResearchPriorityBreakdown(
            evidence_gap_weight=0.5 if stress_result.sample_size < 100 else 0.1,
            uncertainty_weight=severity_score,
            conflict_weight=0.0,
            information_gain_weight=severity_score,
            feasibility_weight=0.8, # We can computationally test this
            novelty_weight=0.0, # Checked below
            reproducibility_weight=1.0,
            expected_information_value_heuristic=severity_score * 0.8
        )
        
        # Novelty check
        identity = PortfolioDiscoveryEngine._hash_identity(stress_result.portfolio_id, gap, stress_result.as_of)
        
        novelty = NoveltyState.NOVEL
        state = PortfolioResearchQuestionState.REVIEW_REQUIRED
        
        for eq in existing_questions:
            eq_identity = PortfolioDiscoveryEngine._hash_identity(eq.portfolio_id, eq.research_gap, eq.as_of)
            if eq_identity == identity:
                if eq.status in [PortfolioResearchQuestionState.APPROVED_FOR_RESEARCH, PortfolioResearchQuestionState.COMPLETED]:
                    novelty = NoveltyState.ALREADY_RESOLVED
                    state = PortfolioResearchQuestionState.ALREADY_RESOLVED
                else:
                    novelty = NoveltyState.DUPLICATE
                    state = PortfolioResearchQuestionState.DUPLICATE
                break
        
        if gap == "NO_GAP":
            state = PortfolioResearchQuestionState.REJECTED
            pb.expected_information_value_heuristic = 0.0
            
        return PortfolioResearchQuestion(
            portfolio_id=stress_result.portfolio_id,
            source_failure=stress_result.stress_assessment.value,
            research_gap=gap,
            question_text=question_text,
            hypothesis=hypothesis,
            falsification_condition=falsification,
            priority=pb.expected_information_value_heuristic,
            priority_breakdown=pb,
            novelty=novelty,
            evidence_gap="Empirical validation required.",
            uncertainty="High" if severity_score > 0.6 else "Low",
            conflict="None detected",
            feasibility="High",
            staleness="Fresh",
            sample_size_state="INSUFFICIENT" if stress_result.sample_size < 30 else "SUFFICIENT",
            validation_requirements=["Out of sample testing"],
            replication_requirements=["Different Seed", "Walk Forward Window"],
            as_of=stress_result.as_of,
            lineage=[stress_result.result_id],
            status=state
        )
