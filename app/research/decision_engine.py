import uuid
import json
import sqlite3
import logging
from typing import List, Optional, Dict, Tuple
from datetime import datetime

from app.config import config
from app.database.schema import init_db
from app.research.decision_models import (
    ResearchConfidenceState, ResearchDecisionState, NextResearchAction,
    ResearchConflict, ResearchRelationship, RelationshipType, ResearchConclusion
)
from app.research.evidence import ResearchEvidenceEvaluator, EvidenceSummary, EvidenceStatus, EvidenceConclusion
from app.research.comparator import CrossExperimentComparator, ComparabilityStatus
from app.research.models import ResearchExperiment
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class ResearchDecisionEngine:
    """Aggregates multiple experiments for a given Research Identity into a definitive Conclusion."""
    
    def __init__(self):
        pass
        
    def _get_conn(self):
        return sqlite3.connect(config.DB_PATH)

    def evaluate_identity(self, identity_hash: str) -> Optional[ResearchConclusion]:
        telemetry.record_stage("EVIDENCE_AGGREGATION_STARTED")
        
        # 1. Fetch all completed jobs/experiments for this identity
        experiments = self._fetch_experiments(identity_hash)
        if not experiments:
            return None
            
        # 2. Evaluate Evidence for each
        evidence_summaries: Dict[str, EvidenceSummary] = {}
        for exp in experiments:
            evidence_summaries[exp.experiment_id] = ResearchEvidenceEvaluator.evaluate(exp)
            
        # 3. Detect Conflicts (Compare all pairs)
        conflicts = self._detect_conflicts(identity_hash, experiments, evidence_summaries)
        
        # 4. Synthesize Decision & Confidence
        decision_state, confidence_state, next_action, limitations, summary = self._synthesize(evidence_summaries, conflicts)
        
        # 5. Create Conclusion
        conclusion = ResearchConclusion(
            conclusion_id=str(uuid.uuid4()),
            identity_hash=identity_hash,
            decision_state=decision_state,
            confidence_state=confidence_state,
            summary=summary,
            supporting_evidence_count=sum(1 for e in evidence_summaries.values() if e.status == EvidenceStatus.STRONG),
            conflicting_evidence_count=len(conflicts),
            limitations=list(set(limitations)),
            next_research_action=next_action,
            provenance_experiment_ids=[e.experiment_id for e in experiments]
        )
        
        # 6. Persist
        self._save_conclusion(conclusion)
        for conflict in conflicts:
            self._save_conflict(conflict)
            
        # 7. Update Knowledge Graph
        try:
            # Avoid circular import
            from app.research.knowledge_service import ResearchKnowledgeService
            ks = ResearchKnowledgeService()
            ks.on_new_conclusion_generated(conclusion)
        except Exception as e:
            logger.error("Failed to notify knowledge service: %s", e)
            
        telemetry.record_stage("CONCLUSION_CREATED")
        return conclusion
        
    def _fetch_experiments(self, identity_hash: str) -> List[ResearchExperiment]:
        experiments = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT result_experiment_id FROM research_jobs 
                    WHERE identity_hash = ? AND state = 'SUCCEEDED' AND result_experiment_id IS NOT NULL
                """, (identity_hash,))
                exp_ids = [r[0] for r in cursor.fetchall()]
                
                for eid in exp_ids:
                    cursor.execute("SELECT experiment_json FROM research_experiments WHERE id = ?", (eid,))
                    row = cursor.fetchone()
                    if row:
                        import json
                        exp_dict = json.loads(row[0])
                        experiments.append(ResearchExperiment(**exp_dict))
        except Exception as e:
            logger.error("Failed to fetch experiments for identity %s: %s", identity_hash, e)
        return experiments

    def _detect_conflicts(self, identity_hash: str, experiments: List[ResearchExperiment], evidence: Dict[str, EvidenceSummary]) -> List[ResearchConflict]:
        conflicts = []
        # O(N^2) comparison, but N is typically very small (<5) per identity.
        for i in range(len(experiments)):
            for j in range(i+1, len(experiments)):
                exp1 = experiments[i]
                exp2 = experiments[j]
                
                # Use Phase 8 Comparator
                report = CrossExperimentComparator.compare(exp1, exp2)
                
                if report.comparability in [ComparabilityStatus.COMPARABLE, ComparabilityStatus.LIMITED_COMPARABILITY]:
                    ev1 = evidence[exp1.experiment_id]
                    ev2 = evidence[exp2.experiment_id]
                    
                    # Direct Contradiction: One is positive (VERIFIED or LIMITED), one is negative (WEAKNESS)
                    positive_conclusions = [EvidenceConclusion.VERIFIED_RESULT, EvidenceConclusion.RESEARCH_LIMITATION]
                    negative_conclusions = [EvidenceConclusion.STRATEGY_MODEL_WEAKNESS]
                    
                    if ev1.conclusion in positive_conclusions and ev2.conclusion in negative_conclusions:
                        conflicts.append(ResearchConflict(
                            conflict_id=str(uuid.uuid4()),
                            identity_hash=identity_hash,
                            experiment_id_1=exp1.experiment_id,
                            experiment_id_2=exp2.experiment_id,
                            conflict_type="OOS_CONTRADICTION",
                            severity="HIGH",
                            explanation=f"Exp1 verified result but Exp2 showed weakness despite comparable setup. Diff: {', '.join(report.differences)}"
                        ))
                    elif ev2.conclusion in positive_conclusions and ev1.conclusion in negative_conclusions:
                        conflicts.append(ResearchConflict(
                            conflict_id=str(uuid.uuid4()),
                            identity_hash=identity_hash,
                            experiment_id_1=exp1.experiment_id,
                            experiment_id_2=exp2.experiment_id,
                            conflict_type="OOS_CONTRADICTION",
                            severity="HIGH",
                            explanation=f"Exp2 verified result but Exp1 showed weakness despite comparable setup. Diff: {', '.join(report.differences)}"
                        ))
        if conflicts:
            telemetry.record_stage("CONTRADICTION_DETECTED")
        return conflicts

    def _synthesize(self, evidence: Dict[str, EvidenceSummary], conflicts: List[ResearchConflict]) -> Tuple[ResearchDecisionState, ResearchConfidenceState, NextResearchAction, List[str], str]:
        all_limitations = []
        has_software_issue = False
        has_insufficient = False
        has_weak = False
        has_strong = False
        has_moderate = False
        
        for ev in evidence.values():
            all_limitations.extend(ev.limitations)
            if ev.conclusion == EvidenceConclusion.SOFTWARE_ACCOUNTING_ISSUE:
                has_software_issue = True
            elif ev.conclusion == EvidenceConclusion.INSUFFICIENT_EVIDENCE:
                has_insufficient = True
            elif ev.status == EvidenceStatus.WEAK:
                has_weak = True
            elif ev.status == EvidenceStatus.MODERATE:
                has_moderate = True
            elif ev.status == EvidenceStatus.STRONG:
                has_strong = True
                
        # Base Decision
        if has_software_issue:
            decision = ResearchDecisionState.SOFTWARE_OR_ACCOUNTING_ISSUE
            confidence = ResearchConfidenceState.LOW
            action = NextResearchAction.INVESTIGATE_ACCOUNTING
            summary = "Research blocked by a software validation or accounting inconsistency."
            
        elif len(conflicts) > 0:
            decision = ResearchDecisionState.CONTRADICTORY_EVIDENCE
            confidence = ResearchConfidenceState.UNRESOLVED
            action = NextResearchAction.INSPECT_CONFLICTING_EXPERIMENTS
            summary = "Research yielded contradictory results across highly comparable experiments."
            
        elif (has_strong or has_moderate) and has_weak:
            decision = ResearchDecisionState.MIXED_EVIDENCE
            confidence = ResearchConfidenceState.LOW
            action = NextResearchAction.EVALUATE_ANOTHER_SEED
            summary = "Research yielded mixed evidence across different experiments."
            
        elif has_strong and not has_weak and not has_insufficient:
            decision = ResearchDecisionState.RESEARCH_RESULT_SUPPORTED
            confidence = ResearchConfidenceState.MODERATE
            action = NextResearchAction.VALIDATE_WALK_FORWARD
            summary = "Evidence strongly supports the hypothesis, pending further robustness checks."
            # Upgrade confidence if many experiments verify it
            if sum(1 for e in evidence.values() if e.status == EvidenceStatus.STRONG) >= 3:
                confidence = ResearchConfidenceState.HIGH
                action = NextResearchAction.NONE_REQUIRED
                
        elif has_moderate and not has_weak and not has_insufficient:
            decision = ResearchDecisionState.SUPPORTED_FOR_FURTHER_RESEARCH
            confidence = ResearchConfidenceState.MODERATE
            action = NextResearchAction.VALIDATE_WALK_FORWARD
            summary = "Evidence supports the hypothesis, but suffers from research limitations (e.g. missing walk-forward)."
                
        elif has_weak and not has_strong and not has_moderate:
            decision = ResearchDecisionState.RESEARCH_LIMITED
            confidence = ResearchConfidenceState.MODERATE
            action = NextResearchAction.TEST_ANOTHER_REGIME
            summary = "Evidence robustly does not support the hypothesis in the tested configurations."
            
        else: # Insufficient
            decision = ResearchDecisionState.INSUFFICIENT_EVIDENCE
            confidence = ResearchConfidenceState.LOW
            action = NextResearchAction.COLLECT_MORE_DATA
            summary = "Insufficient data or observations to form a conclusion."

        return decision, confidence, action, all_limitations, summary

    def _save_conclusion(self, conc: ResearchConclusion):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_conclusions
                    (conclusion_id, identity_hash, decision_state, confidence_state, summary,
                     supporting_evidence_count, conflicting_evidence_count, limitations,
                     next_research_action, ai_explanation, provenance_experiment_ids, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conc.conclusion_id, conc.identity_hash, conc.decision_state.value,
                    conc.confidence_state.value, conc.summary, conc.supporting_evidence_count,
                    conc.conflicting_evidence_count, json.dumps(conc.limitations),
                    conc.next_research_action.value, conc.ai_explanation,
                    json.dumps(conc.provenance_experiment_ids), conc.created_at.isoformat()
                ))
        except Exception as e:
            logger.error("Failed to save conclusion: %s", e)

    def _save_conflict(self, conf: ResearchConflict):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR IGNORE INTO research_conflicts
                    (conflict_id, identity_hash, experiment_id_1, experiment_id_2,
                     conflict_type, severity, explanation, resolution_status, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    conf.conflict_id, conf.identity_hash, conf.experiment_id_1, conf.experiment_id_2,
                    conf.conflict_type, conf.severity, conf.explanation, conf.resolution_status,
                    conf.created_at.isoformat()
                ))
        except Exception as e:
            logger.error("Failed to save conflict: %s", e)

    def add_relationship(self, rel: ResearchRelationship):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                # Check for duplicate
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM research_relationships WHERE source_id=? AND target_id=? AND relationship_type=?",
                              (rel.source_id, rel.target_id, rel.relationship_type.value))
                if cursor.fetchone():
                    return
                conn.execute("""
                    INSERT INTO research_relationships (source_id, target_id, relationship_type, description)
                    VALUES (?, ?, ?, ?)
                """, (rel.source_id, rel.target_id, rel.relationship_type.value, rel.description))
                telemetry.record_stage("RELATIONSHIP_CREATED")
        except Exception as e:
            logger.error("Failed to save relationship: %s", e)
