import logging
import uuid
import traceback
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.research.orchestrator_models import ResearchJob, JobState, OrchestratorConfig
from app.research.loop_models import AIResearchRequest, ResearchRequestStatus
from app.research.memory_repository import ResearchMemoryRepository
from app.research.memory_models import OpportunityStatus, ResearchIdentity
from app.diagnostics.telemetry import telemetry
from app.config import config

from app.data.csv_provider import CsvHistoricalDataProvider
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.portfolio import PortfolioRiskConfig
from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.research.models import ResearchExperiment
from app.research.evidence import ResearchEvidenceEvaluator, EvidenceConclusion
from app.analytics.engine import generate_analytics_report

logger = logging.getLogger(__name__)

class ResearchJobOrchestrator:
    def __init__(self, data_dir: str = "data/historical", orchestrator_config: Optional[OrchestratorConfig] = None):
        self.memory_repo = ResearchMemoryRepository()
        self.data_dir = data_dir
        self.cfg = orchestrator_config or OrchestratorConfig()
        
    def _save_job(self, job: ResearchJob) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self.memory_repo._get_conn() as conn:
                conn.execute(
                    '''INSERT OR REPLACE INTO research_jobs 
                       (job_id, opportunity_id, identity_hash, priority, state, created_at, 
                        claimed_at, started_at, completed_at, retry_count, next_retry_at, 
                        failure_reason, result_experiment_id)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        job.job_id, job.opportunity_id, job.identity_hash, job.priority,
                        job.state.value, job.created_at.isoformat(), 
                        job.claimed_at.isoformat() if job.claimed_at else None,
                        job.started_at.isoformat() if job.started_at else None,
                        job.completed_at.isoformat() if job.completed_at else None,
                        job.retry_count, 
                        job.next_retry_at.isoformat() if job.next_retry_at else None,
                        job.failure_reason, job.result_experiment_id
                    )
                )
            return True
        except Exception as e:
            logger.error("Failed to save research job: %s", e)
            return False
            
    def _get_job(self, job_id: str) -> Optional[ResearchJob]:
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_jobs WHERE job_id = ?", (job_id,))
                row = cursor.fetchone()
                if row:
                    return ResearchJob(
                        job_id=row[0], opportunity_id=row[1], identity_hash=row[2], priority=row[3],
                        state=JobState(row[4]), created_at=datetime.fromisoformat(row[5]),
                        claimed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        started_at=datetime.fromisoformat(row[7]) if row[7] else None,
                        completed_at=datetime.fromisoformat(row[8]) if row[8] else None,
                        retry_count=row[9], next_retry_at=datetime.fromisoformat(row[10]) if row[10] else None,
                        failure_reason=row[11], result_experiment_id=row[12]
                    )
        except Exception as e:
            logger.error("Failed to fetch job: %s", e)
        return None
        
    def _recover_jobs(self):
        """Moves RUNNING or CLAIMED jobs without active execution back to QUEUED or FAILED."""
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT job_id FROM research_jobs WHERE state IN ('RUNNING', 'CLAIMED')")
                for row in cursor.fetchall():
                    job = self._get_job(row[0])
                    if job:
                        telemetry.record_stage("RECOVERY_DETECTED")
                        if job.retry_count < self.cfg.max_retries:
                            job.state = JobState.QUEUED
                            job.failure_reason = "Recovered from interrupted RUNNING state."
                            job.retry_count += 1
                        else:
                            job.state = JobState.FAILED
                            job.failure_reason = "Recovered from interrupted RUNNING state, max retries exceeded."
                            job.completed_at = datetime.utcnow()
                        self._save_job(job)
        except Exception as e:
            logger.error("Error during job recovery: %s", e)
            
    def _queue_jobs_from_opportunities(self) -> int:
        """Finds READY_FOR_RESEARCH opportunities and queues them if within capacity."""
        if not self.cfg.enabled: return 0
        
        # Check current queue size
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM research_jobs WHERE state = 'QUEUED'")
                current_q = cursor.fetchone()[0]
        except Exception:
            current_q = 0
            
        available_slots = self.cfg.max_queue_size - current_q
        if available_slots <= 0:
            telemetry.record_stage("QUEUE_FULL")
            return 0
            
        opps = self.memory_repo.get_unresolved_opportunities(limit=available_slots)
        queued_count = 0
        for opp in opps:
            # Duplicate check across jobs
            try:
                with self.memory_repo._get_conn() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM research_jobs WHERE identity_hash = ? AND state NOT IN ('FAILED', 'CANCELLED', 'SKIPPED')", (opp.identity_hash,))
                    if cursor.fetchone()[0] > 0:
                        opp.status = OpportunityStatus.DUPLICATE
                        opp.reason = "A job for this identity already exists."
                        self.memory_repo.save_opportunity(opp)
                        continue
            except Exception:
                pass
                
            job = ResearchJob(
                job_id=str(uuid.uuid4()),
                opportunity_id=opp.opportunity_id,
                identity_hash=opp.identity_hash,
                priority=opp.research_priority
            )
            if self._save_job(job):
                opp.status = OpportunityStatus.COMPLETED
                opp.reason = f"Queued as job {job.job_id}"
                self.memory_repo.save_opportunity(opp)
                telemetry.record_stage("JOB_QUEUED")
                queued_count += 1
                
        return queued_count
        
    def run_cycle(self) -> int:
        """The main bounded execution loop."""
        if not self.cfg.enabled: return 0
        
        telemetry.record_stage("CYCLE_STARTED")
        
        self._recover_jobs()
        self._queue_jobs_from_opportunities()
        
        # Claim jobs
        claimed_jobs = []
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                # Fetch pending (QUEUED or RETRY_WAIT if past next_retry_at)
                now_str = datetime.utcnow().isoformat()
                cursor.execute(f"""
                    SELECT job_id FROM research_jobs 
                    WHERE state = 'QUEUED' OR (state = 'RETRY_WAIT' AND next_retry_at <= ?)
                    ORDER BY priority DESC, created_at ASC
                    LIMIT ?
                """, (now_str, self.cfg.max_jobs_per_cycle))
                for row in cursor.fetchall():
                    job = self._get_job(row[0])
                    if job:
                        job.state = JobState.CLAIMED
                        job.claimed_at = datetime.utcnow()
                        if self._save_job(job):
                            claimed_jobs.append(job)
                            telemetry.record_stage("JOB_CLAIMED")
        except Exception as e:
            logger.error("Failed to claim jobs: %s", e)
            
        executed_count = 0
        for job in claimed_jobs:
            self._execute_job(job)
            executed_count += 1
            
        telemetry.record_stage("CYCLE_COMPLETED")
        return executed_count
        
    def _execute_job(self, job: ResearchJob):
        job.state = JobState.RUNNING
        job.started_at = datetime.utcnow()
        self._save_job(job)
        telemetry.record_stage("JOB_STARTED")
        
        # Rehydrate opportunity to get the hypothesis/symbols
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT hypothesis_text, affected_symbols, mapped_strategy FROM research_opportunities WHERE opportunity_id = ?", (job.opportunity_id,))
                row = cursor.fetchone()
                if not row:
                    self._fail_job(job, "Source opportunity not found.", retryable=False)
                    return
                import json
                hypothesis_text = row[0]
                affected_symbols = json.loads(row[1])
                mapped_strategy = row[2]
        except Exception as e:
            self._fail_job(job, f"Failed to load opportunity: {e}", retryable=True)
            return

        # 1. Dataset Loading (Deterministic isolation)
        try:
            provider = CsvHistoricalDataProvider(self.data_dir)
            bars = []
            start_time = datetime.utcnow() - timedelta(days=365)
            for sym in affected_symbols:
                try:
                    sym_bars = provider.get_historical_bars(sym, "1d", start_time)
                    bars.extend(sym_bars)
                except Exception:
                    logger.warning("No data for symbol %s", sym)
                    
            if not bars:
                self._fail_job(job, "No historical data found for affected symbols.", retryable=False)
                # Note: We don't fail the job if we expect data to arrive eventually, but currently if missing, it's missing.
                return
                
            bars.sort(key=lambda x: x.timestamp)
            
            if len(bars) < 100:
                self._fail_job(job, "Insufficient historical data depth after filtering.", retryable=False)
                return
                
            dataset_identity = {
                "source": self.data_dir,
                "start": bars[0].timestamp.isoformat(),
                "end": bars[-1].timestamp.isoformat(),
                "row_count": len(bars)
            }
            
            # 2. Engine Setup
            strategy = None
            if mapped_strategy == "TrendFollowing":
                from app.strategies.trend_following import TrendFollowingStrategy
                strategy = TrendFollowingStrategy()
            elif mapped_strategy == "MeanReversion":
                from app.strategies.mean_reversion import MeanReversionStrategy
                strategy = MeanReversionStrategy()
            elif mapped_strategy == "Breakout":
                from app.strategies.breakout import BreakoutStrategy
                strategy = BreakoutStrategy()
                
            if not strategy:
                self._fail_job(job, f"Mapped strategy {mapped_strategy} is invalid.", retryable=False)
                return
                
            ensemble = StrategyEnsemble([strategy])
            risk_engine = RiskEngine(PortfolioRiskLimits())
            cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.0005)
            
            engine = BacktestEngine(
                ensemble=ensemble,
                risk_engine=risk_engine,
                initial_capital=10000.0,
                cost_config=cost_config
            )
            
            # 3. Execution (Chronological)
            result = engine.run(bars)
            
            analytics_report = generate_analytics_report(job.job_id, result)
            
            # 5. Experiment / Evidence Wrapping
            experiment = ResearchExperiment(
                experiment_id=str(uuid.uuid4()),
                experiment_name=f"AI Job: {job.job_id}",
                dataset_id="local_csv",
                dataset_identity=dataset_identity,
                symbols=affected_symbols,
                timeframe="1d",
                strategy=mapped_strategy,
                configuration="default",
                starting_capital=10000.0,
                random_seed=42,
                created_at=datetime.utcnow(),
                status="COMPLETED",
                validation_results=[],
                out_of_sample_report=analytics_report
            )
            
            # 6. Evaluate Evidence
            summary = ResearchEvidenceEvaluator.evaluate(experiment)
            
            job.result_experiment_id = experiment.experiment_id
            job.state = JobState.SUCCEEDED
            job.completed_at = datetime.utcnow()
            self._save_job(job)
            telemetry.record_stage("JOB_SUCCEEDED")
            
            # 7. Update Memory
            identity = ResearchIdentity.generate(mapped_strategy, affected_symbols, hypothesis_text)
            mem = self.memory_repo.get_memory(identity.identity_hash)
            if mem:
                mem.last_researched_at = datetime.utcnow()
                mem.latest_experiment_id = job.result_experiment_id
                mem.latest_conclusion = summary.conclusion.value
                self.memory_repo.save_memory(mem)
                
        except Exception as e:
            logger.error("Error executing job: %s\n%s", e, traceback.format_exc())
            self._fail_job(job, str(e), retryable=True)

    def _fail_job(self, job: ResearchJob, reason: str, retryable: bool):
        job.failure_reason = reason
        if retryable and job.retry_count < self.cfg.max_retries:
            job.state = JobState.RETRY_WAIT
            job.retry_count += 1
            # Exponential backoff (minutes): 1, 2, 4, 8...
            job.next_retry_at = datetime.utcnow() + timedelta(minutes=(2 ** (job.retry_count - 1)))
            telemetry.record_stage("JOB_RETRY_SCHEDULED")
        else:
            job.state = JobState.FAILED
            job.completed_at = datetime.utcnow()
            telemetry.record_stage("JOB_FAILED")
        self._save_job(job)
