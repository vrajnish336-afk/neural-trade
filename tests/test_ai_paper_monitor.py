import pytest
import sqlite3
import uuid
import json
from datetime import datetime, timezone
from app.database.schema import init_db
from app.config import config
from app.research.monitoring_models import MonitoringCycleStatus
from app.research.monitoring_service import PaperMonitoringService
from app.research.forward_validation_models import ForwardValidationRun, FrozenSpecification, ForwardValidationState, ForwardDriftState
from app.research.forward_validation_service import ForwardValidationService

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_monitor.sqlite"
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
                     ("exp_mon_1", datetime.utcnow().isoformat(), json.dumps(dummy_exp)))
                     
    # Create memory entry for testing opportunity emission
    from app.research.memory_repository import ResearchMemoryRepository
    from app.research.memory_models import ResearchMemoryRecord
    repo = ResearchMemoryRepository()
    repo.save_memory(ResearchMemoryRecord(
        identity_hash="ident_mon",
        canonical_hypothesis="test hypothesis",
        affected_symbols=["BTC"],
        mapped_strategy="Trend",
        first_seen_at=datetime.utcnow()
    ))
    yield

def _inject_validation(validation_id="val_mon_1", drift=ForwardDriftState.STABLE):
    fvs = ForwardValidationService()
    spec = FrozenSpecification(
        strategy="Trend",
        symbols=["BTC"],
        timeframe="1d",
        historical_end=datetime(2024, 1, 1, tzinfo=timezone.utc)
    )
    run = ForwardValidationRun(
        validation_id=validation_id,
        identity_hash="ident_mon",
        reference_experiment_id="hist_exp",
        frozen_specification=spec,
        state=ForwardValidationState.COMPLETED,
        forward_start=datetime(2025, 1, 1, tzinfo=timezone.utc),
        forward_end=datetime(2025, 2, 1, tzinfo=timezone.utc),
        result_experiment_id="exp_mon_1",
        drift_state=drift
    )
    fvs._save_run(run)

def test_empty_cycle():
    service = PaperMonitoringService()
    res = service.run_cycle()
    assert res.status == MonitoringCycleStatus.NO_CHANGES
    assert res.validations_discovered == 0

def test_new_forward_validation_discovery():
    _inject_validation("val_mon_1")
    
    service = PaperMonitoringService()
    res = service.run_cycle()
    assert res.status == MonitoringCycleStatus.COMPLETED
    assert res.validations_discovered == 1
    assert res.observations_recorded == 1
    assert res.errors == 0
    
def test_idempotent_rerun():
    _inject_validation("val_mon_1")
    service = PaperMonitoringService()
    service.run_cycle()
    
    # 20. idempotent rerun
    res2 = service.run_cycle()
    assert res2.status == MonitoringCycleStatus.NO_CHANGES
    assert res2.validations_discovered == 0
    assert res2.observations_recorded == 0

def test_health_transition_opportunity_and_knowledge():
    # Insert 3 SIGNIFICANTLY_DEGRADED observations to force CRITICAL
    _inject_validation("val_mon_1", drift=ForwardDriftState.SIGNIFICANTLY_DEGRADED)
    _inject_validation("val_mon_2", drift=ForwardDriftState.SIGNIFICANTLY_DEGRADED)
    _inject_validation("val_mon_3", drift=ForwardDriftState.SIGNIFICANTLY_DEGRADED)
    
    # We must stagger dates to avoid chronological data quality error
    fvs = ForwardValidationService()
    for i in range(1, 4):
        r = fvs.get_run(f"val_mon_{i}")
        r.forward_start = datetime(2025, i, 1, tzinfo=timezone.utc)
        r.forward_end = datetime(2025, i, 28, tzinfo=timezone.utc)
        fvs._save_run(r)
        
    service = PaperMonitoringService()
    res = service.run_cycle()
    
    assert res.status == MonitoringCycleStatus.COMPLETED
    assert res.validations_discovered == 3
    assert res.observations_recorded == 3
    
    # Health should transition to CRITICAL
    assert res.health_transitions > 0
    assert res.opportunities_created > 0
    assert res.knowledge_updates > 0
    
    # Verify DB state
    with sqlite3.connect(config.DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT current_health_state FROM paper_track_records")
        assert cursor.fetchone()[0] == "CRITICAL"
        
        # 12. degradation opportunity
        cursor.execute("SELECT opportunity_id FROM research_opportunities WHERE source_analysis_id = 'health_monitor'")
        assert cursor.fetchone() is not None
        
        # 14. knowledge update
        cursor.execute("SELECT change_id FROM research_knowledge_changes WHERE change_type = 'HEALTH_STATE_CHANGED'")
        assert cursor.fetchone() is not None
