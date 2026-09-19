import logging
import uuid
import json
import sqlite3
from datetime import datetime
from typing import Optional, List

from app.config import config
from app.research.track_record_models import PaperTrackRecord, PaperObservation, PaperHealthHistory, StrategyHealthState
from app.research.forward_validation_models import ForwardValidationRun
from app.research.health_analyzer import StrategyHealthAnalyzer
from app.diagnostics.telemetry import telemetry
from app.research.forward_validation_service import ForwardValidationService

logger = logging.getLogger(__name__)

class PaperTrackRecordService:
    def _get_conn(self):
        return sqlite3.connect(config.DB_PATH)

    def get_track_record(self, identity_hash: str, frozen_specification_hash: str) -> Optional[PaperTrackRecord]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT track_record_id, initial_equity, current_equity, cumulative_pnl, 
                           cumulative_return_pct, max_drawdown_pct, observation_count, 
                           current_health_state, first_observation_start, last_observation_end,
                           created_at, updated_at
                    FROM paper_track_records
                    WHERE identity_hash = ? AND frozen_specification_hash = ?
                """, (identity_hash, frozen_specification_hash))
                row = cursor.fetchone()
                if row:
                    return PaperTrackRecord(
                        track_record_id=row[0],
                        identity_hash=identity_hash,
                        frozen_specification_hash=frozen_specification_hash,
                        initial_equity=row[1],
                        current_equity=row[2],
                        cumulative_pnl=row[3],
                        cumulative_return_pct=row[4],
                        max_drawdown_pct=row[5],
                        observation_count=row[6],
                        current_health_state=StrategyHealthState(row[7]),
                        first_observation_start=datetime.fromisoformat(row[8]) if row[8] else None,
                        last_observation_end=datetime.fromisoformat(row[9]) if row[9] else None,
                        created_at=datetime.fromisoformat(row[10]),
                        updated_at=datetime.fromisoformat(row[11])
                    )
        except Exception as e:
            logger.error(f"Error fetching track record: {e}")
        return None

    def _save_track_record(self, record: PaperTrackRecord) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO paper_track_records 
                    (track_record_id, identity_hash, frozen_specification_hash, initial_equity,
                     current_equity, cumulative_pnl, cumulative_return_pct, max_drawdown_pct,
                     observation_count, current_health_state, first_observation_start, 
                     last_observation_end, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.track_record_id, record.identity_hash, record.frozen_specification_hash,
                    record.initial_equity, record.current_equity, record.cumulative_pnl,
                    record.cumulative_return_pct, record.max_drawdown_pct, record.observation_count,
                    record.current_health_state.value,
                    record.first_observation_start.isoformat() if record.first_observation_start else None,
                    record.last_observation_end.isoformat() if record.last_observation_end else None,
                    record.created_at.isoformat(), record.updated_at.isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Error saving track record: {e}")
            return False

    def get_observations(self, track_record_id: str) -> List[PaperObservation]:
        observations = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT observation_id, validation_id, observation_start, observation_end,
                           starting_equity, ending_equity, net_pnl, trade_count, win_rate,
                           profit_factor, drawdown_pct, regime_distribution_json, drift_state, created_at
                    FROM paper_observations
                    WHERE track_record_id = ?
                    ORDER BY observation_start ASC
                """, (track_record_id,))
                for row in cursor.fetchall():
                    observations.append(PaperObservation(
                        observation_id=row[0],
                        track_record_id=track_record_id,
                        validation_id=row[1],
                        observation_start=datetime.fromisoformat(row[2]),
                        observation_end=datetime.fromisoformat(row[3]),
                        starting_equity=row[4],
                        ending_equity=row[5],
                        net_pnl=row[6],
                        trade_count=row[7],
                        win_rate=row[8],
                        profit_factor=row[9],
                        drawdown_pct=row[10],
                        regime_distribution=json.loads(row[11]) if row[11] else {},
                        drift_state=row[12],
                        created_at=datetime.fromisoformat(row[13])
                    ))
        except Exception as e:
            logger.error(f"Error fetching observations: {e}")
        return observations

    def _save_observation(self, obs: PaperObservation) -> bool:
        if not config.ENABLE_PERSISTENCE: return False
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO paper_observations 
                    (observation_id, track_record_id, validation_id, observation_start, observation_end,
                     starting_equity, ending_equity, net_pnl, trade_count, win_rate, profit_factor,
                     drawdown_pct, regime_distribution_json, drift_state, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    obs.observation_id, obs.track_record_id, obs.validation_id,
                    obs.observation_start.isoformat(), obs.observation_end.isoformat(),
                    obs.starting_equity, obs.ending_equity, obs.net_pnl, obs.trade_count,
                    obs.win_rate, obs.profit_factor, obs.drawdown_pct,
                    json.dumps(obs.regime_distribution), obs.drift_state, obs.created_at.isoformat()
                ))
            return True
        except Exception as e:
            logger.error(f"Error saving observation: {e}")
            return False

    def append_validation_run(self, run: ForwardValidationRun) -> tuple[bool, str]:
        if run.state.value != "COMPLETED":
            return False, "Validation run is not COMPLETED."
            
        frozen_hash = run.frozen_specification.get_hash()
        record = self.get_track_record(run.identity_hash, frozen_hash)
        
        if not record:
            record = PaperTrackRecord(
                track_record_id=str(uuid.uuid4()),
                identity_hash=run.identity_hash,
                frozen_specification_hash=frozen_hash
            )
            self._save_track_record(record)
            telemetry.record_stage("PAPER_TRACK_CREATED")
            
        # Duplicate validation check
        existing = self.get_observations(record.track_record_id)
        if any(o.validation_id == run.validation_id for o in existing):
            telemetry.record_stage("PAPER_OBSERVATION_DUPLICATE")
            return False, "Validation run already appended."
            
        # Extract metrics
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (run.result_experiment_id,))
                row = cursor.fetchone()
                if not row:
                    return False, "Missing experiment result."
                exp_data = json.loads(row[0])
                metrics = exp_data.get("out_of_sample_report", {}).get("trade_metrics", {})
                equity_metrics = exp_data.get("out_of_sample_report", {}).get("equity_metrics", {})
        except Exception as e:
            return False, f"Failed to extract metrics: {e}"

        obs_start = run.forward_start
        obs_end = run.forward_end
        
        # Chronological boundary check
        if record.last_observation_end and obs_start < record.last_observation_end:
            record.current_health_state = StrategyHealthState.DATA_QUALITY_ISSUE
            self._save_track_record(record)
            self._record_health_change(record, StrategyHealthState.DATA_QUALITY_ISSUE, run.validation_id, "Overlapping periods detected.")
            telemetry.record_stage("PAPER_DATA_QUALITY_ISSUE")
            return False, "Chronological violation: overlapping forward period."

        obs = PaperObservation(
            observation_id=str(uuid.uuid4()),
            track_record_id=record.track_record_id,
            validation_id=run.validation_id,
            observation_start=obs_start,
            observation_end=obs_end,
            starting_equity=record.current_equity,
            ending_equity=record.current_equity + metrics.get("net_profit", 0.0),
            net_pnl=metrics.get("net_profit", 0.0),
            trade_count=metrics.get("total_trades", 0),
            win_rate=metrics.get("win_rate_pct", 0.0),
            profit_factor=metrics.get("profit_factor", 0.0),
            drawdown_pct=equity_metrics.get("max_drawdown_pct", 0.0),
            drift_state=run.drift_state.value if run.drift_state else "UNRESOLVED"
        )
        
        if not self._save_observation(obs):
            return False, "Database save failed."
            
        telemetry.record_stage("PAPER_OBSERVATION_RECORDED")

        # Update cumulative record
        record.observation_count += 1
        record.current_equity = obs.ending_equity
        record.cumulative_pnl += obs.net_pnl
        record.cumulative_return_pct = ((record.current_equity - record.initial_equity) / record.initial_equity) * 100.0
        
        # Max drawdown is an approximation over periods
        if obs.drawdown_pct > record.max_drawdown_pct:
            record.max_drawdown_pct = obs.drawdown_pct
            
        if not record.first_observation_start:
            record.first_observation_start = obs.observation_start
        record.last_observation_end = obs.observation_end
        
        record.updated_at = datetime.utcnow()
        
        # Re-evaluate Health
        existing.append(obs)
        new_health, reason = StrategyHealthAnalyzer.evaluate(existing)
        
        if new_health != record.current_health_state:
            self._record_health_change(record, new_health, obs.observation_id, reason)
            record.current_health_state = new_health
            
        self._save_track_record(record)
        return True, "Observation recorded."

    def _record_health_change(self, record: PaperTrackRecord, new_state: StrategyHealthState, trigger_id: str, reason: str):
        if not config.ENABLE_PERSISTENCE: return
        history = PaperHealthHistory(
            history_id=str(uuid.uuid4()),
            track_record_id=record.track_record_id,
            previous_state=record.current_health_state,
            new_state=new_state,
            trigger_observation_id=trigger_id,
            reason=reason
        )
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO paper_health_history 
                    (history_id, track_record_id, previous_state, new_state, trigger_observation_id, reason, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    history.history_id, history.track_record_id, history.previous_state.value,
                    history.new_state.value, history.trigger_observation_id, history.reason,
                    history.created_at.isoformat()
                ))
            telemetry.record_stage("PAPER_HEALTH_CHANGED")
            
            # Emit Opportunity if degraded/critical
            if new_state in [StrategyHealthState.DEGRADED, StrategyHealthState.CRITICAL]:
                from app.research.memory_repository import ResearchMemoryRepository
                from app.research.memory_models import ResearchOpportunity, OpportunityStatus
                repo = ResearchMemoryRepository()
                mem = repo.get_memory(record.identity_hash)
                if mem:
                    opp = ResearchOpportunity(
                        opportunity_id=str(uuid.uuid4()),
                        source_analysis_id="health_monitor",
                        identity_hash=mem.identity_hash,
                        hypothesis_text=f"Investigate {new_state.value} health state in paper tracking.",
                        affected_symbols=mem.affected_symbols if mem.affected_symbols else [],
                        mapped_strategy=mem.mapped_strategy,
                        novelty_score=0.5,
                        evidence_gap_score=1.0,
                        data_availability_score=1.0,
                        duplicate_penalty=0.0,
                        research_priority=0.9,
                        status=OpportunityStatus.READY_FOR_RESEARCH,
                        reason=reason
                    )
                    repo.save_opportunity(opp)
                    telemetry.record_stage("PAPER_RESEARCH_OPPORTUNITY_CREATED")
        except Exception as e:
            logger.error(f"Error saving health history: {e}")
