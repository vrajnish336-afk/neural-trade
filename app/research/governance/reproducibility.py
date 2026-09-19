from app.research.governance.models import ResearchReproducibilityManifest, ReproducibilityState
from app.research.governance.change_detection import ResearchChangeDetector
from app.research.governance.manifest import ManifestEvaluator, CompletenessState

class ReproducibilityVerifier:
    
    @staticmethod
    def verify(historical: ResearchReproducibilityManifest, current: ResearchReproducibilityManifest) -> ReproducibilityState:
        comp = ManifestEvaluator.evaluate_completeness(historical)
        if comp == CompletenessState.INSUFFICIENT_REPRODUCTION_DATA or comp == CompletenessState.NON_REPRODUCIBLE:
            return ReproducibilityState.INCOMPLETE_MANIFEST
            
        change = ResearchChangeDetector.detect_changes(historical, current)
        
        mapping = {
            "DATA_CHANGED": ReproducibilityState.INPUT_DATA_CHANGED,
            "PARAMETERS_CHANGED": ReproducibilityState.CONFIGURATION_CHANGED,
            "STRATEGY_CHANGED": ReproducibilityState.CONFIGURATION_CHANGED,
            "METHODOLOGY_CHANGED": ReproducibilityState.METHODOLOGY_CHANGED,
            "CODE_CHANGED": ReproducibilityState.CODE_CHANGED,
            "DEPENDENCIES_CHANGED": ReproducibilityState.DEPENDENCY_CHANGED,
            "SCHEMA_CHANGED": ReproducibilityState.SCHEMA_CHANGED,
            "SOURCE_EVIDENCE_CHANGED": ReproducibilityState.SOURCE_EVIDENCE_CHANGED,
            "NO_MATERIAL_CHANGE": ReproducibilityState.REPRODUCIBLE_WITH_SAME_INPUTS
        }
        
        return mapping.get(change.value, ReproducibilityState.NOT_ASSESSABLE)
