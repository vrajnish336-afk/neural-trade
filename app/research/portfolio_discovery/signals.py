from typing import Dict, Any, Tuple
from app.research.portfolio_stress.models import PortfolioFailureAssessment

class PortfolioSignalExtractor:
    
    @staticmethod
    def extract_gap(failure: PortfolioFailureAssessment) -> str:
        mapping = {
            PortfolioFailureAssessment.CORRELATED_FAILURE: "CORRELATED_FAILURE_GAP",
            PortfolioFailureAssessment.SYNCHRONIZED_DOWNSIDE: "SYNCHRONIZED_DOWNSIDE_GAP",
            PortfolioFailureAssessment.REGIME_FRAGILITY: "REGIME_GENERALIZATION_GAP",
            PortfolioFailureAssessment.COST_FRAGILITY: "COST_RESILIENCE_GAP",
            PortfolioFailureAssessment.SINGLE_CANDIDATE_DEPENDENCY: "SINGLE_CANDIDATE_DEPENDENCY_GAP",
            PortfolioFailureAssessment.TIMEFRAME_CONCENTRATION: "TIMEFRAME_DIVERSIFICATION_GAP",
            PortfolioFailureAssessment.TEMPORAL_INSTABILITY: "TEMPORAL_PORTFOLIO_GAP",
            PortfolioFailureAssessment.DATA_INTEGRITY_FAILURE: "DATA_INTEGRITY_GAP",
            PortfolioFailureAssessment.INSUFFICIENT_EVIDENCE: "PORTFOLIO_SAMPLE_SIZE_GAP",
            PortfolioFailureAssessment.MULTIPLE_FAILURE_MODES: "COMPLEX_FAILURE_GAP",
            PortfolioFailureAssessment.NO_MATERIAL_FAILURE_DETECTED: "NO_GAP"
        }
        return mapping.get(failure, "UNKNOWN_GAP")

    @staticmethod
    def generate_hypothesis(gap: str, candidates: list) -> Tuple[str, str, str]:
        """
        Returns (question_text, hypothesis, falsification_condition)
        """
        c_str = ", ".join(candidates) if candidates else "the candidates"
        
        if gap == "CORRELATED_FAILURE_GAP":
            return (
                f"Does the correlated failure between {c_str} persist across differing market regimes?",
                f"If {c_str} are isolated by regime, they will exhibit independent failure behavior in at least one regime.",
                f"They fail together in ALL tested regimes."
            )
        elif gap == "COST_RESILIENCE_GAP":
            return (
                f"Does {c_str} lose portfolio viability under structurally higher friction environments?",
                f"At 2x transaction friction, the portfolio correlation benefits fail to overcome the individual negative yield.",
                f"The portfolio yields positive net expectation even at 2x friction."
            )
        elif gap == "SINGLE_CANDIDATE_DEPENDENCY_GAP":
            return (
                f"Is the portfolio's edge entirely dependent on {c_str}?",
                f"Removing {c_str} destroys the portfolio Sharpe and returns it to a random walk expectation.",
                f"Removing {c_str} leaves the remaining portfolio with a statistically significant positive Sharpe."
            )
        elif gap == "PORTFOLIO_SAMPLE_SIZE_GAP":
            return (
                "Is the observed portfolio behavior statistically robust?",
                "Expanding the historical dataset by 100% will preserve the existing correlation limits.",
                "Correlation changes by > 20% when sample size is expanded."
            )
            
        return (
            f"Investigate {gap} behavior in the portfolio.",
            "The observed failure is structurally persistent.",
            "The failure does not persist in out-of-sample data."
        )
