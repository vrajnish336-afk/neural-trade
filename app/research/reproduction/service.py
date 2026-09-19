from app.research.reproduction.models import (
    OriginalResearchOutput, 
    ReproductionMode, 
    IndependentVerificationResult
)
from app.research.governance.models import ResearchReproducibilityManifest
from app.research.reproduction.specification import SpecificationCompiler
from app.research.reproduction.runner import BoundedReproductionRunner
from app.research.reproduction.verification import VerificationEngine

class ReproductionService:
    
    @staticmethod
    def run_reproduction(manifest: ResearchReproducibilityManifest, original_output: OriginalResearchOutput, mode: ReproductionMode) -> IndependentVerificationResult:
        # 1. Freeze
        spec = SpecificationCompiler.freeze(manifest)
        
        # 2. Reconstruct safely via bounded runner
        reproduced = BoundedReproductionRunner.run(spec, mode)
        
        # 3. Verify
        return VerificationEngine.verify(manifest.manifest_id, original_output, reproduced)
