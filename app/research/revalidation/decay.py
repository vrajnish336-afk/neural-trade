from datetime import datetime, timezone
from typing import List, Tuple, Optional
from app.research.evidence_graph.models import EvidenceNode, NodeType
from app.research.revalidation.models import DecayState

class DecayEngine:
    def calculate_decay(self, supporting_nodes: List[EvidenceNode], as_of: datetime) -> Tuple[Optional[float], DecayState]:
        """
        Determines the age of the evidence. Uses the most recent supporting experiment.
        Strictly enforces the >90 days project rule for STALE evidence.
        """
        exp_nodes = [n for n in supporting_nodes if n.node_type == NodeType.EXPERIMENT]
        if not exp_nodes:
            return None, DecayState.UNKNOWN
            
        # Find the maximum (most recent) created_at or as_of in the supporting experiments
        latest_dt = None
        for n in exp_nodes:
            dt = n.as_of.replace(tzinfo=timezone.utc) if n.as_of.tzinfo is None else n.as_of
            if not latest_dt or dt > latest_dt:
                latest_dt = dt
                
        if not latest_dt:
            return None, DecayState.UNKNOWN
            
        as_of_utc = as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of
        
        # Calculate age in days
        age_seconds = (as_of_utc - latest_dt).total_seconds()
        age_days = age_seconds / 86400.0
        
        if age_days < 0:
            # Future data leakage protection
            age_days = 0.0
            
        if age_days > 90:
            return age_days, DecayState.STALE
        elif age_days > 45:
            return age_days, DecayState.AGING
        else:
            return age_days, DecayState.FRESH
