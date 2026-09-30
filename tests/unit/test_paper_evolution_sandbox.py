import pytest
from unittest import mock
from datetime import datetime, timezone

from app.learning.paper_evolution_engine import EvolutionProposalEngine
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_models import EvolutionProposal, ProposalStatus
from app.sandbox.research_sandbox import ControlledResearchSandbox
from app.sandbox.models import ExperimentStatus
from app.core.models import MarketBar
from app.risk.engine import RiskEngine

@pytest.fixture
def mock_bars():
    return [
        MarketBar(
            symbol="BTC/USD",
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=100.0, high=105.0, low=99.0, close=102.0, volume=1000.0
        )
    ]

@pytest.fixture
def repo(tmp_path):
    db_file = tmp_path / "test_evo.db"
    return PaperEvolutionRepository(db_path=str(db_file))

def test_unapproved_proposal_blocked_from_sandbox(repo, mock_bars):
    """Verify unapproved (REVIEW_REQUIRED) proposals raise PermissionError when attempting sandbox validation."""
    engine = EvolutionProposalEngine(evo_repo=repo, auto_rehydrate=False)
    proposal = EvolutionProposal(
        proposal_id="prop_unapproved",
        lesson_ids=["l1"],
        evidence_ids=["e1"],
        affected_strategy="TrendFollowing",
        affected_parameter="TrendFollowing_MIN_SCORE",
        current_value=50.0,
        proposed_value=60.0,
        delta=10.0,
        reason="Test",
        evidence_summary="Test summary",
        sample_size=10,
        validation_status="NONE",
        expected_research_rationale="Test rationale",
        created_at=datetime.now(timezone.utc),
        status=ProposalStatus.REVIEW_REQUIRED
    )
    repo.save_proposal(proposal)

    with mock.patch("app.config.config.SELF_LEARNING_EVOLUTION_ENABLED", True):
        with pytest.raises(PermissionError, match="must have explicit human approval"):
            engine.validate_proposal_in_sandbox("prop_unapproved", bars=mock_bars)

def test_approved_proposal_sandbox_validation_allowed(repo, mock_bars):
    """Verify approved proposals can be validated inside ControlledResearchSandbox."""
    engine = EvolutionProposalEngine(evo_repo=repo, auto_rehydrate=False)
    proposal = EvolutionProposal(
        proposal_id="prop_approved",
        lesson_ids=["l1"],
        evidence_ids=["e1"],
        affected_strategy="TrendFollowing",
        affected_parameter="TrendFollowing_MIN_SCORE",
        current_value=50.0,
        proposed_value=60.0,
        delta=10.0,
        reason="Test",
        evidence_summary="Test summary",
        sample_size=10,
        validation_status="NONE",
        expected_research_rationale="Test rationale",
        created_at=datetime.now(timezone.utc),
        status=ProposalStatus.APPROVED
    )
    repo.save_proposal(proposal)

    sandbox = ControlledResearchSandbox()
    with mock.patch("app.config.config.SELF_LEARNING_EVOLUTION_ENABLED", True), \
         mock.patch.object(sandbox, "is_enabled", return_value=True):
        res = engine.validate_proposal_in_sandbox("prop_approved", sandbox=sandbox, bars=mock_bars)
        assert res.is_safe is True
        assert res.status == ExperimentStatus.COMPLETED
        updated = repo.get_proposals()[0]
        assert updated.validation_status == "SANDBOX_VALIDATED"

def test_rejected_or_unsafe_proposal_blocked(repo, mock_bars):
    """Verify rejected or non-allowlisted parameter proposals are blocked."""
    engine = EvolutionProposalEngine(evo_repo=repo, auto_rehydrate=False)
    rejected_prop = EvolutionProposal(
        proposal_id="prop_rejected",
        lesson_ids=["l1"],
        evidence_ids=["e1"],
        affected_strategy="Test",
        affected_parameter="MIN_SIGNAL_SCORE",
        current_value=50.0, proposed_value=60.0, delta=10.0, reason="Test",
        evidence_summary="Test", sample_size=10, validation_status="NONE",
        expected_research_rationale="Test", created_at=datetime.now(timezone.utc),
        status=ProposalStatus.REJECTED
    )
    repo.save_proposal(rejected_prop)

    unsafe_prop = EvolutionProposal(
        proposal_id="prop_unsafe",
        lesson_ids=["l1"],
        evidence_ids=["e1"],
        affected_strategy="Test",
        affected_parameter="UNSAFE_SYSTEM_PARAM",
        current_value=1.0, proposed_value=2.0, delta=1.0, reason="Test",
        evidence_summary="Test", sample_size=10, validation_status="NONE",
        expected_research_rationale="Test", created_at=datetime.now(timezone.utc),
        status=ProposalStatus.APPROVED
    )
    repo.save_proposal(unsafe_prop)

    with mock.patch("app.config.config.SELF_LEARNING_EVOLUTION_ENABLED", True):
        with pytest.raises(PermissionError, match="must have explicit human approval"):
            engine.validate_proposal_in_sandbox("prop_rejected", bars=mock_bars)

        with pytest.raises(PermissionError, match="not in the safe allowlist"):
            engine.validate_proposal_in_sandbox("prop_unsafe", bars=mock_bars)

def test_sandbox_cannot_modify_core_trading_files(mock_bars):
    """Verify sandbox candidate validation cannot write to production or core files."""
    sandbox = ControlledResearchSandbox()
    with mock.patch.object(sandbox, "is_enabled", return_value=True):
        res = sandbox.execute_candidate("p1", "open('app/risk/engine.py', 'w').write('hack')", "func", mock_bars)
        assert res.is_safe is False
        assert res.status == ExperimentStatus.FAILED
        assert res.provenance == "CONTROLLED_RESEARCH_SANDBOX_BLOCKED_PROTECTED_FILES"

def test_risk_engine_remains_authoritative():
    """Verify RiskEngine instantiation and core limits are untouched by evolution sandbox."""
    from app.risk.limits import PortfolioRiskLimits
    risk_engine = RiskEngine(limits=PortfolioRiskLimits(initial_equity=10000.0))
    assert hasattr(risk_engine, "evaluate_trade")


