from typing import List, Optional
from datetime import datetime, timedelta, timezone
from app.research.evidence_graph.models import EvidenceNode, NodeType, EvidenceEdge, EdgeRelationship
from app.research.planner.models import ResearchPriorityBreakdown, ResearchAction

class ScoringEngine:
    def __init__(self):
        pass

    def score_candidate(self, candidate_gap_node: EvidenceNode, related_nodes: List[EvidenceNode], as_of: Optional[datetime] = None) -> ResearchPriorityBreakdown:
        breakdown = ResearchPriorityBreakdown()
        
        if not as_of:
            as_of = datetime.now(timezone.utc)
            
        # 1. Gap weight
        gap_type = candidate_gap_node.metadata.get("gap_type", "")
        if "sample" in gap_type.lower() or "size" in gap_type.lower():
            breakdown.evidence_gap_weight = 3.0
            breakdown.explanation += "Significant sample size deficiency detected. "
        elif "robustness" in gap_type.lower():
            breakdown.evidence_gap_weight = 2.0
            breakdown.explanation += "Robustness validation gap detected. "
        else:
            breakdown.evidence_gap_weight = 1.0
            breakdown.explanation += "General evidence gap. "
            
        # 2. Conflict weight
        conflict_count = len([n for n in related_nodes if n.node_type == NodeType.EXPERIMENT_COMPARISON and n.metadata.get("status") == "NOT_SUPPORTED"])
        if conflict_count > 0:
            breakdown.conflict_weight = 2.5 * conflict_count
            breakdown.explanation += f"Found {conflict_count} contradictory findings requiring resolution. "
            
        # 3. Saturation penalty
        experiment_count = len([n for n in related_nodes if n.node_type == NodeType.EXPERIMENT])
        if experiment_count > 5:
            breakdown.evidence_saturation_penalty = (experiment_count - 5) * 1.0
            breakdown.explanation += f"Area heavily researched ({experiment_count} prior experiments). Applying saturation penalty. "
            
        # 4. Uncertainty weight
        if experiment_count == 0:
            breakdown.uncertainty_weight = 2.0
            breakdown.explanation += "High uncertainty due to lack of prior experiments. "
            
        # 5. Staleness (knowledge staleness)
        oldest_exp = None
        for n in related_nodes:
            if n.node_type == NodeType.EXPERIMENT:
                if not oldest_exp or n.created_at < oldest_exp:
                    oldest_exp = n.created_at
                    
        if oldest_exp and (as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of) > (oldest_exp.replace(tzinfo=timezone.utc) if oldest_exp.tzinfo is None else oldest_exp) + timedelta(days=90):
            breakdown.novelty_weight = 1.5
            breakdown.explanation += "Existing evidence is stale (>90 days old). "
            
        # Feasibility check
        feasibility = candidate_gap_node.metadata.get("feasibility", "FEASIBLE")
        if feasibility == "DATA_NOT_AVAILABLE":
            breakdown.feasibility_weight = -10.0
            breakdown.explanation += "Data not available. "

        # Heuristic Expected Information Value
        breakdown.expected_information_value_heuristic = max(0.0, 
            breakdown.evidence_gap_weight 
            + breakdown.conflict_weight 
            + breakdown.uncertainty_weight
            + breakdown.novelty_weight
            - breakdown.evidence_saturation_penalty
            + breakdown.feasibility_weight
        )
        
        breakdown.final_score = breakdown.expected_information_value_heuristic
        
        if breakdown.final_score <= 0.5:
            breakdown.explanation += "Low expected information gain."
            
        return breakdown

    def determine_action(self, breakdown: ResearchPriorityBreakdown, gap_node: EvidenceNode) -> ResearchAction:
        feasibility = gap_node.metadata.get("feasibility", "FEASIBLE")
        if feasibility == "DATA_NOT_AVAILABLE":
            return ResearchAction.COLLECT_DATA
            
        if breakdown.final_score >= 3.0:
            if breakdown.conflict_weight > 0:
                return ResearchAction.RESOLVE_CONFLICT
            return ResearchAction.RESEARCH_NOW
        elif breakdown.final_score > 0.5:
            return ResearchAction.RESEARCH_LATER
        elif breakdown.evidence_saturation_penalty > 2.0:
            return ResearchAction.ALREADY_RESEARCHED
        else:
            return ResearchAction.NO_ACTION
