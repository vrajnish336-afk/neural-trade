from typing import List, Dict, Any
from app.backtesting.models import BacktestResult
from app.analytics.models import FullAnalyticsReport, StrategyComparison
from app.analytics.performance import calculate_trade_metrics, calculate_equity_metrics
from app.analytics.attribution import (
    analyze_strategy_attribution,
    analyze_regime_attribution,
    analyze_signal_bucket_attribution,
    analyze_intelligence_attribution
)
from app.analytics.failure_analysis import generate_failure_findings

def generate_analytics_report(run_id: str, result: BacktestResult) -> FullAnalyticsReport:
    """
    Generates a full analytics report from a completed backtest result.
    """
    trades = result.trades
    
    trade_metrics = calculate_trade_metrics(trades)
    equity_metrics = calculate_equity_metrics(result.equity_curve, result.initial_capital)
    
    strategy_attr = analyze_strategy_attribution(trades)
    regime_attr = analyze_regime_attribution(trades)
    signal_attr = analyze_signal_bucket_attribution(trades)
    intel_attr = analyze_intelligence_attribution(trades)
    
    failures = generate_failure_findings(trades)
    
    # Simple Strategy Comparison mapping (just formatting the attribution)
    comparisons = []
    for attr in strategy_attr:
        comparisons.append(StrategyComparison(
            strategy=attr.label,
            trade_count=attr.sample_size,
            total_return_pct=(attr.total_pnl / result.initial_capital) * 100, # Approximation for sub-strategy
            max_drawdown_pct=0.0, # Cannot accurately isolate DD per strategy from a single shared portfolio trivially
            win_rate=attr.win_rate,
            profit_factor=attr.profit_factor,
            average_trade=attr.average_pnl,
            sample_size_warning=(attr.sample_size < 30)
        ))
        
    return FullAnalyticsReport(
        backtest_id=run_id,
        trade_metrics=trade_metrics,
        equity_metrics=equity_metrics,
        strategy_attribution=strategy_attr,
        regime_attribution=regime_attr,
        signal_bucket_attribution=signal_attr,
        intelligence_attribution=intel_attr,
        failure_findings=failures,
        strategy_comparisons=comparisons,
        telemetry_snapshot=getattr(result, 'telemetry_snapshot', None)
    )

