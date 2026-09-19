from app.research.governance.models import ResearchReproducibilityManifest, ChangeCategory

class ResearchChangeDetector:
    
    @staticmethod
    def detect_changes(old: ResearchReproducibilityManifest, new: ResearchReproducibilityManifest) -> ChangeCategory:
        if old.dataset_identity != new.dataset_identity or old.dataset_version != new.dataset_version:
            return ChangeCategory.DATA_CHANGED
            
        if old.methodology_version != new.methodology_version:
            return ChangeCategory.METHODOLOGY_CHANGED
            
        if old.code_fingerprint != new.code_fingerprint:
            return ChangeCategory.CODE_CHANGED
            
        if old.dependency_fingerprint != new.dependency_fingerprint:
            return ChangeCategory.DEPENDENCIES_CHANGED
            
        if old.schema_version != new.schema_version:
            return ChangeCategory.SCHEMA_CHANGED
            
        if old.configuration_fingerprint != new.configuration_fingerprint:
            return ChangeCategory.PARAMETERS_CHANGED
            
        if set(old.source_evidence_ids) != set(new.source_evidence_ids):
            return ChangeCategory.SOURCE_EVIDENCE_CHANGED
            
        if old.seed != new.seed:
            return ChangeCategory.SEED_CHANGED
            
        if old.as_of != new.as_of:
            return ChangeCategory.AS_OF_CHANGED
            
        return ChangeCategory.NO_MATERIAL_CHANGE
