import uuid
import logging
from datetime import datetime, timezone
from typing import List, Callable, Optional
from app.core.models import MarketBar, TradingSignal
from app.backtesting.engine import BacktestEngine
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.backtesting.models import CostConfig
from app.research.multi_timeframe.models import TimeframeHierarchy, TimeframeAblationResult, MultiTimeframeContext
from app.research.multi_timeframe.strategy import MultiTimeframeStrategy

logger = logging.getLogger(__name__)

class MultiTimeframeEvaluator:
    def __init__(self, cost_config: CostConfig):
        self.cost_config = cost_config

    def _run_variant(self, name: str, hierarchy: TimeframeHierarchy, bars: List[MarketBar], 
                     htf_logic, mtf_logic, ltf_logic, as_of: datetime) -> float:
                         
        strat = MultiTimeframeStrategy(
            name=name, hierarchy=hierarchy, dataset_identity="ablation",
            as_of=as_of, htf_logic=htf_logic, mtf_logic=mtf_logic, ltf_logic=ltf_logic
        )
        
        ensemble = StrategyEnsemble([strat])
        risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
        engine = BacktestEngine(
            ensemble=ensemble,
            risk_engine=risk_engine,
            initial_capital=10000.0,
            cost_config=self.cost_config
        )
        
        # Note: BacktestEngine calls ensemble.evaluate().
        # We need to ensure the ensemble correctly routes to strat.evaluate().
        # Ensemble currently loops over strategies and calls evaluate().
        result = engine.run(bars)
        return result.total_return_pct

    def run_ablation(self, candidate_id: str, hierarchy: TimeframeHierarchy, bars: List[MarketBar],
                     htf_logic: Callable, mtf_logic: Callable, ltf_logic: Callable, as_of: datetime) -> TimeframeAblationResult:
        
        # 1. Baseline: HTF Only (Assume LTF logic defaults to a basic crossover if no MTF/LTF provided)
        # To do an ablation, we simulate what would happen if the lower timeframes were removed.
        # But wait, LTF logic generates the actual signal. HTF is just a filter.
        # If we remove HTF, we run LTF alone. If we remove LTF, HTF alone cannot generate a signal on its own unless we adapt the signal generator.
        # A true ablation for MTF architecture:
        # Full: HTF + MTF + LTF
        # HTF + LTF (remove MTF setup)
        # LTF Only (Baseline, remove HTF trend and MTF setup filters)
        
        # LTF Only (No filters)
        ltf_only_return = self._run_variant("LTF_ONLY", hierarchy, bars, 
                                            htf_logic=lambda c, b: True, 
                                            mtf_logic=None, 
                                            ltf_logic=ltf_logic, 
                                            as_of=as_of)
                                            
        # HTF + LTF
        htf_ltf_return = self._run_variant("HTF_LTF", hierarchy, bars, 
                                            htf_logic=htf_logic, 
                                            mtf_logic=None, 
                                            ltf_logic=ltf_logic, 
                                            as_of=as_of)
                                            
        # HTF + MTF + LTF
        full_return = self._run_variant("FULL_MTF", hierarchy, bars, 
                                        htf_logic=htf_logic, 
                                        mtf_logic=mtf_logic, 
                                        ltf_logic=ltf_logic, 
                                        as_of=as_of)
                                        
        return TimeframeAblationResult(
            ablation_id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            hierarchy=hierarchy,
            baseline_return_pct=ltf_only_return,
            htf_only_return_pct=htf_ltf_return,
            htf_mtf_return_pct=full_return,
            full_return_pct=full_return,
            created_at=datetime.now(timezone.utc)
        )
