import math
from typing import List, Optional
from pydantic import BaseModel
from app.research.models import ResearchExperiment

class EvidenceConsistencyReport(BaseModel):
    is_consistent: bool
    inconsistencies: List[str]
    warnings: List[str]

class EvidenceConsistencyValidator:
    @staticmethod
    def validate(experiment: ResearchExperiment) -> EvidenceConsistencyReport:
        inconsistencies = []
        warnings = []
        
        # A. Dataset Validity
        if experiment.validation_results:
            for val in experiment.validation_results:
                if not val.is_valid:
                    inconsistencies.append(f"Dataset validation explicitly invalid for {val.symbol}.")
        else:
            warnings.append("Dataset validation metadata NOT_AVAILABLE.")

        # B. Strategy Metadata Consistency
        oos = experiment.out_of_sample_report
        if oos:
            if hasattr(oos, 'strategy_attribution') and oos.strategy_attribution:
                # We can't guarantee a single strategy in the OOS report, but if there's only 1, it should match
                # Wait, does the OOS report have a single strategy name?
                # actually, `strategy_attribution` is a list of AttributionMetrics.
                strat_labels = [attr.label for attr in oos.strategy_attribution]
                if strat_labels and experiment.strategy not in strat_labels:
                    # Let's be careful. Ensembles might have multiple. 
                    # If it's explicitly one strategy, and it doesn't match...
                    # Let's just issue a warning, or maybe an inconsistency if we're sure.
                    warnings.append(f"Metadata strategy '{experiment.strategy}' not found in report strategy_attribution labels.")

        # C. Trade Count Consistency
        if oos and oos.trade_metrics:
            oos_trades = oos.trade_metrics.total_trades
            if oos.telemetry_snapshot and 'stage_counts' in oos.telemetry_snapshot:
                stages = oos.telemetry_snapshot['stage_counts']
                if 'PAPER_TRADES' in stages:
                    telemetry_trades = stages['PAPER_TRADES']
                    if telemetry_trades != oos_trades:
                        inconsistencies.append(f"Telemetry trade count ({telemetry_trades}) differs from OOS report trade count ({oos_trades}).")
            else:
                warnings.append("Telemetry trade count NOT_AVAILABLE.")
        
        # D. Accounting Consistency
        if oos and oos.trade_metrics:
            tm = oos.trade_metrics
            expected_net = tm.gross_pnl - tm.total_commission
            if not math.isclose(expected_net, tm.net_pnl, abs_tol=1e-4):
                inconsistencies.append(f"Accounting mismatch: Gross PnL ({tm.gross_pnl}) - Commission ({tm.total_commission}) != Net PnL ({tm.net_pnl}).")

        is_consistent = len(inconsistencies) == 0

        return EvidenceConsistencyReport(
            is_consistent=is_consistent,
            inconsistencies=inconsistencies,
            warnings=warnings
        )
