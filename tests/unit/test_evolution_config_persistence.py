import pytest
import tempfile
import os
from datetime import datetime, timezone, timedelta
from app.config import config
from app.learning.paper_evolution_models import EvolutionProposal, ProposalStatus
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_engine import EvolutionProposalEngine


@pytest.fixture
def temp_repo():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)
    old_db = config.DB_PATH
    old_persist = config.ENABLE_PERSISTENCE
    config.DB_PATH = path
    config.ENABLE_PERSISTENCE = True
    repo = PaperEvolutionRepository(db_path=path)
    yield repo
    config.DB_PATH = old_db
    config.ENABLE_PERSISTENCE = old_persist
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


def _make_proposal(proposal_id, param, current_v, proposed_v, status, created_at=None):
    return EvolutionProposal(
        proposal_id=proposal_id,
        lesson_ids=["l1"],
        evidence_ids=["e1"],
        affected_strategy="BreakoutStrategy" if "_MIN_SCORE" in param else "GLOBAL",
        affected_parameter=param,
        current_value=current_v,
        proposed_value=proposed_v,
        delta=proposed_v - current_v if isinstance(proposed_v, (int, float)) and isinstance(current_v, (int, float)) else 0.0,
        reason="Test proposal",
        evidence_summary="Test evidence",
        sample_size=10,
        validation_status="VALIDATED",
        expected_research_rationale="Test rationale",
        created_at=created_at or datetime.now(timezone.utc),
        status=status
    )


def test_applied_proposal_rehydrates_after_restart(temp_repo):
    # 1. Save an APPLIED proposal to DB
    prop = _make_proposal("p1", "BreakoutStrategy_MIN_SCORE", 50.0, 65.0, ProposalStatus.APPLIED)
    temp_repo.save_proposal(prop)
    
    # 2. Reset in-memory config attribute to default
    if hasattr(config, "BreakoutStrategy_MIN_SCORE"):
        delattr(config, "BreakoutStrategy_MIN_SCORE")
        
    # 3. Simulate process restart by instantiating new engine
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert getattr(config, "BreakoutStrategy_MIN_SCORE") == 65.0


def test_multiple_proposals_same_parameter_order_resolution(temp_repo):
    t0 = datetime.now(timezone.utc) - timedelta(hours=2)
    t1 = datetime.now(timezone.utc) - timedelta(hours=1)
    
    p1 = _make_proposal("p1", "NEWS_LOOKBACK_HOURS", 24.0, 48.0, ProposalStatus.APPLIED, created_at=t0)
    p2 = _make_proposal("p2", "NEWS_LOOKBACK_HOURS", 48.0, 72.0, ProposalStatus.APPLIED, created_at=t1)
    
    temp_repo.save_proposal(p1)
    temp_repo.save_proposal(p2)
    
    if hasattr(config, "NEWS_LOOKBACK_HOURS"):
        delattr(config, "NEWS_LOOKBACK_HOURS")
        
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    # Latest applied proposal (p2 = 72.0) must supersede earlier one (p1 = 48.0)
    assert getattr(config, "NEWS_LOOKBACK_HOURS") == 72.0


def test_unapproved_proposal_not_rehydrated(temp_repo):
    p_unapproved = _make_proposal("p_unapp", "MIN_SIGNAL_SCORE", 50.0, 75.0, ProposalStatus.REVIEW_REQUIRED)
    temp_repo.save_proposal(p_unapproved)
    
    config.MIN_SIGNAL_SCORE = 50.0
    
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert config.MIN_SIGNAL_SCORE == 50.0


def test_rolled_back_state_not_rehydrated(temp_repo):
    p_rolled = _make_proposal("p_roll", "ANOMALY_ZSCORE_THRESHOLD", 3.0, 4.5, ProposalStatus.ROLLED_BACK)
    temp_repo.save_proposal(p_rolled)
    
    config.ANOMALY_ZSCORE_THRESHOLD = 3.0
    
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert config.ANOMALY_ZSCORE_THRESHOLD == 3.0


def test_invalid_persisted_value_fails_safely(temp_repo):
    # Non-numeric proposed value
    p_invalid = _make_proposal("p_bad", "MIN_ARTICLE_RELEVANCE", 0.5, "INVALID_STRING", ProposalStatus.APPLIED)
    temp_repo.save_proposal(p_invalid)
    
    config.MIN_ARTICLE_RELEVANCE = 0.5
    
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert config.MIN_ARTICLE_RELEVANCE == 0.5


def test_empty_proposal_history_preserves_defaults(temp_repo):
    orig_score = getattr(config, "MIN_SIGNAL_SCORE", 50.0)
    
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert getattr(config, "MIN_SIGNAL_SCORE", 50.0) == orig_score


def test_risk_safety_parameters_cannot_be_rehydrated(temp_repo):
    # Attempting to rehydrate a restricted risk parameter
    p_unsafe = _make_proposal("p_unsafe", "MAX_DRAWDOWN_PCT", 0.20, 0.50, ProposalStatus.APPLIED)
    temp_repo.save_proposal(p_unsafe)
    
    if hasattr(config, "MAX_DRAWDOWN_PCT"):
        delattr(config, "MAX_DRAWDOWN_PCT")
        
    engine = EvolutionProposalEngine(evo_repo=temp_repo, auto_rehydrate=True)
    
    assert not hasattr(config, "MAX_DRAWDOWN_PCT")
