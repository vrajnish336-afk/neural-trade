import pytest
import os
import sqlite3
from datetime import datetime, timezone, timedelta

from app.execution.paper_repository import PaperRepository
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_models import LessonState, ProposalStatus
from app.learning.paper_evolution_engine import PostMortemAnalyzer, LessonExtractor, EvolutionProposalEngine
from app.config import config

@pytest.fixture
def paper_db():
    db_path = "test_phase60_paper.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Must use config's path to fake it for the code under test if it reads config
    # but we pass the injected repo! So it's fine.
    
    conn = sqlite3.connect(db_path)
    with conn:
        conn.execute("""
        CREATE TABLE paper_portfolios (
            portfolio_id TEXT PRIMARY KEY,
            initial_equity REAL,
            current_equity REAL,
            current_cash REAL,
            created_at TEXT,
            updated_at TEXT
        )""")
        conn.execute("""
        CREATE TABLE paper_closed_positions (
            position_id TEXT PRIMARY KEY,
            portfolio_id TEXT NOT NULL,
            symbol TEXT NOT NULL,
            direction TEXT NOT NULL,
            entry_time TEXT NOT NULL,
            entry_price REAL NOT NULL,
            exit_time TEXT NOT NULL,
            exit_price REAL NOT NULL,
            quantity REAL NOT NULL,
            realized_pnl REAL NOT NULL,
            exit_reason TEXT,
            created_at TEXT NOT NULL
        )""")
    conn.close()
    
    repo = PaperRepository(db_path)
    yield repo
    
    if os.path.exists(db_path):
        os.remove(db_path)

@pytest.fixture
def evo_db():
    db_path = "test_phase60_evo.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    # Enable persistence forcefully for tests
    old_persist = config.ENABLE_PERSISTENCE
    config.ENABLE_PERSISTENCE = True
    
    repo = PaperEvolutionRepository(db_path)
    yield repo
    
    config.ENABLE_PERSISTENCE = old_persist
    if os.path.exists(db_path):
        os.remove(db_path)

def test_post_mortem_analysis(paper_db):
    conn = paper_db._get_conn()
    with conn:
        conn.execute("INSERT INTO paper_portfolios VALUES ('default_paper', 10000, 10000, 10000, 'now', 'now')")
        conn.execute("INSERT INTO paper_closed_positions VALUES ('pos1', 'default_paper', 'BTC/USD', 'LONG', '2023-01-01T10:00:00+00:00', 100, '2023-01-01T11:00:00+00:00', 110, 1, 10, 'TAKE_PROFIT', 'now')")
    conn.close()
    
    analyzer = PostMortemAnalyzer(paper_db)
    obs = analyzer.analyze_portfolio("default_paper")
    
    assert len(obs) == 1
    assert obs[0].is_win is True
    assert obs[0].realized_pnl == 10
    assert obs[0].holding_duration_seconds == 3600
    assert obs[0].strategy == "UNKNOWN"

def test_lesson_extraction_insufficient_sample(evo_db):
    extractor = LessonExtractor(evo_db)
    from app.learning.paper_evolution_models import PostMortemObservation
    
    obs = [
        PostMortemObservation(position_id="pos1", symbol="BTC/USD", direction="LONG", entry_time=datetime.now(timezone.utc), exit_time=datetime.now(timezone.utc), holding_duration_seconds=3600, realized_pnl=10, is_win=True, exit_reason="TP", strategy="UNKNOWN", regime="UNKNOWN")
    ]
    
    lessons = extractor.extract_lessons(obs)
    assert len(lessons) == 1
    assert lessons[0].confidence_status == LessonState.INSUFFICIENT_EVIDENCE

def test_lesson_extraction_validated(evo_db):
    extractor = LessonExtractor(evo_db)
    from app.learning.paper_evolution_models import PostMortemObservation
    
    obs = []
    for i in range(5):
        obs.append(PostMortemObservation(position_id=f"pos{i}", symbol="BTC/USD", direction="LONG", entry_time=datetime.now(timezone.utc), exit_time=datetime.now(timezone.utc), holding_duration_seconds=3600, realized_pnl=-10, is_win=False, exit_reason="SL", strategy="UNKNOWN", regime="UNKNOWN"))
        
    lessons = extractor.extract_lessons(obs)
    assert len(lessons) == 1
    assert lessons[0].confidence_status == LessonState.VALIDATED
    assert lessons[0].wins == 0
    assert lessons[0].losses == 5
    assert lessons[0].observed_pnl == -50

def test_evolution_proposal_generation(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    from app.learning.paper_evolution_models import PaperResearchLesson
    
    lesson = PaperResearchLesson(
        lesson_id="lesson1",
        source_trade_ids=[],
        strategy="UNKNOWN",
        regime="UNKNOWN",
        observation="Test",
        sample_count=5,
        wins=0,
        losses=5,
        observed_pnl=-50,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime.now(timezone.utc),
        data_window_start=datetime.now(timezone.utc),
        data_window_end=datetime.now(timezone.utc)
    )
    
    proposals = engine.generate_proposals([lesson])
    assert len(proposals) == 1
    p = proposals[0]
    assert p.affected_parameter == "MIN_SIGNAL_SCORE"
    assert p.status == ProposalStatus.REVIEW_REQUIRED

def test_human_approval_required(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    from app.learning.paper_evolution_models import EvolutionProposal
    
    p = EvolutionProposal(
        proposal_id="prop1",
        lesson_ids=[],
        evidence_ids=[],
        affected_strategy="UNKNOWN",
        affected_parameter="MIN_SIGNAL_SCORE",
        current_value=50.0,
        proposed_value=60.0,
        delta=10.0,
        reason="Test",
        evidence_summary="Test",
        sample_size=5,
        validation_status="PASSED",
        expected_research_rationale="Test",
        created_at=datetime.now(timezone.utc),
        status=ProposalStatus.REVIEW_REQUIRED
    )
    evo_db.save_proposal(p)
    
    # Try to apply without approval
    res = engine.apply_proposal("prop1")
    assert res is False
    
    # Approve and apply
    p.status = ProposalStatus.APPROVED
    evo_db.save_proposal(p)
    
    # Modify config to match expected current value
    old_val = getattr(config, "MIN_SIGNAL_SCORE", None)
    config.MIN_SIGNAL_SCORE = 50.0
    
    res = engine.apply_proposal("prop1")
    assert res is True
    assert config.MIN_SIGNAL_SCORE == 60.0
    
    # Rollback
    res = engine.rollback_proposal("prop1")
    assert res is True
    assert config.MIN_SIGNAL_SCORE == 50.0
    
    # Restore original config
    if old_val: config.MIN_SIGNAL_SCORE = old_val

def test_runaway_loop_protection(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    from app.learning.paper_evolution_models import PaperResearchLesson
    
    lesson = PaperResearchLesson(
        lesson_id="lesson1",
        source_trade_ids=[],
        strategy="UNKNOWN",
        regime="UNKNOWN",
        observation="Test",
        sample_count=5,
        wins=0,
        losses=5,
        observed_pnl=-50,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime.now(timezone.utc),
        data_window_start=datetime.now(timezone.utc),
        data_window_end=datetime.now(timezone.utc)
    )
    
    proposals_1 = engine.generate_proposals([lesson])
    assert len(proposals_1) == 1
    
    # Same parameter, should not generate another proposal while REVIEW_REQUIRED
    proposals_2 = engine.generate_proposals([lesson])
    assert len(proposals_2) == 0

def test_stale_proposal_rejected(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    from app.learning.paper_evolution_models import EvolutionProposal
    
    p = EvolutionProposal(
        proposal_id="prop1",
        lesson_ids=[],
        evidence_ids=[],
        affected_strategy="UNKNOWN",
        affected_parameter="MIN_SIGNAL_SCORE",
        current_value=50.0,
        proposed_value=60.0,
        delta=10.0,
        reason="Test",
        evidence_summary="Test",
        sample_size=5,
        validation_status="PASSED",
        expected_research_rationale="Test",
        created_at=datetime.now(timezone.utc),
        status=ProposalStatus.APPROVED
    )
    evo_db.save_proposal(p)
    
    old_val = getattr(config, "MIN_SIGNAL_SCORE", 50.0)
    # Drift the config
    config.MIN_SIGNAL_SCORE = 99.0
    
    res = engine.apply_proposal("prop1")
    assert res is False
    
    saved_p = evo_db.get_proposals()[0]
    assert saved_p.status == ProposalStatus.EXPIRED
    
    # Restore original config
    config.MIN_SIGNAL_SCORE = old_val

def test_forbidden_parameter_modification(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    from app.learning.paper_evolution_models import EvolutionProposal
    
    p = EvolutionProposal(
        proposal_id="prop1",
        lesson_ids=[],
        evidence_ids=[],
        affected_strategy="UNKNOWN",
        affected_parameter="PAPER_TRADING", # FORBIDDEN
        current_value=True,
        proposed_value=False,
        delta=False,
        reason="Test",
        evidence_summary="Test",
        sample_size=5,
        validation_status="PASSED",
        expected_research_rationale="Test",
        created_at=datetime.now(timezone.utc),
        status=ProposalStatus.APPROVED
    )
    evo_db.save_proposal(p)
    
    res = engine.apply_proposal("prop1")
    assert res is False
