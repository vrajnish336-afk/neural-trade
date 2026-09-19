import uuid
import json
import sqlite3
import logging
from typing import List, Optional, Dict
from datetime import datetime

from app.config import config
from app.database.schema import init_db
from app.research.knowledge_models import (
    ResearchKnowledgeSnapshot, ResearchKnowledgeChange, KnowledgeChangeType,
    EvidenceGap, EvidenceGapType, EvidenceGapStatus
)
from app.research.decision_models import (
    ResearchDecisionState, ResearchConfidenceState, NextResearchAction,
    ResearchConclusion, ResearchConflict, ResearchRelationship
)
from app.research.decision_engine import ResearchDecisionEngine
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class ResearchKnowledgeService:
    """Service to consolidate Research Identity state into unified Snapshots and tracking History."""
    
    def __init__(self):
        self.decision_engine = ResearchDecisionEngine()
        
    def _get_conn(self):
        return sqlite3.connect(config.DB_PATH)

    def get_snapshot(self, identity_hash: str) -> Optional[ResearchKnowledgeSnapshot]:
        """Constructs an ephemeral, unified snapshot of what is currently known about an identity."""
        try:
            with self._get_conn() as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                
                # 1. Base Memory Record
                cursor.execute("SELECT * FROM research_memory WHERE identity_hash = ?", (identity_hash,))
                mem_row = cursor.fetchone()
                if not mem_row:
                    return None
                    
                canonical_hypothesis = mem_row["canonical_hypothesis"]
                affected_symbols = json.loads(mem_row["affected_symbols"]) if mem_row["affected_symbols"] else []
                mapped_strategy = mem_row["mapped_strategy"]
                first_seen_at = datetime.fromisoformat(mem_row["first_seen_at"]) if mem_row["first_seen_at"] else datetime.utcnow()
                
                # 2. Execution Stats
                cursor.execute("SELECT COUNT(*), SUM(CASE WHEN state='SUCCEEDED' THEN 1 ELSE 0 END) FROM research_jobs WHERE identity_hash = ?", (identity_hash,))
                jobs_row = cursor.fetchone()
                total_experiments = jobs_row[0] or 0
                total_completed = jobs_row[1] or 0
                
                # 3. Latest Conclusion
                cursor.execute("SELECT * FROM research_conclusions WHERE identity_hash = ? ORDER BY created_at DESC LIMIT 1", (identity_hash,))
                conc_row = cursor.fetchone()
                
                latest_conc = None
                decision = ResearchDecisionState.INSUFFICIENT_EVIDENCE
                confidence = ResearchConfidenceState.LOW
                action = NextResearchAction.COLLECT_MORE_DATA
                last_updated_at = first_seen_at
                
                if conc_row:
                    latest_conc = ResearchConclusion(
                        conclusion_id=conc_row["conclusion_id"],
                        identity_hash=conc_row["identity_hash"],
                        decision_state=ResearchDecisionState(conc_row["decision_state"]),
                        confidence_state=ResearchConfidenceState(conc_row["confidence_state"]),
                        summary=conc_row["summary"],
                        supporting_evidence_count=conc_row["supporting_evidence_count"],
                        conflicting_evidence_count=conc_row["conflicting_evidence_count"],
                        limitations=json.loads(conc_row["limitations"]) if conc_row["limitations"] else [],
                        next_research_action=NextResearchAction(conc_row["next_research_action"]),
                        ai_explanation=conc_row["ai_explanation"],
                        provenance_experiment_ids=json.loads(conc_row["provenance_experiment_ids"]) if conc_row["provenance_experiment_ids"] else [],
                        created_at=datetime.fromisoformat(conc_row["created_at"])
                    )
                    decision = latest_conc.decision_state
                    confidence = latest_conc.confidence_state
                    action = latest_conc.next_research_action
                    last_updated_at = latest_conc.created_at
                
                # 4. Unresolved Conflicts
                cursor.execute("SELECT * FROM research_conflicts WHERE identity_hash = ? AND resolution_status = 'UNRESOLVED'", (identity_hash,))
                conflicts = []
                for cr in cursor.fetchall():
                    conflicts.append(ResearchConflict(**dict(cr)))
                    
                # 5. Open Gaps
                cursor.execute("SELECT * FROM research_evidence_gaps WHERE identity_hash = ? AND status = 'OPEN'", (identity_hash,))
                gaps = []
                for gr in cursor.fetchall():
                    gaps.append(EvidenceGap(**dict(gr)))
                    
                # 6. Relationships (Bounded depth=1)
                cursor.execute("SELECT * FROM research_relationships WHERE source_id = ? OR target_id = ? LIMIT 100", (identity_hash, identity_hash))
                rels = []
                for rr in cursor.fetchall():
                    rels.append(ResearchRelationship(**dict(rr)))

                return ResearchKnowledgeSnapshot(
                    identity_hash=identity_hash,
                    canonical_hypothesis=canonical_hypothesis,
                    affected_symbols=affected_symbols,
                    mapped_strategy=mapped_strategy,
                    total_experiments=total_experiments,
                    total_completed_jobs=total_completed,
                    current_decision_state=decision,
                    current_confidence_state=confidence,
                    next_research_action=action,
                    latest_conclusion=latest_conc,
                    unresolved_conflicts=conflicts,
                    open_evidence_gaps=gaps,
                    related_identities=rels,
                    first_seen_at=first_seen_at,
                    last_updated_at=last_updated_at
                )
        except Exception as e:
            logger.error("Failed to build snapshot for %s: %s", identity_hash, e)
            return None

    def record_knowledge_change(self, change: ResearchKnowledgeChange):
        """Immutably record a state transition in the knowledge graph."""
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT INTO research_knowledge_changes 
                    (change_id, identity_hash, change_type, previous_decision, new_decision, 
                     previous_confidence, new_confidence, reason, source_reference_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    change.change_id, change.identity_hash, change.change_type.value,
                    change.previous_decision.value if change.previous_decision else None,
                    change.new_decision.value if change.new_decision else None,
                    change.previous_confidence.value if change.previous_confidence else None,
                    change.new_confidence.value if change.new_confidence else None,
                    change.reason, change.source_reference_id, change.created_at.isoformat()
                ))
            telemetry.record_stage("KNOWLEDGE_CHANGE_RECORDED")
        except Exception as e:
            logger.error("Failed to record knowledge change: %s", e)
            
    def record_evidence_gap(self, gap: EvidenceGap):
        """Record a missing requirement for research robustness."""
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                # Upsert or ignore if identical open gap exists
                cursor = conn.cursor()
                cursor.execute("SELECT gap_id FROM research_evidence_gaps WHERE identity_hash=? AND gap_type=? AND status='OPEN'", 
                              (gap.identity_hash, gap.gap_type.value))
                if cursor.fetchone():
                    return # Already tracked
                    
                conn.execute("""
                    INSERT INTO research_evidence_gaps 
                    (gap_id, identity_hash, gap_type, severity, status, recommended_action, created_at, resolved_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    gap.gap_id, gap.identity_hash, gap.gap_type.value, gap.severity, 
                    gap.status.value, gap.recommended_action.value, gap.created_at.isoformat(),
                    gap.resolved_at.isoformat() if gap.resolved_at else None
                ))
            telemetry.record_stage("EVIDENCE_GAP_RECORDED")
        except Exception as e:
            logger.error("Failed to record evidence gap: %s", e)

    def on_new_conclusion_generated(self, conclusion: ResearchConclusion):
        """Event hook to detect state changes and emit gaps/change events."""
        # What was the previous conclusion?
        prev_decision = None
        prev_confidence = None
        
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                # Get the conclusion before this one
                cursor.execute("SELECT decision_state, confidence_state FROM research_conclusions WHERE identity_hash = ? AND conclusion_id != ? ORDER BY created_at DESC LIMIT 1", 
                              (conclusion.identity_hash, conclusion.conclusion_id))
                row = cursor.fetchone()
                if row:
                    prev_decision = ResearchDecisionState(row[0])
                    prev_confidence = ResearchConfidenceState(row[1])
        except Exception:
            pass

        # If changed, emit Knowledge Change
        if prev_decision != conclusion.decision_state or prev_confidence != conclusion.confidence_state:
            change = ResearchKnowledgeChange(
                change_id=str(uuid.uuid4()),
                identity_hash=conclusion.identity_hash,
                change_type=KnowledgeChangeType.CONCLUSION_CHANGED,
                previous_decision=prev_decision,
                new_decision=conclusion.decision_state,
                previous_confidence=prev_confidence,
                new_confidence=conclusion.confidence_state,
                reason="New research evidence evaluated",
                source_reference_id=conclusion.conclusion_id
            )
            self.record_knowledge_change(change)
            
        # Emit gaps based on action
        if conclusion.next_research_action == NextResearchAction.VALIDATE_WALK_FORWARD:
            self.record_evidence_gap(EvidenceGap(
                gap_id=str(uuid.uuid4()),
                identity_hash=conclusion.identity_hash,
                gap_type=EvidenceGapType.MISSING_WALK_FORWARD,
                severity="HIGH",
                recommended_action=NextResearchAction.VALIDATE_WALK_FORWARD
            ))
        elif conclusion.next_research_action == NextResearchAction.TEST_ANOTHER_REGIME:
            self.record_evidence_gap(EvidenceGap(
                gap_id=str(uuid.uuid4()),
                identity_hash=conclusion.identity_hash,
                gap_type=EvidenceGapType.MISSING_REGIME_COVERAGE,
                severity="MEDIUM",
                recommended_action=NextResearchAction.TEST_ANOTHER_REGIME
            ))
