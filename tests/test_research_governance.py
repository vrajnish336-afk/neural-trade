import pytest
from datetime import datetime, timezone
from app.research.governance.models import (
    ResearchReproducibilityManifest, ResearchConclusionRevision, CompletenessState, ReproducibilityState, ChangeCategory
)
from app.research.governance.fingerprints import FingerprintGenerator
from app.research.governance.manifest import ManifestEvaluator
from app.research.governance.change_detection import ResearchChangeDetector
from app.research.governance.reproducibility import ReproducibilityVerifier
from app.research.governance.regression import ResearchRegressionDetector
from app.research.meta_analysis.models import MetaResearchStatus

def test_fingerprint_redaction():
    config = {
        "learning_rate": 0.01,
        "api_key": "secret123",
        "nested": {"token_auth": "xyz"}
    }
    clean = FingerprintGenerator._redact_secrets(config)
    assert clean["learning_rate"] == 0.01
    assert clean["api_key"] == "[REDACTED]"
    assert clean["nested"]["token_auth"] == "[REDACTED]"
    
    fp1 = FingerprintGenerator.generate_config_fingerprint(config)
    
    config2 = {
        "learning_rate": 0.01,
        "api_key": "different_secret",
        "nested": {"token_auth": "abc"}
    }
    fp2 = FingerprintGenerator.generate_config_fingerprint(config2)
    assert fp1 == fp2 # Identical because secrets are ignored

def test_manifest_completeness():
    m = ResearchReproducibilityManifest(
        research_identity_hash="h1",
        as_of=datetime.utcnow()
    )
    # Default is UNKNOWN for fields
    assert ManifestEvaluator.evaluate_completeness(m) == CompletenessState.INSUFFICIENT_REPRODUCTION_DATA
    
    m.dataset_identity = "d1"
    m.configuration_fingerprint = "c1"
    m.methodology_version = "v1"
    m.code_fingerprint = "code1"
    assert ManifestEvaluator.evaluate_completeness(m) == CompletenessState.COMPLETE

def test_change_detection():
    d = datetime.utcnow()
    m1 = ResearchReproducibilityManifest(research_identity_hash="h1", dataset_identity="d1", as_of=d)
    m2 = ResearchReproducibilityManifest(research_identity_hash="h1", dataset_identity="d2", as_of=d)
    
    assert ResearchChangeDetector.detect_changes(m1, m2) == ChangeCategory.DATA_CHANGED

def test_regression_detection():
    # If inputs unchanged, but we drop from ESTABLISHED to CONFLICTED => Regression!
    assert ResearchRegressionDetector.detect_regression(
        MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE.value,
        MetaResearchStatus.CONFLICTED.value,
        ChangeCategory.NO_MATERIAL_CHANGE
    ) == True
    
    # If data changed, it's NOT a regression, it's a valid scientific shift
    assert ResearchRegressionDetector.detect_regression(
        MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE.value,
        MetaResearchStatus.CONFLICTED.value,
        ChangeCategory.DATA_CHANGED
    ) == False
