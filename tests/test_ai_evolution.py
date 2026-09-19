import pytest
from app.learning.evolution_engine import ControlledEvolutionEngine, ResearchGapDetector
from app.learning.evolution_models import EvolutionProposalState, ResearchAnswer
from app.sandbox.models import ResearchSandboxExperiment, ExperimentStatus

@pytest.fixture
def engine():
    e = ControlledEvolutionEngine()
    e.repo._init_db()
    e.sandbox_repo._init_db()
    return e

def test_gap_detection(engine):
    # Setup mock

    
    # Add a weak sample size experiment
    exp = ResearchSandboxExperiment(
        experiment_id="weak_exp",
        proposal_id="p1",
        code_hash="c1",
        dataset_identity="ds1",
        parameters={"x":1},
        backtest_result_json='{"number_of_trades": 15}'
    )
    engine.sandbox_repo.save_experiment(exp)
    
    gaps = engine.gap_detector.detect_gaps()
    weak_gap = next((g for g in gaps if g["experiment_id"] == "weak_exp"), None)
    assert weak_gap is not None
    assert weak_gap["gap_type"] == "SAMPLE_SIZE_WEAK"

def test_evolution_bounds_rejection(engine):
    baseline = {"lookback": 20, "multiplier": 2.0}
    
    # Invalid key
    assert engine._validate_bounds(baseline, {"lookback": 20, "new_key": 1}) == False
    # Invalid type
    assert engine._validate_bounds(baseline, {"lookback": "20", "multiplier": 2.0}) == False
    # Negative bound check
    assert engine._validate_bounds(baseline, {"lookback": -5, "multiplier": 2.0}) == False
    # Valid
    assert engine._validate_bounds(baseline, {"lookback": 18, "multiplier": 2.5}) == True

def test_evolution_pipeline(engine):
    import uuid
    base_id = str(uuid.uuid4())
    # Setup baseline
    base = ResearchSandboxExperiment(
        experiment_id=base_id,
        proposal_id="pbase",
        code_hash="cbase",
        dataset_identity="ds1",
        parameters={"lookback": 20}
    )
    engine.sandbox_repo.save_experiment(base)
    
    # Generate proposal
    prop = engine.generate_proposal(
        baseline_exp_id=base_id,
        proposed_params={"lookback": 18},
        question="Does shorter lookback improve robustness?",
        rationale="Tested gap"
    )
    assert prop is not None
    assert prop.state == EvolutionProposalState.REVIEW_REQUIRED
    
    # Cannot execute without approval
    assert engine.execute_proposal(prop.proposal_id) == False
    
    # Approve
    assert engine.approve_proposal(prop.proposal_id) == True
    assert engine.repo.get_proposal(prop.proposal_id).state == EvolutionProposalState.APPROVED_FOR_RESEARCH
    
    # In a real test, execute_proposal would need a matching sandbox proposal to extract code
    # We will skip execution test because it requires mocked Sandbox Code injection,
    # but we can test duplication prevention.
    
    prop2 = engine.generate_proposal(
        baseline_exp_id=base_id,
        proposed_params={"lookback": 18},
        question="Does shorter lookback improve robustness?",
        rationale="Tested gap"
    )
    assert prop2 is None # Duplicate rejected
