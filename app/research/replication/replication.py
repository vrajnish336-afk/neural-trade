from typing import List, Dict, Any, Tuple, Optional
import dateutil.parser
from datetime import datetime
from app.research.evidence_graph.models import EvidenceNode
from app.research.replication.models import ReplicationCategory, ReplicationAssessment

class ReplicationAnalyzer:
    """Analyzes independent evidence, separating overlapping periods and repeated seeds."""

    def analyze(self, supporting_nodes: List[EvidenceNode]) -> ReplicationAssessment:
        experiments = [n for n in supporting_nodes if n.node_type == "EXPERIMENT"]
        if not experiments:
            return ReplicationAssessment(evidence_nodes_assessed=len(supporting_nodes))

        # We will track categorized combinations of datasets to avoid double counting
        # For simplicity in this heuristic engine, we compare each experiment to all others 
        # to find its most "dependent" relation. If it has no dependent relation to prior items, it's INDEPENDENT.

        categories: Dict[str, int] = {k.value: 0 for k in ReplicationCategory}
        independent_count = 0
        overlap_count = 0
        same_dataset_count = 0
        
        seen_datasets = {} # dataset_id -> List of (start_dt, end_dt, seed)
        
        for exp in experiments:
            meta = exp.metadata
            ds_id = meta.get("dataset_id", "unknown")
            seed = meta.get("seed", 0)
            
            # Try to parse start/end for overlap checks
            start_dt = self._parse_date(meta.get("start_time"))
            end_dt = self._parse_date(meta.get("end_time"))
            
            cat = self._classify_experiment(ds_id, seed, start_dt, end_dt, seen_datasets)
            categories[cat.value] += 1
            
            if cat == ReplicationCategory.INDEPENDENT_EXPERIMENT or cat == ReplicationCategory.UNSEEN_DATA:
                independent_count += 1
            elif cat == ReplicationCategory.OVERLAPPING_DATA:
                overlap_count += 1
            elif cat in [ReplicationCategory.SAME_DATASET_REPLAY, ReplicationCategory.SAME_RUN, ReplicationCategory.DIFFERENT_SEED_ONLY]:
                same_dataset_count += 1
                
            if ds_id not in seen_datasets:
                seen_datasets[ds_id] = []
            seen_datasets[ds_id].append((start_dt, end_dt, seed))

        # Warn if there's massive same-dataset rerun (cherry-picking / multiple-testing illusion)
        multiple_testing_risk = (same_dataset_count > 10 and independent_count < 2)

        return ReplicationAssessment(
            category_counts=categories,
            total_independent_units=independent_count,
            overlapping_units=overlap_count,
            same_dataset_units=same_dataset_count,
            multiple_testing_risk=multiple_testing_risk,
            evidence_nodes_assessed=len(supporting_nodes)
        )
        
    def _parse_date(self, val: Any) -> Optional[datetime]:
        if not val: return None
        try:
            return dateutil.parser.isoparse(str(val))
        except Exception:
            return None

    def _classify_experiment(self, ds_id: str, seed: Any, start_dt: Optional[datetime], end_dt: Optional[datetime], seen: Dict[str, List[Tuple]]) -> ReplicationCategory:
        if not seen:
            # First one is our baseline independent observation
            return ReplicationCategory.INDEPENDENT_EXPERIMENT
            
        if ds_id in seen:
            history = seen[ds_id]
            for (h_start, h_end, h_seed) in history:
                # Same exact dataset range
                if h_start == start_dt and h_end == end_dt:
                    if str(h_seed) == str(seed):
                        return ReplicationCategory.SAME_DATASET_REPLAY
                    else:
                        return ReplicationCategory.DIFFERENT_SEED_ONLY
                # Overlap check
                if start_dt and end_dt and h_start and h_end:
                    # Check if (start_dt <= h_end) and (end_dt >= h_start)
                    if start_dt <= h_end and end_dt >= h_start:
                        return ReplicationCategory.OVERLAPPING_DATA
            
            # Same base dataset name, but different periods that don't overlap -> UNSEEN
            return ReplicationCategory.UNSEEN_DATA
            
        return ReplicationCategory.INDEPENDENT_EXPERIMENT
