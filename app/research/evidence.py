from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.research.models import ResearchExperiment
from app.analytics.models import FullAnalyticsReport

class EvidenceStatus(str, Enum):
    STRONG = "STRONG"
    MODERATE = "MODERATE"
    WEAK = "WEAK"
    INSUFFICIENT = "INSUFFICIENT"

class EvidenceConclusion(str, Enum):
    VERIFIED_RESULT = "VERIFIED_RESULT"
    STRATEGY_MODEL_WEAKNESS = "STRATEGY_MODEL_WEAKNESS"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    RESEARCH_LIMITATION = "RESEARCH_LIMITATION"
    SOFTWARE_ACCOUNTING_ISSUE = "SOFTWARE_ACCOUNTING_ISSUE"

class RobustnessState(str, Enum):
    TESTED = "TESTED"
    AVAILABLE_BUT_NOT_RUN = "AVAILABLE_BUT_NOT_RUN"
    NOT_AVAILABLE = "NOT_AVAILABLE"

class DataCoverage(BaseModel):
    train: str
    validation: str
    oos: str
    train_trades: Optional[int] = None
    oos_trades: Optional[int] = None

class RobustnessEvidence(BaseModel):
    walk_forward: RobustnessState
    multi_seed: RobustnessState
    cost_slippage_stress: RobustnessState
    monte_carlo: RobustnessState = RobustnessState.NOT_AVAILABLE
    adversarial_stress: RobustnessState = RobustnessState.NOT_AVAILABLE
    regime_stress: RobustnessState = RobustnessState.NOT_AVAILABLE

class SampleSizeEval(BaseModel):
    total_trades: int
    oos_trades: int
    standard: int = 30
    assessment: str
    regime_trades: Dict[str, int]

class PerformanceEvidence(BaseModel):
    oos_net_pnl: Optional[float]
    oos_profit_factor: Optional[float]
    oos_win_rate: Optional[float]
    train_net_pnl: Optional[float]
    degradation_note: str

from app.research.consistency import EvidenceConsistencyReport, EvidenceConsistencyValidator

class EvidenceSummary(BaseModel):
    status: EvidenceStatus
    conclusion: EvidenceConclusion
    consistency: EvidenceConsistencyReport
    data_coverage: DataCoverage
    robustness: RobustnessEvidence
    sample_size_eval: SampleSizeEval
    performance: PerformanceEvidence
    reasons: List[str]
    limitations: List[str]
    statistical_significance_note: str = "Statistical significance is not established by this evaluator."

class ResearchEvidenceEvaluator:
    @staticmethod
    def evaluate(experiment: ResearchExperiment) -> EvidenceSummary:
        reasons = []
        limitations = []
        
        # 0. Consistency Validation
        consistency = EvidenceConsistencyValidator.validate(experiment)
        if not consistency.is_consistent:
            for inc in consistency.inconsistencies:
                reasons.append(inc)
        
        # 1. Dataset Integrity
        is_software_issue = False
        if experiment.validation_results:
            for val in experiment.validation_results:
                if not val.is_valid:
                    is_software_issue = True
                    reasons.append(f"Dataset validation reported invalid data for {val.symbol}.")
        
        # 2. OOS Extraction
        oos_report = experiment.out_of_sample_report
        if not oos_report:
            reasons.append("OOS report is missing.")
            
        # 3. Sample Size Extraction
        total_trades = 0
        oos_trades = 0
        regime_trades = {}
        
        if oos_report and oos_report.trade_metrics:
            oos_trades = oos_report.trade_metrics.total_trades
            total_trades = oos_trades  # Base assumption, add train if available
            
            for regime in oos_report.regime_attribution:
                regime_trades[regime.label] = regime.sample_size
                
        # 4. Train vs OOS (Walk Forward Extraction)
        train_trades = None
        train_pnl = None
        degradation_note = "Train-vs-OOS degradation unavailable."
        
        walk_forward_state = RobustnessState.NOT_AVAILABLE
        if hasattr(experiment, 'walk_forward_results') and experiment.walk_forward_results:
            walk_forward_state = RobustnessState.TESTED
            # Aggregate training trades/PnL across all windows
            tr_trades = sum(w.train_report.trade_metrics.total_trades for w in experiment.walk_forward_results if w.train_report)
            tr_pnl = sum(w.train_report.trade_metrics.net_pnl for w in experiment.walk_forward_results if w.train_report)
            
            train_trades = tr_trades
            total_trades += train_trades
            train_pnl = tr_pnl
            
            if oos_report and oos_report.trade_metrics:
                degradation_note = "Available (calculated from WF vs OOS)."
        
        data_coverage = DataCoverage(
            train="AVAILABLE" if train_trades is not None else "MISSING",
            validation="AVAILABLE" if walk_forward_state == RobustnessState.TESTED else "MISSING",
            oos="AVAILABLE" if oos_report else "MISSING",
            train_trades=train_trades,
            oos_trades=oos_trades if oos_report else None
        )
        
        # 5. Robustness States
        multi_seed_state = RobustnessState.AVAILABLE_BUT_NOT_RUN
        if hasattr(experiment, 'seeds') and isinstance(experiment.seeds, dict):
            if len(experiment.seeds) > 1:
                multi_seed_state = RobustnessState.TESTED
                
        stress_state = RobustnessState.AVAILABLE_BUT_NOT_RUN
        if hasattr(experiment, 'stress_test_results') and experiment.stress_test_results:
            stress_state = RobustnessState.TESTED
            
        robustness = RobustnessEvidence(
            walk_forward=walk_forward_state,
            multi_seed=multi_seed_state,
            cost_slippage_stress=stress_state
        )
        
        # 6. Regime evidence evaluation
        meaningful_regimes = sum(1 for trades in regime_trades.values() if trades > 0)
        
        # 7. Sample Size Assessment
        sample_assessment = "SUFFICIENT" if oos_trades >= 30 else "INSUFFICIENT"
        
        sample_size_eval = SampleSizeEval(
            total_trades=total_trades,
            oos_trades=oos_trades,
            assessment=sample_assessment,
            regime_trades=regime_trades
        )
        
        # 8. Performance Extraction
        perf = PerformanceEvidence(
            oos_net_pnl=oos_report.trade_metrics.net_pnl if oos_report else None,
            oos_profit_factor=oos_report.trade_metrics.profit_factor if oos_report else None,
            oos_win_rate=oos_report.trade_metrics.win_rate if oos_report else None,
            train_net_pnl=train_pnl,
            degradation_note=degradation_note
        )
        
        # 9. DECISION CASCADE (Strict Order)
        
        if is_software_issue or not consistency.is_consistent:
            conclusion = EvidenceConclusion.SOFTWARE_ACCOUNTING_ISSUE
            status = EvidenceStatus.INSUFFICIENT
            if not consistency.is_consistent:
                reasons.append("Internal evidence inconsistency detected.")
            
        elif not oos_report or oos_trades < 30:
            conclusion = EvidenceConclusion.INSUFFICIENT_EVIDENCE
            status = EvidenceStatus.INSUFFICIENT
            if oos_report and oos_trades < 30:
                reasons.append(f"OOS trade count ({oos_trades}) is below the project standard of 30.")
                
        elif perf.oos_profit_factor is not None and perf.oos_profit_factor < 1.0:
            conclusion = EvidenceConclusion.STRATEGY_MODEL_WEAKNESS
            status = EvidenceStatus.WEAK
            reasons.append("Observed OOS Profit Factor is below 1.0.")
            
        elif perf.oos_net_pnl is not None and perf.oos_net_pnl < 0:
            conclusion = EvidenceConclusion.STRATEGY_MODEL_WEAKNESS
            status = EvidenceStatus.WEAK
            reasons.append("Observed OOS Net PnL is negative.")
            
        elif meaningful_regimes <= 1 or walk_forward_state != RobustnessState.TESTED or stress_state != RobustnessState.TESTED:
            conclusion = EvidenceConclusion.RESEARCH_LIMITATION
            status = EvidenceStatus.MODERATE
            if meaningful_regimes <= 1:
                reasons.append("Multiple regimes were not sufficiently observed.")
                limitations.append("limited regime diversity")
            if walk_forward_state != RobustnessState.TESTED:
                reasons.append("Walk-forward evidence was not actually executed for this experiment.")
                limitations.append("missing walk-forward execution")
            if stress_state != RobustnessState.TESTED:
                reasons.append("Stress testing was not actually executed for this experiment.")
                limitations.append("missing stress test execution")
            if multi_seed_state != RobustnessState.TESTED:
                limitations.append("missing multi-seed execution")
                
        else:
            conclusion = EvidenceConclusion.VERIFIED_RESULT
            status = EvidenceStatus.STRONG
            reasons.append("Observed positive OOS result under the tested assumptions.")
            
        if not limitations:
            limitations.append("fixed/slightly simplified execution assumptions")
            limitations.append("missing statistical significance testing")
            
        # Ensure we always have some explicit limitations appended if not already handled
        if "missing statistical significance testing" not in limitations:
            limitations.append("missing statistical significance testing")

        return EvidenceSummary(
            status=status,
            conclusion=conclusion,
            consistency=consistency,
            data_coverage=data_coverage,
            robustness=robustness,
            sample_size_eval=sample_size_eval,
            performance=perf,
            reasons=reasons,
            limitations=limitations
        )
