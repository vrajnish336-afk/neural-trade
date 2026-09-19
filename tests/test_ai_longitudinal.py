import pytest
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone

from app.config import config
from app.database.schema import init_db
from app.research.longitudinal_models import LongitudinalEventType
from app.research.longitudinal_service import LongitudinalCandidateTracker
from app.research.portfolio_service import ResearchPortfolioService
from app.research.track_record_models import StrategyHealthState

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_longitudinal.sqlite"
    config.DB_PATH = str(db_file)
    config.ENABLE_PERSISTENCE = True
    init_db()
    yield

def _seed_time_series(identity_hash: str):
    base_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    
    with sqlite3.connect(config.DB_PATH) as conn:
        # T0: Discovery
        conn.execute("""
            INSERT INTO research_memory (identity_hash, canonical_hypothesis, affected_symbols, mapped_strategy, first_seen_at, last_researched_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (identity_hash, "Hypo", '["BTC"]', "Trend", base_time.isoformat(), base_time.isoformat()))
        
        # T1: Conclusion (Insufficient)
        t1 = base_time + timedelta(days=1)
        conn.execute("""
            INSERT INTO research_conclusions (conclusion_id, identity_hash, decision_state, confidence_state, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), identity_hash, "INSUFFICIENT_EVIDENCE", "LOW", "No fwd obs", t1.isoformat()))
        
        # T2: Track Record init and 1 observation
        t2 = base_time + timedelta(days=2)
        tr_id = identity_hash + "_tr"
        conn.execute("""
            INSERT INTO paper_track_records (track_record_id, identity_hash, current_health_state, initial_equity, current_equity, cumulative_return_pct, cumulative_pnl, max_drawdown_pct, observation_count, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tr_id, identity_hash, "HEALTHY", 10000.0, 10100.0, 1.0, 100.0, 1.0, 1, t2.isoformat(), t2.isoformat()))
        
        conn.execute("""
            INSERT INTO paper_observations (observation_id, track_record_id, observation_end, net_pnl, drawdown_pct, drift_state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), tr_id, t2.isoformat(), 100.0, 1.0, "STABLE", t2.isoformat()))
        
        # T3: Health Change to WATCH
        t3 = base_time + timedelta(days=3)
        conn.execute("""
            INSERT INTO paper_health_history (history_id, track_record_id, previous_state, new_state, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), tr_id, "HEALTHY", "WATCH", t3.isoformat()))
        
        # T4: Future Observation (Drifted)
        t4 = base_time + timedelta(days=10)
        conn.execute("""
            INSERT INTO paper_observations (observation_id, track_record_id, observation_end, net_pnl, drawdown_pct, drift_state, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), tr_id, t4.isoformat(), -500.0, -5.0, "SIGNIFICANTLY_DEGRADED", t4.isoformat()))
        conn.execute("UPDATE paper_track_records SET observation_count = 2 WHERE track_record_id = ?", (tr_id,))
        
        # T5: Conclusion (Contradictory) & Conflict
        t5 = base_time + timedelta(days=11)
        conn.execute("""
            INSERT INTO research_conclusions (conclusion_id, identity_hash, decision_state, confidence_state, summary, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), identity_hash, "CONTRADICTORY_EVIDENCE", "MODERATE", "Drifted", t5.isoformat()))
        
        conn.execute("""
            INSERT INTO research_conflicts (conflict_id, identity_hash, experiment_id_1, experiment_id_2, conflict_type, severity, explanation, resolution_status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), identity_hash, "e1", "e2", "OOS_CONTRADICTION", "HIGH", "Drift conflict", "UNRESOLVED", t5.isoformat()))

    return base_time

def test_longitudinal_tracking_chronology():
    base_time = _seed_time_series("cand_time")
    tracker = LongitudinalCandidateTracker()
    
    # We want full history up to T5
    timeline = tracker.get_history("cand_time")
    
    assert timeline is not None
    assert timeline.identity_hash == "cand_time"
    
    # Check that events are chronologically sorted
    for i in range(1, len(timeline.events)):
        assert timeline.events[i].timestamp >= timeline.events[i-1].timestamp
        
    # Check counts
    assert timeline.total_forward_observations == 2
    assert timeline.health_transitions_count > 0

def test_future_data_barrier():
    """Future evidence MUST NOT corrupt past snapshots (As-Of)."""
    base_time = _seed_time_series("cand_asof")
    tracker = LongitudinalCandidateTracker()
    
    # Request state as of T2 (before Health changed to WATCH, and before observation 2)
    t2_barrier = base_time + timedelta(days=2, hours=1)
    
    timeline = tracker.get_history("cand_asof", as_of=t2_barrier)
    snap = timeline.latest_snapshot
    
    assert snap is not None
    # At T2, observation count should be 1
    assert snap.forward_observation_count == 1
    # At T2, health should be HEALTHY
    assert snap.current_health == StrategyHealthState.HEALTHY
    # At T2, conclusion should be INSUFFICIENT
    assert snap.decision_state.value == "INSUFFICIENT_EVIDENCE"
    
    # None of the events after T2 should be in the timeline
    for evt in timeline.events:
        assert evt.timestamp <= t2_barrier

def test_transition_explanations():
    base_time = _seed_time_series("cand_explain")
    tracker = LongitudinalCandidateTracker()
    timeline = tracker.get_history("cand_explain")
    
    # Look for the health change event at T3
    health_evt = None
    for evt in timeline.events:
        if evt.event_type == LongitudinalEventType.HEALTH_CHANGED:
            health_evt = evt
            break
            
    assert health_evt is not None
    # Check transitions inside the event
    assert len(health_evt.transitions) > 0
    
    health_trans = next((t for t in health_evt.transitions if t.field_name == "health"), None)
    assert health_trans is not None
    assert health_trans.previous_state == "HEALTHY"
    assert health_trans.new_state == "WATCH"
    assert health_trans.reason == "Health state transition detected."
    
def test_no_pnl_classification():
    """Verify that priorities are derived, not raw PnL winners."""
    base_time = _seed_time_series("cand_pnl")
    tracker = LongitudinalCandidateTracker()
    timeline = tracker.get_history("cand_pnl")
    
    # Check the final snapshot
    snap = timeline.latest_snapshot
    # At T5, it has a CONTRADICTORY conclusion, and significant drift.
    # Therefore priority should reflect research urgency (VERY_HIGH or HIGH)
    assert snap.priority.value in ["HIGH", "VERY_HIGH"]
    assert len(snap.priority_reasons) > 0
