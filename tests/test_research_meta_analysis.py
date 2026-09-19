import pytest
from datetime import datetime, timezone, timedelta
from app.research.meta_analysis.models import (
    MetaEvidenceUnit, MetaResearchStatus, IndependenceClassification, MultipleTestingState, SelectionBiasState
)
from app.research.meta_analysis.independence import IndependenceClassifier
from app.research.meta_analysis.synthesis import MetaAnalysisEngine

def test_independence_same_experiment():
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    
    assert IndependenceClassifier.classify_pair(u1, u2) == IndependenceClassification.SAME_EXPERIMENT

def test_independence_different_seed_only():
    d1 = datetime(2023, 1, 1)
    d2 = datetime(2023, 6, 1)
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", historical_start=d1, historical_end=d2, seed=42, observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="2", dataset_identity="d1", historical_start=d1, historical_end=d2, seed=99, observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    
    assert IndependenceClassifier.classify_pair(u1, u2) == IndependenceClassification.DIFFERENT_SEED_ONLY

def test_independence_unseen_data():
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="2", dataset_identity="d2", observed_at=datetime.utcnow(), as_of=datetime.utcnow())
    
    assert IndependenceClassifier.classify_pair(u1, u2) == IndependenceClassification.INDEPENDENT_EXPERIMENT

def test_strict_as_of_filtering():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=as_of_date, as_of=as_of_date, result_direction="POSITIVE")
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="2", dataset_identity="d2", observed_at=as_of_date + timedelta(days=1), as_of=as_of_date + timedelta(days=1), result_direction="POSITIVE")
    
    res = MetaAnalysisEngine.synthesize("h1", [u1, u2], as_of_date)
    # Only u1 is included
    assert res.total_evidence_count == 1
    assert res.independent_evidence_count == 1

def test_negative_result_preserved():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=as_of_date, as_of=as_of_date, result_direction="NEGATIVE")
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="2", dataset_identity="d2", observed_at=as_of_date, as_of=as_of_date, result_direction="NEGATIVE")
    
    res = MetaAnalysisEngine.synthesize("h1", [u1, u2], as_of_date)
    assert res.evidence_state == MetaResearchStatus.FALSIFIED_WITHIN_TESTED_SCOPE
    assert res.independent_evidence_count == 2
    
def test_conflicting_evidence():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=as_of_date, as_of=as_of_date, result_direction="POSITIVE")
    u2 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="2", dataset_identity="d2", observed_at=as_of_date, as_of=as_of_date, result_direction="NEGATIVE")
    
    res = MetaAnalysisEngine.synthesize("h1", [u1, u2], as_of_date)
    assert res.evidence_state == MetaResearchStatus.CONFLICTED
    assert "METHODOLOGY_CONFLICT_GAP" in res.unresolved_questions

def test_multiple_testing_warning():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    units = []
    # Create 15 replays on the exact same dataset
    for i in range(15):
        units.append(MetaEvidenceUnit(
            research_identity_hash="h1", source_type="T", source_id=str(i), 
            dataset_identity="d1", seed=i, observed_at=as_of_date, as_of=as_of_date, 
            result_direction="POSITIVE"
        ))
        
    res = MetaAnalysisEngine.synthesize("h1", units, as_of_date)
    assert res.independent_evidence_count == 1
    assert res.multiple_testing_state != MultipleTestingState.NO_RISK_DETECTED
    assert res.evidence_state == MetaResearchStatus.PROMISING_BUT_FRAGILE

def test_stale_evidence():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    u1 = MetaEvidenceUnit(research_identity_hash="h1", source_type="T", source_id="1", dataset_identity="d1", observed_at=as_of_date, as_of=as_of_date, result_direction="POSITIVE", revalidation_state="STALE")
    
    res = MetaAnalysisEngine.synthesize("h1", [u1], as_of_date)
    assert res.evidence_state == MetaResearchStatus.REQUIRES_REVALIDATION
    assert "EVIDENCE_DECAY_GAP" in res.unresolved_questions

def test_causal_limitation_preserved():
    as_of_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # Give it 5 independent positive results
    units = []
    for i in range(5):
        units.append(MetaEvidenceUnit(
            research_identity_hash="h1", source_type="T", source_id=str(i), 
            dataset_identity=f"d{i}", observed_at=as_of_date, as_of=as_of_date, 
            result_direction="POSITIVE"
        ))
        
    res = MetaAnalysisEngine.synthesize("h1", units, as_of_date, causal_limitation="CAUSAL_IDENTIFICATION_LIMITED")
    assert res.evidence_state == MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE
    assert "Meta-analysis cannot upgrade correlational findings to causality." in res.limitations
