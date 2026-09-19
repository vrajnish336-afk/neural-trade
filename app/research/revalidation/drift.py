from datetime import datetime, timezone
from typing import List, Dict, Set
from app.research.evidence_graph.models import EvidenceNode, NodeType
from app.research.revalidation.models import RevalidationReason
from app.research.hypothesis_validation.models import HypothesisValidationResult

class DriftEngine:
    def detect_drift(self, validation: HypothesisValidationResult, all_newer_experiments: List[EvidenceNode], base_experiments: List[EvidenceNode]) -> tuple[List[str], List[RevalidationReason]]:
        """
        Scans for drift comparing the base experiments (at the time of validation)
        against the newer experiments (discovered post-validation up to the as_of boundary).
        """
        reasons = set()
        flags = []
        
        if not base_experiments:
            return flags, list(reasons)
            
        base_regimes = set()
        base_methodologies = set()
        base_datasets = set()
        
        for n in base_experiments:
            meta = n.metadata
            if "regime" in meta: base_regimes.add(meta["regime"])
            if "methodology_version" in meta: base_methodologies.add(meta["methodology_version"])
            if "dataset_id" in meta: base_datasets.add(meta["dataset_id"])
            
        for n in all_newer_experiments:
            meta = n.metadata
            
            # Regime drift
            if "regime" in meta and meta["regime"] not in base_regimes and base_regimes:
                reasons.add(RevalidationReason.NEW_REGIME)
                if "REGIME_SHIFT" not in flags: flags.append("REGIME_SHIFT")
                
            # Methodology drift
            if "methodology_version" in meta and meta["methodology_version"] not in base_methodologies and base_methodologies:
                reasons.add(RevalidationReason.METHODOLOGY_CHANGED)
                if "METHODOLOGY_DRIFT" not in flags: flags.append("METHODOLOGY_DRIFT")
                
            # Dataset drift
            if "dataset_id" in meta and meta["dataset_id"] not in base_datasets and base_datasets:
                reasons.add(RevalidationReason.DATASET_DRIFT)
                if "DATASET_DRIFT" not in flags: flags.append("DATASET_DRIFT")
                
            # Cost drift (assume encoded in a cost_scenario flag in metadata)
            if "cost_scenario" in meta and "cost_scenario" in base_experiments[0].metadata:
                if meta["cost_scenario"] != base_experiments[0].metadata["cost_scenario"]:
                    reasons.add(RevalidationReason.COST_DRIFT)
                    if "COST_DRIFT" not in flags: flags.append("COST_DRIFT")
                    
        return flags, list(reasons)
