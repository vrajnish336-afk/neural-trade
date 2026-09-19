import uuid
from datetime import datetime, timezone
from typing import List, Optional
import hashlib
from app.research.evidence_graph.repository import EvidenceGraphRepository
from app.research.evidence_graph.queries import GraphQueries
from app.research.evidence_graph.models import NodeType
from app.research.planner.repository import PlannerRepository
from app.research.planner.models import ResearchQuestionCandidate, ResearchDecision, ResearchAction, ResearchDecisionState
from app.research.planner.scoring import ScoringEngine

class ResearchDecisionPlanner:
    def __init__(self, max_queue_size: int = 50):
        self.repo = PlannerRepository()
        self.graph_repo = EvidenceGraphRepository()
        self.graph_queries = GraphQueries()
        self.scoring_engine = ScoringEngine()
        self.max_queue_size = max_queue_size

    def generate_plan(self, as_of: Optional[datetime] = None) -> List[ResearchDecision]:
        """Scans the evidence graph for unaddressed gaps/conflicts and ranks them."""
        
        if as_of is None:
            as_of = datetime.now(timezone.utc)
            
        # 1. Find all GAPs in the graph up to as_of
        gap_nodes = [n for n in self.graph_repo.get_nodes(as_of=as_of) if n.node_type == NodeType.EVIDENCE_GAP]
        
        decisions = []
        for gap in gap_nodes:
            identity = gap.identity_hash or self._deterministic_hash(gap.node_id)
            q_id = self._deterministic_hash(f"q_{gap.node_id}")
            
            # Check if this exact gap has a recently approved active decision
            existing_dec = self.repo.get_decision(self._deterministic_hash(f"dec_{q_id}"))
            if existing_dec:
                if existing_dec.status in [ResearchDecisionState.APPROVED_FOR_RESEARCH, ResearchDecisionState.QUEUED, ResearchDecisionState.COMPLETED]:
                    continue
                if existing_dec.status == ResearchDecisionState.REVIEW_REQUIRED:
                    decisions.append(existing_dec)
                    continue
                
            # Pull Evidence Graph Context
            related_nodes = self.graph_queries.get_supporting_evidence(gap.node_id, as_of=as_of) + self.graph_queries.get_contradicting_evidence(gap.node_id, as_of=as_of)
            
            # Save candidate
            candidate = ResearchQuestionCandidate(
                question_id=q_id,
                research_identity=identity,
                research_question=f"Resolve evidence gap: {gap.metadata.get('gap_type', 'Unknown')}",
                originating_gap=gap.node_id,
                created_at=as_of,
                as_of=as_of,
                status=ResearchDecisionState.DISCOVERED
            )
            self.repo.save_candidate(candidate)
            
            # Score
            breakdown = self.scoring_engine.score_candidate(gap, related_nodes, as_of)
            action = self.scoring_engine.determine_action(breakdown, gap)
            
            status = ResearchDecisionState.REVIEW_REQUIRED if action in [ResearchAction.RESEARCH_NOW, ResearchAction.RESOLVE_CONFLICT, ResearchAction.RESEARCH_LATER] else ResearchDecisionState.ANALYZED
            if action == ResearchAction.COLLECT_DATA:
                status = ResearchDecisionState.DATA_NOT_AVAILABLE
            
            # Create Decision
            dec = ResearchDecision(
                decision_id=self._deterministic_hash(f"dec_{candidate.question_id}"),
                research_question_id=candidate.question_id,
                recommended_action=action,
                priority=breakdown.final_score,
                priority_breakdown=breakdown,
                feasibility=gap.metadata.get("feasibility", "FEASIBLE"),
                expected_information_value=breakdown.expected_information_value_heuristic,
                rationale=breakdown.explanation,
                status=status,
                created_at=as_of,
                as_of=as_of
            )
            
            self.repo.save_decision(dec)
            decisions.append(dec)
            
        # Sort by priority
        decisions.sort(key=lambda x: x.priority, reverse=True)
        
        # Enforce max queue size
        return decisions[:self.max_queue_size]

    def approve_decision(self, decision_id: str) -> bool:
        dec = self.repo.get_decision(decision_id)
        if dec and dec.status == ResearchDecisionState.REVIEW_REQUIRED:
            dec.status = ResearchDecisionState.APPROVED_FOR_RESEARCH
            dec.approval_timestamp = datetime.now(timezone.utc)
            self.repo.save_decision(dec)
            return True
        return False

    def _deterministic_hash(self, val: str) -> str:
        return hashlib.sha256(val.encode('utf-8')).hexdigest()[:16]
