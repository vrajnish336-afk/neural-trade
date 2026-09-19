import pytest
from app.research.experiment_intelligence.service import ExperimentComparisonService
from app.sandbox.models import ResearchSandboxExperiment, ExperimentStatus
from app.research.experiment_intelligence.models import CompatibilityStatus, EvidenceStrength
from datetime import datetime

@pytest.fixture
def svc():
    s = ExperimentComparisonService()
    s.compare_repo._init_db()
    s.sandbox_repo._init_db()
    return s

def test_compatibility_check(svc):
    exp_a = ResearchSandboxExperiment(
        experiment_id="A",
        proposal_id="1",
        code_hash="h1",
        dataset_identity="DS1",
        parameters={"x": 1}
    )
    exp_b = ResearchSandboxExperiment(
        experiment_id="B",
        proposal_id="2",
        code_hash="h2",
        dataset_identity="DS2",
        parameters={"x": 1}
    )
    status, notes = svc._check_compatibility(exp_a, exp_b)
    assert status == CompatibilityStatus.NOT_COMPARABLE
    
    exp_b.dataset_identity = "DS1"
    status, notes = svc._check_compatibility(exp_a, exp_b)
    assert status == CompatibilityStatus.DIRECTLY_COMPARABLE
    
    exp_b.parameters = {"x": 2}
    status, notes = svc._check_compatibility(exp_a, exp_b)
    assert status == CompatibilityStatus.PARTIALLY_COMPARABLE

def test_compare_experiments(svc):
    exp_a = ResearchSandboxExperiment(
        experiment_id="expA",
        proposal_id="p1",
        code_hash="abc",
        dataset_identity="data1",
        parameters={"a":1},
        backtest_result_json='{"total_return_pct": 0.15, "max_drawdown_pct": 0.05, "number_of_trades": 50}',
        status=ExperimentStatus.COMPLETED
    )
    exp_b = ResearchSandboxExperiment(
        experiment_id="expB",
        proposal_id="p2",
        code_hash="def",
        dataset_identity="data1",
        parameters={"a":2},
        backtest_result_json='{"total_return_pct": 0.05, "max_drawdown_pct": 0.02, "number_of_trades": 5}',
        status=ExperimentStatus.COMPLETED
    )
    
    svc.sandbox_repo.save_experiment(exp_a)
    svc.sandbox_repo.save_experiment(exp_b)
    
    comp = svc.compare_experiments("expA", "expB")
    assert comp is not None
    assert comp.compatibility == CompatibilityStatus.PARTIALLY_COMPARABLE
    
    assert comp.profile_a.overall_strength == EvidenceStrength.STRONG
    assert comp.profile_b.overall_strength == EvidenceStrength.INSUFFICIENT
    
    assert comp.performance_winner == "expA"
    assert comp.coverage_winner == "expA"
    assert comp.final_research_assessment == EvidenceStrength.STRONG

def test_missing_experiment_returns_none(svc):
    comp = svc.compare_experiments("not_exist_1", "not_exist_2")
    assert comp is None
