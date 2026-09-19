import logging
from typing import List, Dict, Tuple
from app.research.evidence_graph.models import EvidenceNode
from app.research.hypothesis_validation.models import FalsificationState

logger = logging.getLogger(__name__)

class FalsificationEngine:
    """
    Evaluates whether a given falsification_condition is triggered by the provided contradicting evidence.
    """
    
    def evaluate(self, falsification_condition: str, contradicting_nodes: List[EvidenceNode]) -> Tuple[FalsificationState, str]:
        if not falsification_condition:
            return FalsificationState.UNDETERMINED, "No explicit falsification condition provided."
            
        if not contradicting_nodes:
            return FalsificationState.NOT_TRIGGERED, "No contradicting evidence nodes found to trigger falsification."
            
        # Deterministic falsification evaluation based on keyword mapping vs node metadata.
        # This operates on structurally mapped text to avoid LLM hallucination and ensure determinism.
        
        fc_lower = falsification_condition.lower()
        trigger_count = 0
        
        for node in contradicting_nodes:
            # We look at the node's metadata or type to see if it materially aligns with the falsification
            metadata_str = str(node.metadata).lower()
            
            # Simple heuristic matching
            # E.g., if falsification condition is "performance degrades below statistical significance"
            # and the contradicting node is an EXPERIMENT, we consider it a trigger.
            if "degrades" in fc_lower or "statistical significance" in fc_lower:
                if "performance_degraded" in metadata_str or "insignificant" in metadata_str:
                    trigger_count += 1
                elif node.node_type == "EXPERIMENT":
                    trigger_count += 1 # Any contradicting experiment counts towards this generic falsification
            elif "statistically indistinguishable" in fc_lower or "remains" in fc_lower:
                if "indistinguishable" in metadata_str or "no_change" in metadata_str:
                    trigger_count += 1
                elif node.node_type == "EXPERIMENT":
                    trigger_count += 1
            else:
                # Fallback: if there is contradicting evidence and it's an experiment, we lean towards TRIGGERED to be conservative
                trigger_count += 1
                
        if trigger_count > 0:
            return FalsificationState.TRIGGERED, f"Falsification condition triggered by {trigger_count} contradicting evidence nodes."
            
        return FalsificationState.NOT_TRIGGERED, "Contradicting evidence exists but did not meet the specific falsification threshold."
