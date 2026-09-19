import pytest
import sqlite3
import uuid
import json
from datetime import datetime, timezone, timedelta
from app.database.schema import init_db
from app.config import config
from app.research.orchestrator_models import ResearchJob, JobState, OrchestratorConfig
from app.research.orchestrator_service import ResearchJobOrchestrator
from app.research.memory_models import ResearchOpportunity, OpportunityStatus
from app.research.memory_repository import ResearchMemoryRepository

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_jobs.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    yield

def _inject_opportunity(repo: ResearchMemoryRepository, priority: float = 1.0) -> ResearchOpportunity:
    opp = ResearchOpportunity(
        opportunity_id=str(uuid.uuid4()),
        source_analysis_id=str(uuid.uuid4()),
        identity_hash=str(uuid.uuid4()),
        hypothesis_text="test",
        affected_symbols=["BTC/USD"],
        mapped_strategy="TrendFollowing",
        novelty_score=1.0,
        evidence_gap_score=1.0,
        data_availability_score=1.0,
        duplicate_penalty=0.0,
        research_priority=priority,
        status=OpportunityStatus.READY_FOR_RESEARCH,
        reason="test"
    )
    repo.save_opportunity(opp)
    return opp

def test_job_queueing():
    orchestrator = ResearchJobOrchestrator()
    _inject_opportunity(orchestrator.memory_repo)
    
    queued = orchestrator._queue_jobs_from_opportunities()
    assert queued == 1
    
    # Attempting to queue again should not create a duplicate if the opportunity is COMPLETED
    queued = orchestrator._queue_jobs_from_opportunities()
    assert queued == 0

def test_run_cycle_claims_and_executes(tmp_path):
    cfg = OrchestratorConfig(max_jobs_per_cycle=1)
    orchestrator = ResearchJobOrchestrator(data_dir=str(tmp_path), orchestrator_config=cfg)
    opp = _inject_opportunity(orchestrator.memory_repo)
    
    orchestrator._queue_jobs_from_opportunities()
    
    # We expect this to fail gracefully due to missing data in tmp_path
    executed = orchestrator.run_cycle()
    
    # One job claimed and executed
    assert executed == 1
    
    # Verify failure state
    with orchestrator.memory_repo._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT state, retry_count FROM research_jobs")
        row = cursor.fetchone()
        assert row is not None
        # It's missing data, which in our logic is Non-Retryable currently (retryable=False for missing data)
        assert row[0] == JobState.FAILED.value
        assert row[1] == 0

def test_job_recovery():
    orchestrator = ResearchJobOrchestrator()
    job = ResearchJob(
        job_id=str(uuid.uuid4()),
        opportunity_id="fake",
        identity_hash="fake",
        state=JobState.RUNNING
    )
    orchestrator._save_job(job)
    
    # Run recovery
    orchestrator._recover_jobs()
    
    loaded = orchestrator._get_job(job.job_id)
    assert loaded.state == JobState.QUEUED
    assert loaded.retry_count == 1
    
def test_job_max_retries():
    orchestrator = ResearchJobOrchestrator(orchestrator_config=OrchestratorConfig(max_retries=1))
    job = ResearchJob(
        job_id=str(uuid.uuid4()),
        opportunity_id="fake",
        identity_hash="fake",
        state=JobState.RUNNING,
        retry_count=1 # already retried once
    )
    orchestrator._save_job(job)
    
    orchestrator._recover_jobs()
    
    loaded = orchestrator._get_job(job.job_id)
    assert loaded.state == JobState.FAILED
    assert "max retries exceeded" in loaded.failure_reason

def test_queue_size_limit():
    cfg = OrchestratorConfig(max_queue_size=2)
    orchestrator = ResearchJobOrchestrator(orchestrator_config=cfg)
    
    for _ in range(5):
        _inject_opportunity(orchestrator.memory_repo)
        
    queued = orchestrator._queue_jobs_from_opportunities()
    assert queued == 2
    
    # Remaining opps should stay READY_FOR_RESEARCH
    opps = orchestrator.memory_repo.get_unresolved_opportunities(limit=10)
    assert len(opps) == 3
