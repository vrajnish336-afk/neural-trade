import pytest
from datetime import datetime, timezone, timedelta
from app.research.temporal_generalization.models import (
    WalkForwardType, WalkForwardWindowStatus, TemporalGeneralizationState
)
from app.research.temporal_generalization.service import TemporalGeneralizationService
from app.research.forward_validation_service import ForwardValidationService

@pytest.fixture
def temp_service():
    s = TemporalGeneralizationService()
    s.repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_temporal_windows")
        conn.execute("DELETE FROM research_temporal_assessments")
    return s

def test_walk_forward_window_builder(temp_service):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2021, 1, 1, tzinfo=timezone.utc)
    
    # 360 day train, 90 val, 90 fwd, 90 step -> should build multiple rolling windows
    # Since total period is only 365 days, it shouldn't fit multiple windows. Let's make it bigger.
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    
    run_id = temp_service.create_run(
        candidate_id="cand_1", dataset_identity="test_ds",
        full_start=start, full_end=end,
        train_days=365, val_days=90, forward_days=180, step_days=180,
        wf_type=WalkForwardType.ROLLING, strategy_identity="strat1", parameter_identity="param1",
        as_of=datetime.now(timezone.utc), lineage="manual"
    )
    
    windows = temp_service.repo.get_windows_for_run(run_id)
    assert len(windows) > 1
    
    # Check bounds
    w1 = windows[0]
    w2 = windows[1]
    
    assert (w1.train_end - w1.train_start).days == 365
    assert (w1.validation_end - w1.validation_start).days == 90
    assert (w1.forward_end - w1.forward_start).days == 180
    assert w1.forward_start == w1.validation_end
    
    # Check rolling properties
    assert w2.train_start == w1.train_start + timedelta(days=180)
    
def test_walk_forward_future_as_of_lock(temp_service):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    # The as_of constraint restricts anything past 2021.
    as_of = datetime(2021, 6, 1, tzinfo=timezone.utc)
    
    run_id = temp_service.create_run(
        candidate_id="cand_1", dataset_identity="test_ds",
        full_start=start, full_end=end,
        train_days=365, val_days=90, forward_days=180, step_days=180,
        wf_type=WalkForwardType.ROLLING, strategy_identity="strat1", parameter_identity="param1",
        as_of=as_of, lineage="manual"
    )
    
    windows = temp_service.repo.get_windows_for_run(run_id)
    # The first window fwd_end is 2020 + 365 + 90 + 180 = ~mid 2021
    # Depending on exact days, it might just fit or get blocked.
    # We guarantee the last window's fwd_end <= as_of
    for w in windows:
        assert w.forward_end <= as_of
        
def test_temporal_evaluator(temp_service):
    start = datetime(2020, 1, 1, tzinfo=timezone.utc)
    end = datetime(2024, 1, 1, tzinfo=timezone.utc)
    run_id = temp_service.create_run(
        candidate_id="cand_2", dataset_identity="test_ds",
        full_start=start, full_end=end,
        train_days=365, val_days=90, forward_days=90, step_days=90,
        wf_type=WalkForwardType.EXPANDING, strategy_identity="strat1", parameter_identity="param1",
        as_of=datetime.now(timezone.utc), lineage="manual"
    )
    
    windows = temp_service.repo.get_windows_for_run(run_id)
    assert len(windows) >= 3
    
    for w in windows:
        temp_service.execute_window(w.window_id)
        
    assessment = temp_service.assess_run(run_id, "cand_2", WalkForwardType.EXPANDING, datetime.now(timezone.utc))
    assert assessment.total_windows == len(windows)
    # Based on the mocked service, returns are 0.05 consistently -> std dev is 0.0 -> no inconsistency
    assert assessment.performance_dispersion == 0.0
    assert assessment.overall_state == TemporalGeneralizationState.STRONG_TEMPORAL_GENERALIZATION
