import pandas as pd
from typing import Dict, List, Optional
from datetime import datetime, timezone
from app.research.portfolio_intelligence.models import (
    PortfolioResearchSnapshot, DiversificationAssessment, PortfolioResearchAssessment, CorrelationResult
)
from app.research.portfolio_intelligence.correlation import CorrelationEngine
from app.research.portfolio_intelligence.portfolio import PortfolioComposer

class PortfolioEvaluator:
    
    @staticmethod
    def evaluate(
        candidate_ids: List[str],
        weights: Dict[str, float],
        dataset_identity: str,
        returns_map: Dict[str, pd.Series],
        drawdowns_map: Dict[str, pd.Series],
        cost_model: dict,
        risk_model: dict,
        as_of: datetime,
        seed: int = 42
    ) -> PortfolioResearchSnapshot:
        
        if not PortfolioComposer.validate_weights(weights):
            raise ValueError("Invalid weights provided. Must sum to 1.0 and be non-negative.")
            
        aligned_returns = PortfolioComposer.align_series(returns_map)
        if aligned_returns.empty:
            raise ValueError("No overlapping historical data to construct portfolio.")
            
        common_start = aligned_returns.index.min()
        common_end = aligned_returns.index.max()
        
        if common_end > as_of:
            raise ValueError("Future data leak detected: common_end > as_of boundary.")
            
        # Calculate Correlation Matrix
        corr_matrix = {}
        for c1 in candidate_ids:
            corr_matrix[c1] = {}
            for c2 in candidate_ids:
                if c1 == c2:
                    corr_matrix[c1][c2] = CorrelationResult(pearson_correlation=1.0, spearman_correlation=1.0, drawdown_overlap_pct=1.0, sample_size=len(aligned_returns), is_statistically_significant=True)
                    continue
                    
                corr = CorrelationEngine.calculate_correlation(aligned_returns[c1], aligned_returns[c2])
                dd_overlap = CorrelationEngine.calculate_drawdown_overlap(drawdowns_map[c1], drawdowns_map[c2])
                corr.drawdown_overlap_pct = dd_overlap
                corr_matrix[c1][c2] = corr
                
        # Diversification Assessment
        # Simple heuristic for research simulation
        max_corr = -1.0
        max_dd_overlap = 0.0
        
        for c1 in candidate_ids:
            for c2 in candidate_ids:
                if c1 != c2:
                    cr = corr_matrix[c1][c2]
                    if cr.is_statistically_significant and cr.pearson_correlation is not None:
                        max_corr = max(max_corr, cr.pearson_correlation)
                        max_dd_overlap = max(max_dd_overlap, cr.drawdown_overlap_pct or 0.0)
                        
        div_state = DiversificationAssessment.INSUFFICIENT_EVIDENCE
        if max_corr != -1.0:
            if max_dd_overlap > 0.6:
                div_state = DiversificationAssessment.CONCENTRATED_DOWNSIDE
            elif max_corr < 0.3:
                div_state = DiversificationAssessment.STRONG_DIVERSIFICATION_EVIDENCE
            elif max_corr < 0.6:
                div_state = DiversificationAssessment.MODERATE_DIVERSIFICATION_EVIDENCE
            elif max_corr < 0.8:
                div_state = DiversificationAssessment.WEAK_DIVERSIFICATION
            else:
                div_state = DiversificationAssessment.NO_DIVERSIFICATION_EVIDENCE
                
        # Overall Assessment
        port_state = PortfolioResearchAssessment.INSUFFICIENT_EVIDENCE
        if div_state in [DiversificationAssessment.STRONG_DIVERSIFICATION_EVIDENCE, DiversificationAssessment.MODERATE_DIVERSIFICATION_EVIDENCE]:
            port_state = PortfolioResearchAssessment.ROBUST_PORTFOLIO_EVIDENCE
        elif div_state == DiversificationAssessment.CONCENTRATED_DOWNSIDE:
            port_state = PortfolioResearchAssessment.FRAGILE_PORTFOLIO_EVIDENCE
        elif div_state in [DiversificationAssessment.WEAK_DIVERSIFICATION, DiversificationAssessment.NO_DIVERSIFICATION_EVIDENCE]:
            port_state = PortfolioResearchAssessment.CONDITIONAL_PORTFOLIO_EVIDENCE
            
        return PortfolioResearchSnapshot(
            candidate_ids=candidate_ids,
            dataset_identity=dataset_identity,
            common_start=common_start,
            common_end=common_end,
            weights=weights,
            cost_model=cost_model,
            risk_model=risk_model,
            as_of=as_of,
            seed=seed,
            correlation_matrix=corr_matrix,
            diversification_state=div_state,
            research_assessment=port_state,
            created_at=datetime.now(timezone.utc)
        )
