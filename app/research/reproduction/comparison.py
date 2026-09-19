import math
from app.research.reproduction.models import (
    OriginalResearchOutput, 
    ReproducedResearchOutput, 
    ComparisonState, 
    ReproductionDiscrepancy, 
    DiscrepancyCategory
)

class ResearchComparator:
    
    ABSOLUTE_TOLERANCE = 1e-6
    RELATIVE_TOLERANCE = 1e-4

    @staticmethod
    def compare(orig: OriginalResearchOutput, repo: ReproducedResearchOutput) -> tuple[ComparisonState, list[ReproductionDiscrepancy]]:
        discrepancies = []
        
        # 1. Structural Comparison
        if orig.trade_count is not None and repo.trade_count is not None:
            if orig.trade_count != repo.trade_count:
                discrepancies.append(ReproductionDiscrepancy(
                    category=DiscrepancyCategory.TRADE_SEQUENCE_DIFFERENCE,
                    description=f"Trade count mismatch: Orig {orig.trade_count} vs Repo {repo.trade_count}",
                    evidence_context="Structural execution difference"
                ))
                
        # 2. Output Fingerprint Match
        if orig.result_fingerprint != "UNKNOWN" and repo.output_fingerprint != "UNKNOWN":
            if orig.result_fingerprint != repo.output_fingerprint:
                # Could be structural, could be numerical drift that crossed rounding threshold
                discrepancies.append(ReproductionDiscrepancy(
                    category=DiscrepancyCategory.NONDETERMINISTIC_OUTPUT_DETECTED,
                    description=f"Fingerprint mismatch: Orig {orig.result_fingerprint[:8]} vs Repo {repo.output_fingerprint[:8]}",
                    evidence_context="Determinism boundary violated"
                ))

        # 3. Numerical Comparison (PnL)
        pnl_diff = False
        if orig.return_pct is not None and repo.return_pct is not None:
            diff = abs(orig.return_pct - repo.return_pct)
            if diff > ResearchComparator.ABSOLUTE_TOLERANCE and (diff / max(abs(orig.return_pct), 1e-9)) > ResearchComparator.RELATIVE_TOLERANCE:
                discrepancies.append(ReproductionDiscrepancy(
                    category=DiscrepancyCategory.NUMERICAL_DRIFT,
                    description=f"PnL diff exceeds tolerance: {diff:.6f}",
                    evidence_context="Mathematical variance detected"
                ))
                pnl_diff = True
                
        # 4. Resolve State
        if not discrepancies:
            return ComparisonState.EXACT_MATCH, []
            
        if pnl_diff and any(d.category == DiscrepancyCategory.TRADE_SEQUENCE_DIFFERENCE for d in discrepancies):
            return ComparisonState.STRUCTURAL_DIFFERENCE, discrepancies
            
        if pnl_diff:
            return ComparisonState.MATERIAL_DIFFERENCE, discrepancies
            
        # If no material PnL diff but some other flag hit (e.g. slight fingerprint miss due to rounding before hashing)
        # We classify it as WITHIN_TOLERANCE if trade count is identical and PnL is identical.
        if any(d.category == DiscrepancyCategory.TRADE_SEQUENCE_DIFFERENCE for d in discrepancies):
            return ComparisonState.STRUCTURAL_DIFFERENCE, discrepancies
            
        return ComparisonState.WITHIN_TOLERANCE, discrepancies
