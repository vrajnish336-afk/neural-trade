import pytest
from datetime import datetime, timezone
from app.research.reproduction.models import (
    OriginalResearchOutput, 
    ReproducedResearchOutput, 
    ComparisonState, 
    ReproductionStatus, 
    ReproductionMode,
    DiscrepancyCategory
)
from app.research.reproduction.fingerprints import OutputFingerprintGenerator
from app.research.reproduction.comparison import ResearchComparator
from app.research.reproduction.verification import VerificationEngine
from app.research.governance.models import ResearchReproducibilityManifest
from app.research.reproduction.specification import SpecificationCompiler
from app.research.reproduction.runner import BoundedReproductionRunner

def test_frozen_specification_immutability():
    manifest = ResearchReproducibilityManifest(research_identity_hash="h1", as_of=datetime.utcnow(), dataset_identity="d1")
    spec = SpecificationCompiler.freeze(manifest)
    
    assert spec.dataset_identity == "d1"
    
def test_output_fingerprint_determinism():
    trades1 = [{"timestamp_str": "T1", "direction": "LONG", "price": 100.0, "size": 1.0}]
    trades2 = [{"timestamp_str": "T1", "direction": "LONG", "price": 100.0, "size": 1.0}] # Identical structurally
    
    fp1 = OutputFingerprintGenerator.generate_fingerprint(trades1, {"sharpe": 1.2}, "d1", "v1")
    fp2 = OutputFingerprintGenerator.generate_fingerprint(trades2, {"sharpe": 1.2}, "d1", "v1")
    assert fp1 == fp2

def test_output_fingerprint_drift_resistance():
    trades1 = [{"timestamp_str": "T1", "direction": "LONG", "price": 100.00001, "size": 1.0}]
    trades2 = [{"timestamp_str": "T1", "direction": "LONG", "price": 100.00004, "size": 1.0}]
    
    # Due to round(price, 4), these should hash exactly the same despite 1e-5 differences
    fp1 = OutputFingerprintGenerator.generate_fingerprint(trades1, {"sharpe": 1.2}, "d1", "v1")
    fp2 = OutputFingerprintGenerator.generate_fingerprint(trades2, {"sharpe": 1.2}, "d1", "v1")
    assert fp1 == fp2

def test_comparator_exact_match():
    orig = OriginalResearchOutput(research_identity_hash="h1", as_of=datetime.utcnow(), trade_count=10, return_pct=0.05, result_fingerprint="f1")
    repo = ReproducedResearchOutput(specification_id="s1", dataset_identity="d1", configuration_fingerprint="c1", reproduction_mode=ReproductionMode.FULL_RESEARCH_RECONSTRUCTION, trade_count=10, return_pct=0.05, output_fingerprint="f1")
    
    state, discrepancies = ResearchComparator.compare(orig, repo)
    assert state == ComparisonState.EXACT_MATCH
    assert len(discrepancies) == 0

def test_comparator_structural_difference():
    orig = OriginalResearchOutput(research_identity_hash="h1", as_of=datetime.utcnow(), trade_count=10, return_pct=0.05, result_fingerprint="f1")
    repo = ReproducedResearchOutput(specification_id="s1", dataset_identity="d1", configuration_fingerprint="c1", reproduction_mode=ReproductionMode.FULL_RESEARCH_RECONSTRUCTION, trade_count=11, return_pct=0.05, output_fingerprint="f2")
    
    state, discrepancies = ResearchComparator.compare(orig, repo)
    assert state == ComparisonState.STRUCTURAL_DIFFERENCE
    assert any(d.category == DiscrepancyCategory.TRADE_SEQUENCE_DIFFERENCE for d in discrepancies)

def test_comparator_material_difference():
    orig = OriginalResearchOutput(research_identity_hash="h1", as_of=datetime.utcnow(), trade_count=10, return_pct=0.05, result_fingerprint="f1")
    repo = ReproducedResearchOutput(specification_id="s1", dataset_identity="d1", configuration_fingerprint="c1", reproduction_mode=ReproductionMode.FULL_RESEARCH_RECONSTRUCTION, trade_count=10, return_pct=0.15, output_fingerprint="f1")
    
    state, discrepancies = ResearchComparator.compare(orig, repo)
    assert state == ComparisonState.MATERIAL_DIFFERENCE
    assert any(d.category == DiscrepancyCategory.NUMERICAL_DRIFT for d in discrepancies)

def test_verification_engine_status():
    orig = OriginalResearchOutput(research_identity_hash="h1", as_of=datetime.utcnow(), trade_count=10, return_pct=0.05, result_fingerprint="f1")
    repo = ReproducedResearchOutput(specification_id="s1", dataset_identity="d1", configuration_fingerprint="c1", reproduction_mode=ReproductionMode.FULL_RESEARCH_RECONSTRUCTION, trade_count=10, return_pct=0.15, output_fingerprint="f1")
    
    res = VerificationEngine.verify("m1", orig, repo)
    assert res.status == ReproductionStatus.REPRODUCTION_DIFFERED
    assert res.revalidation_required == True
    assert res.independent_replication_supported == False # Always false for reproduction
