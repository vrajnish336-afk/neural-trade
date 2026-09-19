import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.core.models import TradingSignal
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_models import LessonState

logger = logging.getLogger(__name__)

class BoundedWeightingResult:
    def __init__(self, strategy: str, weight_multiplier: float, reason: str, evidence_age_days: Optional[float] = None, meta_conclusion: Optional[Any] = None):
        self.strategy = strategy
        self.weight_multiplier = weight_multiplier
        self.reason = reason
        self.evidence_age_days = evidence_age_days
        self.meta_conclusion = meta_conclusion

class StrategyWeightingService:
    def __init__(self, evo_repo: Optional[PaperEvolutionRepository] = None):
        self.evo_repo = evo_repo or PaperEvolutionRepository()
        self.max_weight = 1.5
        self.min_weight = 0.5
        self.max_delta = 0.25 # Max change from neutral (1.0) per update logic bounds

    def calculate_weights(self, signals: List[TradingSignal], as_of: datetime, current_mtf: str = "UNKNOWN", current_corr: str = "UNKNOWN") -> Dict[str, BoundedWeightingResult]:
        # Fetch lessons available strictly before as_of
        all_lessons = self.evo_repo.get_lessons()
        
        # Filter for chronological safety
        valid_lessons = [l for l in all_lessons if l.created_at <= as_of]
        
        results = {}
        for sig in signals:
            strategy_name = sig.strategy
            
            # Find ALL VALIDATED lessons for this strategy across ALL assets/regimes
            strat_lessons = [
                l for l in valid_lessons 
                if l.strategy == strategy_name 
                and l.confidence_status == LessonState.VALIDATED
            ]
            
            # Context match fallback (if we have direct context match, use it. Otherwise use meta-analysis)
            context_matches = [
                l for l in strat_lessons
                if getattr(l, "mtf_alignment", "UNKNOWN") == current_mtf
                and getattr(l, "portfolio_correlation", "UNKNOWN") == current_corr
            ]
            
            if not strat_lessons:
                results[strategy_name] = BoundedWeightingResult(
                    strategy=strategy_name,
                    weight_multiplier=1.0,
                    reason=f"INSUFFICIENT_EVIDENCE - No validated lessons for {strategy_name}."
                )
                continue
                
            # Perform Cross-Asset Meta-Analysis
            try:
                from app.research.meta_analysis.models import MetaEvidenceUnit, MetaResearchStatus
                from app.research.meta_analysis.synthesis import MetaAnalysisEngine
                import hashlib
                
                hash_id = hashlib.md5(strategy_name.encode()).hexdigest()
                units = []
                for sl in strat_lessons:
                    direction = "POSITIVE" if sl.observed_pnl > 0 else "NEGATIVE"
                    units.append(MetaEvidenceUnit(
                        evidence_id=sl.lesson_id,
                        research_identity_hash=hash_id,
                        source_type="PAPER_TRADE",
                        source_id=sl.lesson_id,
                        dataset_identity=",".join(getattr(sl, "cross_asset_symbols", [])),
                        historical_start=sl.data_window_start,
                        historical_end=sl.data_window_end,
                        observed_at=sl.created_at,
                        as_of=sl.created_at,
                        result_direction=direction,
                        sample_size=sl.sample_count
                    ))
                    
                meta_conclusion = MetaAnalysisEngine.synthesize(hash_id, units, as_of)
                
                # Bounded adjustment based on meta-analysis
                base_mult = 1.0
                reason_str = meta_conclusion.evidence_state.value
                
                if meta_conclusion.evidence_state == MetaResearchStatus.ESTABLISHED_WITHIN_TESTED_SCOPE:
                    base_mult = 1.25
                elif meta_conclusion.evidence_state == MetaResearchStatus.SUPPORTED_BUT_CONDITIONAL:
                    # Only boost if context matches perfectly
                    if context_matches:
                        base_mult = 1.15
                        reason_str += " (Context Matched)"
                    else:
                        base_mult = 1.0
                elif meta_conclusion.evidence_state in [MetaResearchStatus.CONFLICTED, MetaResearchStatus.FALSIFIED_WITHIN_TESTED_SCOPE]:
                    base_mult = 0.75
                else:
                    base_mult = 1.0
                    
            except ImportError:
                # Fallback if meta_analysis engine isn't available or fails
                base_mult = 1.0
                reason_str = "META_ANALYSIS_FAILED"
            
            # Identify staleness of latest relevant lesson
            latest = sorted(strat_lessons, key=lambda x: x.created_at, reverse=True)[0]
            age_days = (as_of - latest.created_at).total_seconds() / 86400.0
            
            if age_days > 30:
                base_mult = 1.0
                reason_str = "STALE_EVIDENCE"
                
            results[strategy_name] = BoundedWeightingResult(
                strategy=strategy_name,
                weight_multiplier=max(self.min_weight, min(self.max_weight, base_mult)),
                reason=reason_str,
                evidence_age_days=age_days,
                meta_conclusion=meta_conclusion if 'meta_conclusion' in locals() else None
            )
        return results
