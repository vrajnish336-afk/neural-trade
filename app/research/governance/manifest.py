from app.research.governance.models import ResearchReproducibilityManifest, CompletenessState

class ManifestEvaluator:
    
    @staticmethod
    def evaluate_completeness(manifest: ResearchReproducibilityManifest) -> CompletenessState:
        required_fields = [
            manifest.dataset_identity,
            manifest.configuration_fingerprint,
            manifest.methodology_version,
            manifest.code_fingerprint
        ]
        
        missing_count = sum(1 for val in required_fields if val in ["UNKNOWN", "MISSING", "NOT_AVAILABLE", ""])
        
        if missing_count == 0:
            return CompletenessState.COMPLETE
        elif missing_count <= 2:
            return CompletenessState.PARTIALLY_REPRODUCIBLE
        else:
            return CompletenessState.INSUFFICIENT_REPRODUCTION_DATA
