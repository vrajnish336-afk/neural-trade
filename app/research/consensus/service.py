import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, List
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.hypothesis_validation.models import HypothesisValidationResult, FalsificationState
from app.research.replication.models import ResearchReplicationResult
from app.research.revalidation.models import RevalidationAssessment, DecayState

from app.research.consensus.models import ConsensusAssessment, ConsensusState, ConsensusConflict, ConflictType, ConflictSeverity, ResolutionState
from app.research.consensus.repository import ConsensusRepository
from app.research.consensus.normalizer import EvidenceNormalizer
from app.research.consensus.resolver import ConflictResolver

logger = logging.getLogger(__name__)

class ConsensusService:
    def __init__(self):
        self.repo = ConsensusRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.normalizer = EvidenceNormalizer(self.graph_repo)
        self.resolver = ConflictResolver()

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def evaluate(self, hypothesis_id: str, identity_hash: str, validation: HypothesisValidationResult, replication: Optional[ResearchReplicationResult] = None, revalidation: Optional[RevalidationAssessment] = None, as_of: Optional[datetime] = None) -> ConsensusAssessment:
        if not as_of:
            as_of = datetime.now(timezone.utc)
        as_of = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # 1. Normalize Evidence
        units = self.normalizer.normalize(identity_hash, as_of, replication)
        
        support_units = [u for u in units if u.support_or_contradiction == "SUPPORTS"]
        contradict_units = [u for u in units if u.support_or_contradiction == "CONTRADICTS"]
        
        s_count = sum(1 for u in support_units if u.is_independent)
        c_count = sum(1 for u in contradict_units if u.is_independent)
        
        # 2. Extract Warnings
        falsification_triggered = (validation.falsification_triggered == FalsificationState.TRIGGERED)
        multiple_testing_risk = replication.replication.multiple_testing_risk if replication else False
        evidence_health_warning = (revalidation.decay_state == DecayState.STALE) if revalidation else False
        
        # 3. Handle Absolute Falsification
        if falsification_triggered:
            conflicts = [ConsensusConflict(
                conflict_type=ConflictType.FALSIFICATION_CONFLICT,
                severity=ConflictSeverity.CRITICAL,
                resolution=ResolutionState.RESOLVED_BY_FALSIFICATION,
                description="Phase 34 falsification engine forcefully rejected this hypothesis."
            )]
            res = ConsensusAssessment(
                assessment_id=self._deterministic_hash(f"con_{hypothesis_id}_{as_of.timestamp()}"),
                hypothesis_id=hypothesis_id, research_identity=identity_hash,
                state=ConsensusState.CONFLICTED,
                independent_support_count=s_count, independent_contradict_count=c_count,
                conflicts=conflicts, falsification_triggered=True,
                explanation="Falsification condition triggered. State locked to CONFLICTED.",
                as_of=as_of, created_at=datetime.now(timezone.utc)
            )
            self.repo.save_result(res)
            return res

        # 4. Handle Insufficient
        if s_count == 0 and c_count == 0:
            res = ConsensusAssessment(
                assessment_id=self._deterministic_hash(f"con_{hypothesis_id}_{as_of.timestamp()}"),
                hypothesis_id=hypothesis_id, research_identity=identity_hash,
                state=ConsensusState.INSUFFICIENT_EVIDENCE,
                falsification_triggered=falsification_triggered, multiple_testing_risk=multiple_testing_risk,
                evidence_health_warning=evidence_health_warning,
                explanation="No independent evidence found before the as_of bound.",
                as_of=as_of, created_at=datetime.now(timezone.utc)
            )
            self.repo.save_result(res)
            return res
            
        # 5. Resolve Conflicts
        conflicts, conditions = self.resolver.evaluate_conflicts(support_units, contradict_units)
        
        # 6. Determine State
        state = ConsensusState.UNRESOLVED
        
        if c_count == 0 and s_count > 0:
            state = ConsensusState.CONSENSUS_SUPPORTED
        elif s_count == 0 and c_count > 0:
            state = ConsensusState.CONFLICTED
        elif s_count > 0 and c_count > 0:
            # We have a mix. Let's look at the resolutions.
            unresolved = [c for c in conflicts if c.resolution == ResolutionState.UNRESOLVED]
            conditionally_resolved = [c for c in conflicts if c.resolution == ResolutionState.RESOLVED_BY_CONDITION]
            
            if unresolved:
                state = ConsensusState.CONFLICTED
            elif conditionally_resolved:
                state = ConsensusState.CONDITIONAL_CONSENSUS
            else:
                state = ConsensusState.PARTIAL_CONSENSUS

        research_gaps = []
        if state in [ConsensusState.CONFLICTED, ConsensusState.UNRESOLVED]:
            research_gaps.append("Need unseen-data replication to resolve direct contradiction.")
            
        res = ConsensusAssessment(
            assessment_id=self._deterministic_hash(f"con_{hypothesis_id}_{as_of.timestamp()}"),
            hypothesis_id=hypothesis_id, research_identity=identity_hash,
            state=state,
            independent_support_count=s_count, independent_contradict_count=c_count,
            conditional_conditions=conditions, conflicts=conflicts,
            evidence_health_warning=evidence_health_warning,
            falsification_triggered=falsification_triggered,
            multiple_testing_risk=multiple_testing_risk,
            explanation=f"State reached: {state.value} (Support: {s_count}, Contradict: {c_count})",
            research_gaps=research_gaps,
            as_of=as_of, created_at=datetime.now(timezone.utc)
        )
        self.repo.save_result(res)
        return res
