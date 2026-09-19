import hashlib
from datetime import datetime, timezone
from typing import List, Optional, Set
from app.research.evidence_graph.models import NodeType
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.synthesis.repository import SynthesisRepository
from app.research.revalidation.repository import RevalidationRepository
from app.research.revalidation.models import RevalidationAssessmentState, EvidenceStrengthLevel
from app.research.knowledge_intelligence.models import (
    ResearchKnowledgeClaim, KnowledgeState, KnowledgeScope, KnowledgePattern, PatternFamily, KnowledgeGap
)
from app.research.consensus.normalizer import EvidenceNormalizer

class KnowledgeSynthesizer:
    def __init__(self):
        self.graph_repo = EvidenceGraphRepository()
        self.syn_repo = SynthesisRepository()
        self.rev_repo = RevalidationRepository()
        self.normalizer = EvidenceNormalizer(self.graph_repo)

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]

    def synthesize_knowledge(self, research_identity: str, as_of: datetime) -> Optional[ResearchKnowledgeClaim]:
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # 1. Fetch Phase 33 Synthesis
        # In a real setup, we'd query by research_identity and as_of
        # Here we mock finding the latest synthesis
        syns = [s for s in self.syn_repo.get_all_syntheses() if s.research_identity == research_identity and s.as_of <= as_of_utc]
        if not syns:
            return None
        latest_syn = max(syns, key=lambda x: x.as_of)

        # 2. Fetch Phase 50 Revalidation Assessment
        revs = [r for r in self.rev_repo.get_all_results() if r.research_identity == research_identity and r.as_of <= as_of_utc]
        latest_rev = max(revs, key=lambda x: x.as_of) if revs else None

        # 3. Normalize Evidence
        normalized_units = self.normalizer.normalize(research_identity, as_of_utc)
        independent_count = sum(1 for u in normalized_units if u.is_independent)
        
        # Scopes
        datasets = list(set(u.dataset_id for u in normalized_units if u.dataset_id))
        regimes = list(set(u.regime for u in normalized_units if u.regime))
        methods = list(set(u.methodology_version for u in normalized_units if u.methodology_version))
        costs = list(set(u.cost_assumption for u in normalized_units if u.cost_assumption))

        # 4. Determine Knowledge State
        state = KnowledgeState.INSUFFICIENT_EVIDENCE
        if latest_rev:
            if latest_rev.assessment_state == RevalidationAssessmentState.REVALIDATION_CONFIRMS_ORIGINAL:
                state = KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY if independent_count >= 3 else KnowledgeState.SUPPORTED
            elif latest_rev.assessment_state == RevalidationAssessmentState.REVALIDATION_WEAKENS_ORIGINAL:
                state = KnowledgeState.WEAKENED
            elif latest_rev.assessment_state == RevalidationAssessmentState.REVALIDATION_CONFLICTS_WITH_ORIGINAL:
                state = KnowledgeState.CONFLICTED
            elif latest_rev.assessment_state == RevalidationAssessmentState.REVALIDATION_INCONCLUSIVE:
                state = KnowledgeState.INCONCLUSIVE
        else:
            # Fallback to Phase 33 confidence state
            fallback_map = {
                "INSUFFICIENT_EVIDENCE": KnowledgeState.INSUFFICIENT_EVIDENCE,
                "EMERGING": KnowledgeState.CONDITIONALLY_SUPPORTED,
                "PARTIALLY_SUPPORTED": KnowledgeState.CONDITIONALLY_SUPPORTED,
                "SUPPORTED": KnowledgeState.SUPPORTED,
                "CONFLICTED": KnowledgeState.CONFLICTED,
                "WEAKENED": KnowledgeState.WEAKENED,
                "STALE": KnowledgeState.STALE,
                "REQUIRES_REVALIDATION": KnowledgeState.REQUIRES_REVALIDATION
            }
            state = fallback_map.get(latest_syn.confidence_state.value, KnowledgeState.INSUFFICIENT_EVIDENCE)

        # 5. Determine Canonical Statement
        if state in [KnowledgeState.ESTABLISHED_WITHIN_BOUNDARY, KnowledgeState.SUPPORTED, KnowledgeState.CONDITIONALLY_SUPPORTED]:
            stmt = f"Within the tested datasets, regime boundaries, methodology and historical period, structural support was observed for {research_identity}."
        elif state == KnowledgeState.WEAKENED:
            stmt = f"Structural support for {research_identity} was observed but weakened by revalidation or conflicting evidence."
        elif state == KnowledgeState.CONFLICTED:
            stmt = f"Evidence for {research_identity} is conflicting and unresolved."
        else:
            stmt = f"Evidence for {research_identity} is currently insufficient or inconclusive."

        claim_id = self._deterministic_hash(f"claim_{research_identity}_{state.value}_{as_of_utc.timestamp()}")
        
        strength = latest_rev.current_evidence_strength.value if latest_rev else EvidenceStrengthLevel.INSUFFICIENT.value

        return ResearchKnowledgeClaim(
            claim_id=claim_id,
            canonical_statement=stmt,
            knowledge_state=state,
            scope=KnowledgeScope(
                dataset_scope=datasets,
                regime_scope=regimes,
                methodology_scope=methods,
                cost_scope=costs
            ),
            evidence_ids=[u.evidence_id for u in normalized_units],
            supporting_evidence_ids=latest_syn.supporting_evidence,
            contradicting_evidence_ids=latest_syn.contradictory_evidence,
            independent_evidence_count=independent_count,
            evidence_strength=strength,
            as_of=as_of_utc,
            created_at=datetime.now(timezone.utc)
        )

    def extract_patterns(self, claims: List[ResearchKnowledgeClaim], as_of: datetime) -> List[KnowledgePattern]:
        """Detect recurring structural patterns across multiple claims."""
        patterns = []
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # Bounded Pattern: DATASET SENSITIVITY
        # Detect if a specific dataset scope consistently results in WEAKENED or CONFLICTED state
        dataset_fail_counts = {}
        dataset_ev_counts = {}
        for c in claims:
            if c.as_of > as_of_utc:
                continue
            for ds in c.scope.dataset_scope:
                dataset_ev_counts[ds] = dataset_ev_counts.get(ds, 0) + len(c.supporting_evidence_ids) + len(c.contradicting_evidence_ids)
                if c.knowledge_state in [KnowledgeState.WEAKENED, KnowledgeState.CONFLICTED, KnowledgeState.INCONCLUSIVE]:
                    dataset_fail_counts[ds] = dataset_fail_counts.get(ds, 0) + 1

        for ds, fails in dataset_fail_counts.items():
            if fails >= 3: # Arbitrary threshold for recurrence
                pid = self._deterministic_hash(f"pat_dataset_{ds}_{as_of_utc.timestamp()}")
                patterns.append(KnowledgePattern(
                    pattern_id=pid,
                    pattern_family=PatternFamily.DATASET,
                    description=f"Recurring discrepancy/conflict observed frequently on dataset: {ds}",
                    independent_evidence_count=fails,
                    supporting_evidence_units=0,
                    contradicting_evidence_units=dataset_ev_counts.get(ds, 0),
                    datasets_involved=[ds],
                    as_of=as_of_utc,
                    created_at=datetime.now(timezone.utc)
                ))
                
        # Could add more bounded pattern families here (Regime, Methodology)
        return patterns

    def generate_research_gaps(self, claims: List[ResearchKnowledgeClaim], patterns: List[KnowledgePattern], as_of: datetime) -> List[KnowledgeGap]:
        gaps = []
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        for c in claims:
            if c.as_of > as_of_utc:
                continue
            if c.knowledge_state == KnowledgeState.INCONCLUSIVE:
                gid = self._deterministic_hash(f"gap_inconclusive_{c.claim_id}")
                gaps.append(KnowledgeGap(
                    gap_id=gid,
                    claim_id=c.claim_id,
                    description="Evidence remains inconclusive after discrepancy isolation. Further independent data required.",
                    reason="Phase 50 Revalidation yielded INCONCLUSIVE.",
                    required_evidence_type="INDEPENDENT_DATASET_TEST",
                    as_of=as_of_utc,
                    created_at=datetime.now(timezone.utc)
                ))
                
        for p in patterns:
            gid = self._deterministic_hash(f"gap_pattern_{p.pattern_id}")
            gaps.append(KnowledgeGap(
                gap_id=gid,
                description=f"Pattern '{p.pattern_family.value}' suggests structural sensitivity. Is this conditionally reproducible?",
                reason=f"Recurring pattern detected: {p.description}",
                required_evidence_type="CONTROLLED_ISOLATION_TEST",
                as_of=as_of_utc,
                created_at=datetime.now(timezone.utc)
            ))
            
        return gaps
