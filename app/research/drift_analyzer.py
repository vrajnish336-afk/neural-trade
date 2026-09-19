from typing import Optional
from app.backtesting.models import BacktestResult
from app.research.forward_validation_models import ForwardDriftState

class PerformanceDriftAnalyzer:
    """Deterministically compares historical vs forward results."""
    
    @staticmethod
    def analyze(historical_result: BacktestResult, forward_result: BacktestResult) -> ForwardDriftState:
        # 1. Sample Size Check
        if forward_result.number_of_trades < 10:
            return ForwardDriftState.INSUFFICIENT_COMPARISON
            
        if historical_result.number_of_trades == 0:
            return ForwardDriftState.UNRESOLVED
            
        # 2. Extract metrics
        hist_win_rate = historical_result.win_rate
        fwd_win_rate = forward_result.win_rate
        
        hist_pf = historical_result.profit_factor
        fwd_pf = forward_result.profit_factor
        
        hist_avg = historical_result.average_trade_result
        fwd_avg = forward_result.average_trade_result
        
        # 3. Calculate degradation
        # We define degraded if win_rate drops by >15% absolute, OR pf drops by >30% relative
        degraded = False
        significantly_degraded = False
        
        if fwd_win_rate < (hist_win_rate - 15.0):
            degraded = True
        if fwd_win_rate < (hist_win_rate - 25.0):
            significantly_degraded = True
            
        if hist_pf > 1.0:
            pf_drop = (hist_pf - fwd_pf) / hist_pf
            if pf_drop > 0.30:
                degraded = True
            if pf_drop > 0.50 or fwd_pf < 1.0:
                significantly_degraded = True
                
        # 4. Return state
        if significantly_degraded:
            return ForwardDriftState.SIGNIFICANTLY_DEGRADED
        if degraded:
            return ForwardDriftState.DEGRADED
            
        return ForwardDriftState.STABLE
