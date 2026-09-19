import pytest
import sqlite3
import json
from datetime import datetime, timezone
import uuid

from app.config import config
from app.database.schema import init_db
from app.research.portfolio_models import (
    ResearchCandidateSnapshot, ResearchPriority, ResearchEvidenceScore, CandidateComparisonMatrix
)
from app.research.portfolio_service import ResearchPortfolioService
from app.research.track_record_models import StrategyHealthState
from app.research.decision_models import ResearchDecisionState
from app.research.comparator import ComparabilityStatus

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_portfolio.sqlite"
    config.DB_PATH = str(db_file)
    config.ENABLE_PERSISTENCE = True
    init_db()
    yield

def _seed_candidate(identity_hash: str, strategy: str, decision: str, health: str, obs_count: int, conflicts: int, missing_lineage: bool = False):
    with sqlite3.connect(config.DB_PATH) as conn:
        # Seed Memory
        if not missing_lineage:
            conn.execute("""
                INSERT INTO research_memory (identity_hash, canonical_hypothesis, affected_symbols, mapped_strategy, first_seen_at, last_researched_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (identity_hash, f"Hypo for {identity_hash}", '["BTC"]', strategy, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()))
        
        # Seed Decision
        conn.execute("""
            INSERT INTO research_conclusions (conclusion_id, identity_hash, decision_state, confidence_state, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), identity_hash, decision, "MODERATE", "Summary", datetime.utcnow().isoformat()))
        
        # Seed Track Record
        conn.execute("""
            INSERT INTO paper_track_records (track_record_id, identity_hash, current_health_state, initial_equity, current_equity, cumulative_return_pct, cumulative_pnl, max_drawdown_pct, observation_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (identity_hash + "_tr", identity_hash, health, 10000.0, 10500.0, 5.0, 500.0, 2.0, obs_count, datetime.utcnow().isoformat()))
        
        # Seed Conflicts
        for i in range(conflicts):
            conn.execute("""
                INSERT INTO research_conflicts (conflict_id, identity_hash, conflict_type, severity, explanation, resolution_status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), identity_hash, "EVIDENCE_CONTRADICTION", "HIGH", "Conflict", "UNRESOLVED"))

def test_build_snapshot():
    _seed_candidate("cand1", "Trend", "RESEARCH_RESULT_SUPPORTED", "HEALTHY", 10, 0)
    service = ResearchPortfolioService()
    snap = service.build_snapshot("cand1")
    
    assert snap is not None
    assert snap.identity_hash == "cand1"
    assert snap.strategy == "Trend"
    assert snap.forward_observation_count == 10
    assert snap.current_health == StrategyHealthState.HEALTHY
    assert snap.decision_state == ResearchDecisionState.RESEARCH_RESULT_SUPPORTED
    assert snap.unresolved_conflicts == 0
    assert snap.missing_lineage is False
    
    # Priority check: Strong historical, strong forward, healthy, no conflicts -> MEDIUM (solid base, keep monitoring)
    assert snap.priority == ResearchPriority.MEDIUM
    assert snap.evidence_score.total_score == 9  # hist(3) + fwd(3) + health(3) - 0

def test_missing_lineage_priority():
    _seed_candidate("cand2", "MeanRev", "RESEARCH_RESULT_SUPPORTED", "HEALTHY", 10, 0, missing_lineage=True)
    service = ResearchPortfolioService()
    snap = service.build_snapshot("cand2")
    
    # Missing memory means it returns None
    assert snap is None

def test_degraded_priority():
    _seed_candidate("cand3", "Breakout", "RESEARCH_RESULT_SUPPORTED", "CRITICAL", 5, 0)
    service = ResearchPortfolioService()
    snap = service.build_snapshot("cand3")
    
    # Critical health triggers VERY_HIGH priority (needs investigation)
    assert snap.priority == ResearchPriority.VERY_HIGH
    assert snap.evidence_score.health_score == -3

def test_get_portfolio_sorting():
    _seed_candidate("cand_healthy", "StratA", "RESEARCH_RESULT_SUPPORTED", "HEALTHY", 10, 0) # Score 6, MEDIUM
    _seed_candidate("cand_degraded", "StratB", "SUPPORTED_FOR_FURTHER_RESEARCH", "CRITICAL", 5, 0) # VERY_HIGH
    _seed_candidate("cand_blocked", "StratC", "BLOCKED", "INSUFFICIENT_HISTORY", 0, 0) # BLOCKED
    _seed_candidate("cand_new", "StratD", "SUPPORTED_FOR_FURTHER_RESEARCH", "INSUFFICIENT_HISTORY", 0, 0) # HIGH (needs forward validation)
    
    service = ResearchPortfolioService()
    portfolio = service.get_portfolio()
    
    assert len(portfolio) == 4
    # Expected order: VERY_HIGH, HIGH, MEDIUM, LOW/BLOCKED
    assert portfolio[0].identity_hash == "cand_degraded"
    assert portfolio[1].identity_hash == "cand_new"
    assert portfolio[2].identity_hash == "cand_healthy"
    assert portfolio[3].identity_hash == "cand_blocked"

def test_compare_candidates_comparability():
    _seed_candidate("c1", "Trend", "RESEARCH_RESULT_SUPPORTED", "HEALTHY", 10, 0)
    _seed_candidate("c2", "Trend", "SUPPORTED_FOR_FURTHER_RESEARCH", "HEALTHY", 5, 0)
    _seed_candidate("c3", "MeanRev", "RESEARCH_RESULT_SUPPORTED", "HEALTHY", 10, 0)
    
    service = ResearchPortfolioService()
    
    # Comparable
    res1 = service.compare_candidates(["c1", "c2"])
    assert res1.comparability == ComparabilityStatus.COMPARABLE
    assert len(res1.candidates) == 2
    
    # Limited
    res2 = service.compare_candidates(["c1", "c3"])
    assert res2.comparability == ComparabilityStatus.LIMITED_COMPARABILITY
    assert len(res2.differences) == 1
    assert "Strategy mismatch" in res2.differences[0]
