import pytest
from datetime import datetime, timezone, timedelta
from app.research.causality.models import CausalAssessment, ConfoundingRisk, MechanismCandidate
from app.research.causal_experiments.service import CausalExperimentService
from app.research.causal_experiments.models import ExperimentApprovalStatus

@pytest.fixture
def experiment_service():
    s = CausalExperimentService()
    s.repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_causal_experiment_designs")
        conn.execute("DELETE FROM research_causal_experiment_results")
    return s

def test_experiment_design_generation(experiment_service):
    t_now = datetime.now(timezone.utc)
    
    assessment = CausalAssessment(
        assessment_id="ass_1",
        hypothesis_id="hyp_1",
        research_identity="id_1",
        confounders=[
            ConfoundingRisk(risk_id="cr_1", description="overlap", overlapping_variables=["cost_scenario", "regime"])
        ],
        mechanisms=[MechanismCandidate(mechanism_id="m1", description="mech desc")],
        causal_level="CAUSAL_EVIDENCE_SUPPORTED",
        temporal_ordering_verified=True,
        as_of=t_now,
        created_at=t_now
    )
    
    designs = experiment_service.generate_designs(assessment)
    assert len(designs) == 1
    d = designs[0]
    assert d.hypothesis_id == "hyp_1"
    assert d.focal_variable == "cost_scenario"
    assert "regime" in d.control_variables
    assert d.status == ExperimentApprovalStatus.DRAFT

def test_experiment_approval_workflow(experiment_service):
    t_now = datetime.now(timezone.utc)
    assessment = CausalAssessment(
        assessment_id="ass_2", hypothesis_id="hyp_2", research_identity="id_2",
        confounders=[ConfoundingRisk(risk_id="cr_1", description="overlap", overlapping_variables=["volatility", "regime"])],
        as_of=t_now, created_at=t_now
    )
    designs = experiment_service.generate_designs(assessment)
    d = designs[0]
    
    # Must fail execution if draft
    with pytest.raises(ValueError, match="blocked"):
        experiment_service.run_experiment(d.experiment_id, "hyp_2")
        
    # Approve
    success = experiment_service.approve_experiment(d.experiment_id, "hyp_2")
    assert success == True
    
    # Run
    res = experiment_service.run_experiment(d.experiment_id, "hyp_2")
    assert res is not None
    assert res.hypothesis_id == "hyp_2"
    assert "volatility" in res.treatment_condition
    assert "regime" in res.control_condition
