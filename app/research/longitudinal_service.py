import logging
import sqlite3
import uuid
from typing import List, Optional, Dict
from datetime import datetime

from app.research.longitudinal_models import (
    LongitudinalEventType, StateTransition, LongitudinalEvent, CandidateTimeline
)
from app.research.portfolio_service import ResearchPortfolioService
from app.research.portfolio_models import ResearchCandidateSnapshot
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class LongitudinalCandidateTracker:
    """Reconstructs the chronological evolution of a Research Candidate."""
    
    def __init__(self):
        self.portfolio_service = ResearchPortfolioService()
        
    def _fetch_all_timestamps(self, identity_hash: str, as_of: Optional[datetime] = None) -> List[Dict]:
        """Fetch all raw events that might have changed candidate state."""
        events = []
        
        def _add_event(ts_str, evt_type, source_id, extra=None):
            if not ts_str: return
            try:
                dt = datetime.fromisoformat(ts_str)
                if as_of:
                    # Strip tz if as_of doesn't have it for comparison, or assume UTC
                    dt_comp = dt.replace(tzinfo=None) if as_of.tzinfo is None else dt
                    as_comp = as_of.replace(tzinfo=None) if dt.tzinfo is None else as_of
                    if dt_comp > as_comp:
                        return
                events.append({
                    "timestamp": dt,
                    "event_type": evt_type,
                    "source_id": source_id,
                    "extra": extra or {}
                })
            except Exception as e:
                logger.debug(f"Invalid timestamp {ts_str}: {e}")

        try:
            with self.portfolio_service.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                
                # 1. First Seen
                cursor.execute("SELECT first_seen_at FROM research_memory WHERE identity_hash = ?", (identity_hash,))
                row = cursor.fetchone()
                if row and row[0]:
                    _add_event(row[0], LongitudinalEventType.CANDIDATE_DISCOVERED, identity_hash)
                    
                # 2. Conclusions
                cursor.execute("SELECT conclusion_id, created_at FROM research_conclusions WHERE identity_hash = ?", (identity_hash,))
                for row in cursor.fetchall():
                    _add_event(row[1], LongitudinalEventType.CONCLUSION_CHANGED, row[0])
                    
                # 3. Conflicts
                try:
                    cursor.execute("SELECT conflict_id, created_at, resolution_status FROM research_conflicts WHERE identity_hash = ?", (identity_hash,))
                    for row in cursor.fetchall():
                        _add_event(row[1], LongitudinalEventType.CONFLICT_OPENED, row[0])
                        # We don't have a resolved_at timestamp in the schema, so we approximate or just skip resolved events for now.
                except sqlite3.OperationalError:
                    pass
                    
                # 4. Opportunities
                cursor.execute("SELECT opportunity_id, created_at FROM research_opportunities WHERE identity_hash = ?", (identity_hash,))
                for row in cursor.fetchall():
                    _add_event(row[1], LongitudinalEventType.OPPORTUNITY_OPENED, row[0])
                    
        except Exception as e:
            logger.error(f"Failed to fetch base events: {e}")
            
        try:
            with self.portfolio_service.track_service._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT track_record_id FROM paper_track_records WHERE identity_hash = ?", (identity_hash,))
                tr_row = cursor.fetchone()
                if tr_row:
                    tr_id = tr_row[0]
                    # Observations
                    cursor.execute("SELECT observation_id, observation_end, drift_state FROM paper_observations WHERE track_record_id = ?", (tr_id,))
                    for row in cursor.fetchall():
                        _add_event(row[1], LongitudinalEventType.FORWARD_OBSERVATION_ADDED, row[0])
                        if row[2] and row[2] != "UNRESOLVED":
                            _add_event(row[1], LongitudinalEventType.DRIFT_DETECTED, row[0])
                            
                    # Health
                    cursor.execute("SELECT history_id, created_at FROM paper_health_history WHERE track_record_id = ?", (tr_id,))
                    for row in cursor.fetchall():
                        _add_event(row[1], LongitudinalEventType.HEALTH_CHANGED, row[0])
                        
        except Exception as e:
            logger.error(f"Failed to fetch track record events: {e}")
            
        # Sort chronologically. If tie, sort by event_type name to be deterministic
        events.sort(key=lambda x: (x["timestamp"], x["event_type"].value))
        return events

    def _compute_transitions(self, old: Optional[ResearchCandidateSnapshot], new: ResearchCandidateSnapshot, evt_type: LongitudinalEventType) -> List[StateTransition]:
        if not old:
            return [StateTransition(field_name="candidate", previous_state="NONE", new_state="CREATED", reason="Candidate initial creation.")]
            
        transitions = []
        
        if old.priority != new.priority:
            # Deterministic reason based on what actually changed
            reason = "Priority computed from new evidence score."
            if new.missing_lineage: reason = "Lineage broke."
            elif old.unresolved_conflicts < new.unresolved_conflicts: reason = "New unresolved conflict."
            elif old.current_health != new.current_health: reason = f"Health changed to {new.current_health.value}."
            elif old.forward_observation_count < new.forward_observation_count: reason = "Forward observation count increased."
            
            transitions.append(StateTransition(
                field_name="priority",
                previous_state=old.priority.value,
                new_state=new.priority.value,
                reason=reason
            ))
            
        if old.evidence_score.total_score != new.evidence_score.total_score:
            transitions.append(StateTransition(
                field_name="evidence_score",
                previous_state=str(old.evidence_score.total_score),
                new_state=str(new.evidence_score.total_score),
                reason=f"Score updated upon {evt_type.value}"
            ))
            
        if old.current_health != new.current_health:
            transitions.append(StateTransition(
                field_name="health",
                previous_state=old.current_health.value,
                new_state=new.current_health.value,
                reason="Health state transition detected."
            ))
            
        if old.decision_state != new.decision_state:
            transitions.append(StateTransition(
                field_name="decision_state",
                previous_state=old.decision_state.value,
                new_state=new.decision_state.value,
                reason="Research Conclusion updated."
            ))
            
        if old.forward_observation_count != new.forward_observation_count:
            transitions.append(StateTransition(
                field_name="forward_observation_count",
                previous_state=str(old.forward_observation_count),
                new_state=str(new.forward_observation_count),
                reason="New forward validation paper observation added."
            ))
            
        if old.unresolved_conflicts != new.unresolved_conflicts:
            transitions.append(StateTransition(
                field_name="unresolved_conflicts",
                previous_state=str(old.unresolved_conflicts),
                new_state=str(new.unresolved_conflicts),
                reason="Conflict count changed."
            ))

        return transitions

    def get_history(self, identity_hash: str, as_of: Optional[datetime] = None) -> CandidateTimeline:
        """
        Reconstructs the longitudinal history of a candidate up to `as_of`.
        Does not mutate any records.
        """
        telemetry.record_stage("PAPER_LONGITUDINAL_HISTORY_LOADED")
        
        raw_events = self._fetch_all_timestamps(identity_hash, as_of)
        
        timeline_events = []
        last_snapshot = None
        
        health_transitions_count = 0
        priority_transitions_count = 0
        
        # We only need to compute snapshot if state likely changed. But for safety, we compute it.
        # To avoid performance hit on many events, we deduplicate by timestamp.
        # But wait, we want to attribute transitions to the specific event.
        
        for raw in raw_events:
            ts = raw["timestamp"]
            evt_type = raw["event_type"]
            src_id = raw["source_id"]
            
            # Compute snapshot AS OF this exact event's timestamp
            current_snapshot = self.portfolio_service.build_snapshot(identity_hash, as_of=ts)
            
            if current_snapshot:
                transitions = self._compute_transitions(last_snapshot, current_snapshot, evt_type)
                
                # Update counts
                for t in transitions:
                    if t.field_name == "health": health_transitions_count += 1
                    if t.field_name == "priority": priority_transitions_count += 1
                
                # Even if no major transitions, we still record the event if it's significant
                evt = LongitudinalEvent(
                    event_id=str(uuid.uuid4()),
                    timestamp=ts,
                    event_type=evt_type,
                    source_record_id=src_id,
                    transitions=transitions,
                    resulting_snapshot=current_snapshot
                )
                timeline_events.append(evt)
                last_snapshot = current_snapshot

        # The final snapshot requested
        final_snapshot = self.portfolio_service.build_snapshot(identity_hash, as_of=as_of)

        return CandidateTimeline(
            identity_hash=identity_hash,
            events=timeline_events,
            latest_snapshot=final_snapshot,
            total_forward_observations=final_snapshot.forward_observation_count if final_snapshot else 0,
            health_transitions_count=health_transitions_count,
            priority_transitions_count=priority_transitions_count,
            as_of=as_of
        )
