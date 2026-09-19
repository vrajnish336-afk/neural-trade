from typing import List
from app.backtesting.models import BacktestTrade
from app.analytics.models import FailureFinding
from app.analytics.attribution import analyze_regime_attribution, analyze_strategy_attribution, analyze_intelligence_attribution

def generate_failure_findings(trades: List[BacktestTrade]) -> List[FailureFinding]:
    """
    Analyzes trades to identify patterns associated with negative performance.
    """
    findings = []
    
    if not trades:
        return findings
        
    MIN_SAMPLE_SIZE = 3 # Require at least a few trades to flag a pattern
    
    # Check Regimes
    regime_attr = analyze_regime_attribution(trades)
    for attr in regime_attr:
        if attr.sample_size >= MIN_SAMPLE_SIZE and attr.average_pnl < 0:
            findings.append(FailureFinding(
                finding=f"Trades executed in the {attr.label} regime produced negative average returns.",
                sample_size=attr.sample_size,
                metric="average_pnl"
            ))
            
    # Check Strategies
    strategy_attr = analyze_strategy_attribution(trades)
    for attr in strategy_attr:
        if attr.sample_size >= MIN_SAMPLE_SIZE and attr.average_pnl < 0:
            findings.append(FailureFinding(
                finding=f"Strategy {attr.label} underperformed with negative total P&L.",
                sample_size=attr.sample_size,
                metric="total_pnl"
            ))
            
    # Check Intelligence (Fakeout & Anomalies)
    intel_attr = analyze_intelligence_attribution(trades)
    for attr in intel_attr:
        if attr.category == "Fakeout Risk" and attr.label == "POSSIBLE_FAKEOUT":
            if attr.sample_size >= MIN_SAMPLE_SIZE and attr.win_rate < 50.0:
                findings.append(FailureFinding(
                    finding=f"POSSIBLE_FAKEOUT signals historically had a poor win rate ({attr.win_rate:.1f}%).",
                    sample_size=attr.sample_size,
                    metric="win_rate"
                ))
        if attr.category == "Sentiment" and attr.label == "NEGATIVE":
            if attr.sample_size >= MIN_SAMPLE_SIZE and attr.average_pnl < 0:
                findings.append(FailureFinding(
                    finding=f"Trades entered during NEGATIVE sentiment generated negative average returns.",
                    sample_size=attr.sample_size,
                    metric="average_pnl"
                ))
                
    return findings
