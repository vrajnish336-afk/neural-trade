from app.research.governance.models import ResearchReproducibilityManifest
from app.research.reproduction.models import FrozenResearchSpecification

class SpecificationCompiler:
    
    @staticmethod
    def freeze(manifest: ResearchReproducibilityManifest) -> FrozenResearchSpecification:
        return FrozenResearchSpecification(
            research_identity_hash=manifest.research_identity_hash,
            manifest_id=manifest.manifest_id,
            experiment_id=manifest.experiment_id,
            dataset_identity=manifest.dataset_identity,
            dataset_version=manifest.dataset_version,
            historical_start=manifest.historical_start,
            historical_end=manifest.historical_end,
            as_of=manifest.as_of,
            seed=manifest.seed,
            strategy_identity=manifest.strategy_identity,
            strategy_version=manifest.strategy_version,
            parameter_fingerprint=manifest.parameter_fingerprint,
            configuration_fingerprint=manifest.configuration_fingerprint,
            methodology_version=manifest.methodology_version,
            code_fingerprint=manifest.code_fingerprint,
            dependency_fingerprint=manifest.dependency_fingerprint,
            schema_version=manifest.schema_version,
            analysis_version=manifest.analysis_version,
            source_evidence_ids=manifest.source_evidence_ids,
            cost_assumptions={"frozen": True},
            execution_assumptions={"frozen": True},
            validation_boundaries={"frozen": True}
        )
