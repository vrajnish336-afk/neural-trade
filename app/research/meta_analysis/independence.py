from typing import List, Tuple
from app.research.meta_analysis.models import (
    MetaEvidenceUnit, IndependenceClassification, MultipleTestingState, SelectionBiasState
)

class IndependenceClassifier:
    
    @staticmethod
    def classify_pair(a: MetaEvidenceUnit, b: MetaEvidenceUnit) -> IndependenceClassification:
        # Same exact source ID is same experiment
        if a.source_id == b.source_id:
            return IndependenceClassification.SAME_EXPERIMENT
            
        # Same dataset and same historical bounds => Replay
        same_data = (a.dataset_identity == b.dataset_identity)
        same_bounds = False
        if a.historical_start and b.historical_start and a.historical_end and b.historical_end:
             same_bounds = (a.historical_start == b.historical_start and a.historical_end == b.historical_end)
        elif not a.historical_start and not b.historical_start:
             same_bounds = True
             
        if same_data and same_bounds:
            if a.seed != b.seed:
                return IndependenceClassification.DIFFERENT_SEED_ONLY
            return IndependenceClassification.SAME_DATASET_REPLAY
            
        if same_data:
            # Overlapping bounds check
            if a.historical_start and b.historical_end and a.historical_start <= b.historical_end and a.historical_end >= b.historical_start:
                return IndependenceClassification.OVERLAPPING_DATA
            return IndependenceClassification.INDEPENDENT_DATA
            
        # Completely different dataset identity
        return IndependenceClassification.INDEPENDENT_EXPERIMENT

    @staticmethod
    def assess_corpus(units: List[MetaEvidenceUnit]) -> Tuple[int, MultipleTestingState, SelectionBiasState]:
        if not units:
            return 0, MultipleTestingState.NO_RISK_DETECTED, SelectionBiasState.NO_BIAS_DETECTED
            
        # Naive greedy independence counter
        independent_units = []
        for u in units:
            is_independent = True
            for ind_u in independent_units:
                cls = IndependenceClassifier.classify_pair(u, ind_u)
                if cls in [
                    IndependenceClassification.SAME_EXPERIMENT,
                    IndependenceClassification.SAME_DATASET_REPLAY,
                    IndependenceClassification.SAME_TIME_RANGE_REPLAY,
                    IndependenceClassification.DIFFERENT_SEED_ONLY,
                    IndependenceClassification.OVERLAPPING_DATA
                ]:
                    is_independent = False
                    break
            if is_independent:
                independent_units.append(u)
                
        ind_count = len(independent_units)
        total = len(units)
        
        mt_state = MultipleTestingState.NO_RISK_DETECTED
        sb_state = SelectionBiasState.NO_BIAS_DETECTED
        
        # Heuristics for Multiple Testing Risk
        if total > 10 and ind_count <= 2:
            mt_state = MultipleTestingState.REPEATED_DATASET_REPLAY
        elif total > 30 and (ind_count / total) < 0.2:
            mt_state = MultipleTestingState.HIGH_EXPERIMENT_REUSE
            
        # Heuristics for Selection Bias Risk
        # E.g., if all reported tests are POSITIVE but we know there are tons of missing seeds
        positives = sum(1 for u in units if u.result_direction == "POSITIVE")
        if total > 5 and positives == total and mt_state != MultipleTestingState.NO_RISK_DETECTED:
            sb_state = SelectionBiasState.SELECTION_BIAS_RISK
            
        return ind_count, mt_state, sb_state
