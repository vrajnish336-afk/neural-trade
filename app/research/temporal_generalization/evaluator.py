import hashlib
import statistics
from datetime import datetime, timezone
from typing import List
from app.research.temporal_generalization.models import (
    WalkForwardWindow, WalkForwardWindowStatus, 
    TemporalGeneralizationAssessment, TemporalGeneralizationState, WalkForwardType
)

class TemporalEvaluator:
    def evaluate(self, run_id: str, candidate_id: str, windows: List[WalkForwardWindow], wf_type: WalkForwardType, as_of: datetime) -> TemporalGeneralizationAssessment:
        if not windows:
            return TemporalGeneralizationAssessment(
                assessment_id=hashlib.sha256(f"temp_{run_id}".encode()).hexdigest()[:16],
                candidate_id=candidate_id, run_id=run_id, window_type=wf_type,
                total_windows=0, successful_windows=0, failed_windows=0, zero_trade_windows=0,
                performance_dispersion=0.0, drawdown_dispersion=0.0, trade_count_dispersion=0.0,
                overall_state=TemporalGeneralizationState.INSUFFICIENT_WINDOWS,
                as_of=as_of, created_at=datetime.now(timezone.utc)
            )
            
        successes = [w for w in windows if w.status == WalkForwardWindowStatus.COMPLETED and w.return_pct > 0]
        fails = [w for w in windows if w.status == WalkForwardWindowStatus.FAILED or (w.status == WalkForwardWindowStatus.COMPLETED and w.return_pct <= 0)]
        zero_trades = [w for w in windows if w.status == WalkForwardWindowStatus.NO_SIGNAL]
        
        returns = [w.return_pct for w in windows if w.status == WalkForwardWindowStatus.COMPLETED]
        drawdowns = [w.max_drawdown_pct for w in windows if w.status == WalkForwardWindowStatus.COMPLETED]
        trades = [w.trade_count for w in windows if w.status == WalkForwardWindowStatus.COMPLETED]
        
        perf_disp = statistics.stdev(returns) if len(returns) > 1 else 0.0
        dd_disp = statistics.stdev(drawdowns) if len(drawdowns) > 1 else 0.0
        tr_disp = statistics.stdev(trades) if len(trades) > 1 else 0.0
        
        # State logic
        state = TemporalGeneralizationState.INCONSISTENT
        gaps = []
        
        if len(windows) < 3:
            state = TemporalGeneralizationState.INSUFFICIENT_WINDOWS
            gaps.append("FORWARD_SAMPLE_SIZE_GAP")
        else:
            win_rate = len(successes) / len(windows)
            if win_rate >= 0.8:
                state = TemporalGeneralizationState.STRONG_TEMPORAL_GENERALIZATION
            elif win_rate >= 0.5:
                state = TemporalGeneralizationState.MODERATE_TEMPORAL_GENERALIZATION
            elif win_rate > 0.0:
                state = TemporalGeneralizationState.WEAK_TEMPORAL_GENERALIZATION
            else:
                state = TemporalGeneralizationState.FRAGILE_TEMPORAL_GENERALIZATION
                
            if perf_disp > 0.1: # 10% standard dev in returns across forward windows is highly unstable
                if state in [TemporalGeneralizationState.STRONG_TEMPORAL_GENERALIZATION, TemporalGeneralizationState.MODERATE_TEMPORAL_GENERALIZATION]:
                    state = TemporalGeneralizationState.INCONSISTENT
                    gaps.append("WINDOW_INCONSISTENCY_GAP")
                    
        return TemporalGeneralizationAssessment(
            assessment_id=hashlib.sha256(f"temp_{run_id}_{as_of.timestamp()}".encode()).hexdigest()[:16],
            candidate_id=candidate_id, run_id=run_id, window_type=wf_type,
            total_windows=len(windows), successful_windows=len(successes),
            failed_windows=len(fails), zero_trade_windows=len(zero_trades),
            performance_dispersion=perf_disp, drawdown_dispersion=dd_disp, trade_count_dispersion=tr_disp,
            overall_state=state, research_gaps=gaps,
            as_of=as_of, created_at=datetime.now(timezone.utc)
        )
