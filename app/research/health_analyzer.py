from typing import List
from app.research.track_record_models import PaperObservation, StrategyHealthState

class StrategyHealthAnalyzer:
    """Deterministically evaluates the health of a strategy based on its long-term observations."""
    
    @staticmethod
    def evaluate(observations: List[PaperObservation]) -> tuple[StrategyHealthState, str]:
        # Sort chronologically to be safe
        observations = sorted(observations, key=lambda x: x.observation_start)
        
        if len(observations) < 3:
            return StrategyHealthState.INSUFFICIENT_HISTORY, "Requires at least 3 forward observations."
            
        recent = observations[-3:]
        
        # Check for Critical (e.g. 3 consecutive significantly degraded or huge drawdown)
        if all(obs.drift_state == "SIGNIFICANTLY_DEGRADED" for obs in recent):
            return StrategyHealthState.CRITICAL, "3 consecutive significantly degraded observations."
            
        # Check for Data Quality (overlapping or zero trades where expected)
        # Assuming Data Quality is mostly caught during insertion, but we can check bounds
        for i in range(1, len(observations)):
            if observations[i].observation_start < observations[i-1].observation_end:
                return StrategyHealthState.DATA_QUALITY_ISSUE, "Overlapping observations detected in history."
                
        # Check for Degraded
        degraded_count = sum(1 for obs in recent if obs.drift_state in ["DEGRADED", "SIGNIFICANTLY_DEGRADED"])
        if degraded_count >= 2:
            return StrategyHealthState.DEGRADED, "Multiple recent degraded observations."
            
        # Check for Watch
        if recent[-1].drift_state in ["DEGRADED", "SIGNIFICANTLY_DEGRADED"]:
            return StrategyHealthState.WATCH, "Most recent observation degraded."
            
        return StrategyHealthState.HEALTHY, "Strategy performing within historical parameters."
