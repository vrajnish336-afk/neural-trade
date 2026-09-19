import pytest
import sqlite3
import uuid
import json
from datetime import datetime, timezone, timedelta
from app.database.schema import init_db
from app.config import config
from app.research.track_record_models import PaperTrackRecord, PaperObservation, StrategyHealthState
from app.research.track_record_service import PaperTrackRecordService
from app.research.forward_validation_models import ForwardValidationRun, FrozenSpecification, ForwardValidationState, ForwardDriftState
from app.research.health_analyzer import StrategyHealthAnalyzer

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_track_records.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    
    # We must seed research_experiments for the metrics extractor
    dummy_exp = {
        "out_of_sample_report": {
            "trade_metrics": {
                "net_profit": 500.0,
                "total_trades": 10,
                "win_rate_pct": 60.0,
                "profit_factor": 1.5
            },
            "equity_metrics": {
                "max_drawdown_pct": 5.0
            }
        }
    }
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("INSERT INTO research_experiments (id, timestamp, experiment_json) VALUES (?, ?, ?)",
                     ("exp_123", datetime.utcnow().isoformat(), json.dumps(dummy_exp)))
    yield

def _mock_run(start_time, end_time, validation_id="val_1", drift=ForwardDriftState.STABLE):
    spec = FrozenSpecification(
        strategy="Trend",
        symbols=["BTC"],
        timeframe="1d",
        historical_end=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    return ForwardValidationRun(
        validation_id=validation_id,
        identity_hash="ident_1",
        reference_experiment_id="hist_exp",
        frozen_specification=spec,
        state=ForwardValidationState.COMPLETED,
        forward_start=start_time,
        forward_end=end_time,
        result_experiment_id="exp_123",
        drift_state=drift
    )

def test_track_record_creation_and_chronology():
    service = PaperTrackRecordService()
    
    run1 = _mock_run(
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 2, 1, tzinfo=timezone.utc),
        "val_1"
    )
    success, msg = service.append_validation_run(run1)
    assert success is True
    
    # 4. overlapping validation detection
    run2_overlap = _mock_run(
        datetime(2025, 1, 15, tzinfo=timezone.utc),
        datetime(2025, 2, 15, tzinfo=timezone.utc),
        "val_2"
    )
    success, msg = service.append_validation_run(run2_overlap)
    assert success is False
    assert "overlap" in msg
    
    # Check that health state became DATA_QUALITY_ISSUE
    rec = service.get_track_record("ident_1", run1.frozen_specification.get_hash())
    assert rec.current_health_state == StrategyHealthState.DATA_QUALITY_ISSUE
    
def test_duplicate_observation_prevention():
    service = PaperTrackRecordService()
    run = _mock_run(
        datetime(2025, 1, 1, tzinfo=timezone.utc),
        datetime(2025, 2, 1, tzinfo=timezone.utc),
        "val_1"
    )
    
    assert service.append_validation_run(run)[0] is True
    # 5. duplicate observation prevention
    assert service.append_validation_run(run)[0] is False

def test_cumulative_equity():
    service = PaperTrackRecordService()
    
    # First month makes $500
    r1 = _mock_run(datetime(2025, 1, 1, tzinfo=timezone.utc), datetime(2025, 2, 1, tzinfo=timezone.utc), "v1")
    service.append_validation_run(r1)
    
    # We must insert a new experiment for v2
    dummy_exp2 = {
        "out_of_sample_report": {
            "trade_metrics": {"net_profit": 300.0, "total_trades": 5, "win_rate_pct": 50.0, "profit_factor": 1.2},
            "equity_metrics": {"max_drawdown_pct": 2.0}
        }
    }
    with sqlite3.connect(config.DB_PATH) as conn:
        conn.execute("INSERT INTO research_experiments (id, timestamp, experiment_json) VALUES (?, ?, ?)",
                     ("exp_456", datetime.utcnow().isoformat(), json.dumps(dummy_exp2)))
    
    r2 = _mock_run(datetime(2025, 2, 2, tzinfo=timezone.utc), datetime(2025, 3, 1, tzinfo=timezone.utc), "v2")
    r2.result_experiment_id = "exp_456"
    
    service.append_validation_run(r2)
    
    rec = service.get_track_record("ident_1", r1.frozen_specification.get_hash())
    # 6. cumulative equity
    # initial 10000 + 500 + 300 = 10800
    assert rec.current_equity == 10800.0
    assert rec.cumulative_pnl == 800.0
    assert rec.observation_count == 2
    
def test_health_analyzer():
    base_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
    # 10. insufficient history
    obs1 = PaperObservation(
        observation_id="1", track_record_id="t1", validation_id="v1",
        observation_start=base_time, observation_end=base_time + timedelta(days=1),
        starting_equity=1, ending_equity=1, net_pnl=1, trade_count=1, win_rate=1, profit_factor=1, drawdown_pct=1,
        drift_state="STABLE"
    )
    assert StrategyHealthAnalyzer.evaluate([obs1])[0] == StrategyHealthState.INSUFFICIENT_HISTORY
    
    # 11. health state transition
    obs2 = obs1.model_copy(update={"observation_id": "2", "drift_state": "STABLE", "observation_start": base_time + timedelta(days=1), "observation_end": base_time + timedelta(days=2)})
    obs3 = obs1.model_copy(update={"observation_id": "3", "drift_state": "DEGRADED", "observation_start": base_time + timedelta(days=2), "observation_end": base_time + timedelta(days=3)})
    
    # 13. no overreaction to single weak period
    state, _ = StrategyHealthAnalyzer.evaluate([obs1, obs2, obs3])
    assert state == StrategyHealthState.WATCH
    
    # 14. persistent degradation detection
    obs4 = obs1.model_copy(update={"observation_id": "4", "drift_state": "DEGRADED", "observation_start": base_time + timedelta(days=3), "observation_end": base_time + timedelta(days=4)})
    state, _ = StrategyHealthAnalyzer.evaluate([obs2, obs3, obs4])
    assert state == StrategyHealthState.DEGRADED
    
    obs5 = obs1.model_copy(update={"observation_id": "5", "drift_state": "SIGNIFICANTLY_DEGRADED", "observation_start": base_time + timedelta(days=4), "observation_end": base_time + timedelta(days=5)})
    obs6 = obs1.model_copy(update={"observation_id": "6", "drift_state": "SIGNIFICANTLY_DEGRADED", "observation_start": base_time + timedelta(days=5), "observation_end": base_time + timedelta(days=6)})
    obs7 = obs1.model_copy(update={"observation_id": "7", "drift_state": "SIGNIFICANTLY_DEGRADED", "observation_start": base_time + timedelta(days=6), "observation_end": base_time + timedelta(days=7)})
    state, _ = StrategyHealthAnalyzer.evaluate([obs5, obs6, obs7])
    assert state == StrategyHealthState.CRITICAL
