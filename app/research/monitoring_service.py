import logging
import sqlite3
import traceback
from datetime import datetime
from typing import List

from app.config import config
from app.research.monitoring_models import MonitoringCycleResult, MonitoringCycleStatus
from app.research.forward_validation_service import ForwardValidationService
from app.research.track_record_service import PaperTrackRecordService
from app.research.decision_engine import ResearchDecisionEngine
from app.research.knowledge_service import ResearchKnowledgeService
from app.research.track_record_models import StrategyHealthState
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class PaperMonitoringService:
    """Bounded, idempotent cycle to ingest forward validations into track records."""
    
    def __init__(self, max_validations_per_cycle: int = 50):
        self.max_validations_per_cycle = max_validations_per_cycle
        self.validation_service = ForwardValidationService()
        self.track_service = PaperTrackRecordService()
        self.decision_engine = ResearchDecisionEngine()
        self.knowledge_service = ResearchKnowledgeService()
        
    def _get_conn(self):
        return sqlite3.connect(config.DB_PATH)

    def run_cycle(self) -> MonitoringCycleResult:
        result = MonitoringCycleResult()
        telemetry.record_stage("PAPER_MONITOR_CYCLE_STARTED")
        
        try:
            # 1. Discover COMPLETED validations not in paper_observations
            pending_validations = self._discover_pending_validations()
            result.validations_discovered = len(pending_validations)
            
            if not pending_validations:
                result.status = MonitoringCycleStatus.NO_CHANGES
                result.end_time = datetime.utcnow()
                telemetry.record_stage("PAPER_MONITOR_NO_CHANGES")
                return result
                
            # 2. Process bounded chunk
            chunk = pending_validations[:self.max_validations_per_cycle]
            
            for val_id in chunk:
                try:
                    self._process_validation(val_id, result)
                except Exception as e:
                    logger.error(f"Error processing validation {val_id}: {e}")
                    result.errors += 1
                    result.error_messages.append(f"{val_id}: {str(e)}")
                    
            # 3. Determine status
            if result.errors == 0:
                result.status = MonitoringCycleStatus.COMPLETED
            elif result.observations_recorded > 0:
                result.status = MonitoringCycleStatus.PARTIAL
                telemetry.record_stage("PAPER_MONITOR_PARTIAL")
            else:
                result.status = MonitoringCycleStatus.FAILED
                telemetry.record_stage("PAPER_MONITOR_FAILED")
                
            result.end_time = datetime.utcnow()
            telemetry.record_stage("PAPER_MONITOR_CYCLE_COMPLETED")
            self._save_cycle_result(result)
            return result
            
        except Exception as e:
            logger.error(f"Cycle failed: {e}\n{traceback.format_exc()}")
            result.status = MonitoringCycleStatus.FAILED
            result.errors += 1
            result.error_messages.append(f"Cycle Exception: {str(e)}")
            result.end_time = datetime.utcnow()
            telemetry.record_stage("PAPER_MONITOR_FAILED")
            self._save_cycle_result(result)
            return result
            
    def _save_cycle_result(self, result: MonitoringCycleResult):
        if not config.ENABLE_PERSISTENCE: return
        import json
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO paper_monitoring_cycles 
                    (cycle_id, status, validations_discovered, observations_recorded, duplicates_skipped,
                     health_transitions, opportunities_created, knowledge_updates, errors, error_messages_json,
                     start_time, end_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result.cycle_id, result.status.value, result.validations_discovered, result.observations_recorded,
                    result.duplicates_skipped, result.health_transitions, result.opportunities_created,
                    result.knowledge_updates, result.errors, json.dumps(result.error_messages),
                    result.start_time.isoformat(), result.end_time.isoformat() if result.end_time else None
                ))
        except Exception as e:
            logger.error(f"Failed to save monitoring cycle result: {e}")

    def _discover_pending_validations(self) -> List[str]:
        if not config.ENABLE_PERSISTENCE: return []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Find runs that are COMPLETED but not in paper_observations
                cursor.execute("""
                    SELECT f.validation_id 
                    FROM forward_validation_runs f
                    LEFT JOIN paper_observations p ON f.validation_id = p.validation_id
                    WHERE f.state = 'COMPLETED' AND p.observation_id IS NULL
                    ORDER BY f.created_at ASC
                """)
                return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            logger.error(f"Error discovering validations: {e}")
            return []

    def _process_validation(self, validation_id: str, result: MonitoringCycleResult):
        # Fetch the complete run
        run = self.validation_service.get_run(validation_id)
        if not run:
            result.errors += 1
            result.error_messages.append(f"{validation_id}: Run not found")
            return
            
        # Get pre-existing health state if record exists
        frozen_hash = run.frozen_specification.get_hash()
        pre_record = self.track_service.get_track_record(run.identity_hash, frozen_hash)
        old_health = pre_record.current_health_state if pre_record else StrategyHealthState.INSUFFICIENT_HISTORY
        
        # Append validation run
        success, msg = self.track_service.append_validation_run(run)
        
        if not success:
            if "already appended" in msg:
                result.duplicates_skipped += 1
                telemetry.record_stage("PAPER_MONITOR_DUPLICATE_SKIPPED")
            else:
                result.errors += 1
                result.error_messages.append(f"{validation_id}: {msg}")
            return
            
        result.observations_recorded += 1
        telemetry.record_stage("PAPER_MONITOR_OBSERVATION_RECORDED")
        
        # Post-append checks
        post_record = self.track_service.get_track_record(run.identity_hash, frozen_hash)
        if not post_record:
            return
            
        if post_record.track_record_id not in result.track_records_touched:
            result.track_records_touched.append(post_record.track_record_id)
            
        # 1. Did Health Change?
        new_health = post_record.current_health_state
        if old_health != new_health:
            result.health_transitions += 1
            telemetry.record_stage("PAPER_MONITOR_HEALTH_CHANGED")
            
            # Emit Knowledge Change
            from app.research.knowledge_models import ResearchKnowledgeChange
            from datetime import datetime
            import uuid
            
            change = ResearchKnowledgeChange(
                change_id=str(uuid.uuid4()),
                identity_hash=run.identity_hash,
                change_type="HEALTH_STATE_CHANGED",
                reason=f"Health transitioned from {old_health.value} to {new_health.value} due to new observation (Validation: {validation_id})",
                source_reference_id=post_record.track_record_id,
                created_at=datetime.utcnow()
            )
            
            try:
                self.knowledge_service.record_knowledge_change(change)
                k_success = True
            except Exception as e:
                logger.error(f"Failed to record knowledge change: {e}")
                k_success = False
                
            if k_success:
                result.knowledge_updates += 1
                telemetry.record_stage("PAPER_MONITOR_KNOWLEDGE_UPDATED")
                
            if new_health in [StrategyHealthState.DEGRADED, StrategyHealthState.CRITICAL]:
                result.opportunities_created += 1
                telemetry.record_stage("PAPER_MONITOR_DEGRADATION_DETECTED")
                
        # 2. Trigger Decision Engine to re-evaluate evidence
        try:
            self.decision_engine.evaluate_identity(run.identity_hash)
        except Exception as e:
            logger.warning(f"Decision engine evaluation failed for {run.identity_hash}: {e}")
            # Non-fatal for the monitoring cycle
