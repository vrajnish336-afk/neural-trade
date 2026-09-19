from enum import Enum
from typing import List, Optional
from pydantic import BaseModel
from app.research.models import ResearchExperiment

class ComparabilityStatus(str, Enum):
    COMPARABLE = "COMPARABLE"
    LIMITED_COMPARABILITY = "LIMITED_COMPARABILITY"
    NOT_COMPARABLE = "NOT_COMPARABLE"

class ExperimentDifferenceReport(BaseModel):
    exp1_id: str
    exp2_id: str
    
    dataset_1: str
    dataset_2: str
    symbol_1: str
    symbol_2: str
    timeframe_1: str
    timeframe_2: str
    seed_1: str
    seed_2: str
    strategy_1: str
    strategy_2: str
    
    oos_trades_1: str
    oos_trades_2: str
    oos_pnl_1: str
    oos_pnl_2: str
    oos_pf_1: str
    oos_pf_2: str
    
    differences: List[str]
    comparability: ComparabilityStatus
    conclusion: str

class CrossExperimentComparator:
    @staticmethod
    def compare(exp1: ResearchExperiment, exp2: ResearchExperiment) -> ExperimentDifferenceReport:
        differences = []
        
        # Datasets
        id1 = exp1.dataset_identity.get('hash') if isinstance(exp1.dataset_identity, dict) else str(exp1.dataset_identity)
        id2 = exp2.dataset_identity.get('hash') if isinstance(exp2.dataset_identity, dict) else str(exp2.dataset_identity)
        if id1 != id2:
            differences.append(f"Dataset identity mismatch: {id1} vs {id2}")
            
        # Symbol
        sym1 = ",".join(exp1.symbols)
        sym2 = ",".join(exp2.symbols)
        if sym1 != sym2:
            differences.append(f"Symbol mismatch: {sym1} vs {sym2}")
            
        # Timeframe
        if exp1.timeframe != exp2.timeframe:
            differences.append(f"Timeframe mismatch: {exp1.timeframe} vs {exp2.timeframe}")
            
        # Seed
        seed1 = str(exp1.random_seed)
        seed2 = str(exp2.random_seed)
        if seed1 != seed2:
            differences.append(f"Seed mismatch: {seed1} vs {seed2}")
            
        # Strategy
        if exp1.strategy != exp2.strategy:
            differences.append(f"Strategy mismatch: {exp1.strategy} vs {exp2.strategy}")
            
        # Determine comparability
        if id1 != id2 or sym1 != sym2 or exp1.timeframe != exp2.timeframe:
            status = ComparabilityStatus.NOT_COMPARABLE
            conclusion = "COMPARISON INVALID: Core experimental context (dataset, symbol, or timeframe) does not match."
        elif len(differences) > 0:
            status = ComparabilityStatus.LIMITED_COMPARABILITY
            conclusion = "LIMITED COMPARABILITY: Experiments share core context but differ in configuration/seed."
        else:
            status = ComparabilityStatus.COMPARABLE
            
            # If perfectly comparable, we can state a factual observation
            oos1 = exp1.out_of_sample_report
            oos2 = exp2.out_of_sample_report
            
            if oos1 and oos2 and oos1.trade_metrics and oos2.trade_metrics:
                pnl1 = oos1.trade_metrics.net_pnl
                pnl2 = oos2.trade_metrics.net_pnl
                if pnl1 > pnl2:
                    conclusion = f"Experiment {exp1.experiment_id} shows higher observed OOS Net PnL under the compared conditions."
                elif pnl2 > pnl1:
                    conclusion = f"Experiment {exp2.experiment_id} shows higher observed OOS Net PnL under the compared conditions."
                else:
                    conclusion = "Both experiments show identical observed OOS Net PnL under the compared conditions."
            else:
                conclusion = "Experiments are comparable, but OOS performance data is missing."
                
        # Metrics formatting safely
        def _get_metrics(exp: ResearchExperiment):
            if not exp.out_of_sample_report or not exp.out_of_sample_report.trade_metrics:
                return "NOT_AVAILABLE", "NOT_AVAILABLE", "NOT_AVAILABLE"
            tm = exp.out_of_sample_report.trade_metrics
            return str(tm.total_trades), f"{tm.net_pnl:.2f}", f"{tm.profit_factor:.2f}"
            
        t1, pnl1, pf1 = _get_metrics(exp1)
        t2, pnl2, pf2 = _get_metrics(exp2)

        return ExperimentDifferenceReport(
            exp1_id=exp1.experiment_id,
            exp2_id=exp2.experiment_id,
            dataset_1=id1 or "NOT_AVAILABLE",
            dataset_2=id2 or "NOT_AVAILABLE",
            symbol_1=sym1,
            symbol_2=sym2,
            timeframe_1=exp1.timeframe or "NOT_AVAILABLE",
            timeframe_2=exp2.timeframe or "NOT_AVAILABLE",
            seed_1=seed1,
            seed_2=seed2,
            strategy_1=exp1.strategy or "NOT_AVAILABLE",
            strategy_2=exp2.strategy or "NOT_AVAILABLE",
            oos_trades_1=t1,
            oos_trades_2=t2,
            oos_pnl_1=pnl1,
            oos_pnl_2=pnl2,
            oos_pf_1=pf1,
            oos_pf_2=pf2,
            differences=differences,
            comparability=status,
            conclusion=conclusion
        )
