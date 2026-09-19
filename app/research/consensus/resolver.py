from typing import List, Tuple
from app.research.consensus.models import EvidenceConsensusUnit, ConsensusConflict, ConflictType, ConflictSeverity, ResolutionState

class ConflictResolver:
    def evaluate_conflicts(self, support_units: List[EvidenceConsensusUnit], contradict_units: List[EvidenceConsensusUnit]) -> Tuple[List[ConsensusConflict], List[str]]:
        conflicts = []
        conditions = set()
        
        if not support_units or not contradict_units:
            return conflicts, list(conditions)
            
        s_regimes = {u.regime for u in support_units if u.regime}
        c_regimes = {u.regime for u in contradict_units if u.regime}
        
        s_methods = {u.methodology_version for u in support_units if u.methodology_version}
        c_methods = {u.methodology_version for u in contradict_units if u.methodology_version}
        
        s_costs = {u.cost_assumption for u in support_units if u.cost_assumption}
        c_costs = {u.cost_assumption for u in contradict_units if u.cost_assumption}
        
        # Regime divergence -> CONDITIONAL_CONSENSUS
        if s_regimes and c_regimes and s_regimes.isdisjoint(c_regimes):
            conditions.update(s_regimes)
            conflicts.append(ConsensusConflict(
                conflict_type=ConflictType.REGIME_CONFLICT,
                severity=ConflictSeverity.MODERATE,
                resolution=ResolutionState.RESOLVED_BY_CONDITION,
                condition=f"Regime: {', '.join(s_regimes)}",
                description=f"Evidence is divided explicitly by regime boundaries (Support: {s_regimes}, Contradict: {c_regimes})"
            ))
            
        # Methodology drift -> METHODOLOGY_CONFLICT
        elif s_methods and c_methods and s_methods.isdisjoint(c_methods):
            conflicts.append(ConsensusConflict(
                conflict_type=ConflictType.METHODOLOGY_CONFLICT,
                severity=ConflictSeverity.HIGH,
                resolution=ResolutionState.RESOLVED_BY_METHODOLOGY,
                condition=f"Methodology: {', '.join(s_methods)} vs {', '.join(c_methods)}",
                description="Evidence conflicts, but they were generated using materially different methodologies."
            ))
            
        # Cost conflict
        elif s_costs and c_costs and s_costs.isdisjoint(c_costs):
            conflicts.append(ConsensusConflict(
                conflict_type=ConflictType.COST_CONFLICT,
                severity=ConflictSeverity.HIGH,
                resolution=ResolutionState.RESOLVED_BY_CONDITION,
                condition=f"Cost Assumption: {', '.join(s_costs)}",
                description="Evidence conflicts primarily on differing cost assumptions."
            ))
            
        else:
            # Absolute unstructured conflict
            conflicts.append(ConsensusConflict(
                conflict_type=ConflictType.UNKNOWN_CONFLICT,
                severity=ConflictSeverity.CRITICAL,
                resolution=ResolutionState.UNRESOLVED,
                description="Direct conflict found on comparable metadata parameters."
            ))
            
        return conflicts, list(conditions)
