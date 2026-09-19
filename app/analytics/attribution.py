from typing import List, Callable, Optional
from app.backtesting.models import BacktestTrade
from app.analytics.models import AttributionMetrics

def _calculate_attribution(trades: List[BacktestTrade], category: str, label: str) -> AttributionMetrics:
    if not trades:
        return AttributionMetrics(category=category, label=label, sample_size=0, win_rate=0.0, total_pnl=0.0, average_pnl=0.0, profit_factor=0.0)
        
    winning = [t for t in trades if t.realized_pnl > 0]
    losing = [t for t in trades if t.realized_pnl <= 0]
    
    total_pnl = sum(t.realized_pnl for t in trades)
    gross_profit = sum(t.realized_pnl for t in winning)
    gross_loss = abs(sum(t.realized_pnl for t in losing))
    
    pf = gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)
    
    return AttributionMetrics(
        category=category,
        label=label,
        sample_size=len(trades),
        win_rate=(len(winning) / len(trades)) * 100.0,
        total_pnl=total_pnl,
        average_pnl=total_pnl / len(trades),
        profit_factor=pf
    )

def analyze_strategy_attribution(trades: List[BacktestTrade]) -> List[AttributionMetrics]:
    strategies = set(t.strategies or "UNKNOWN" for t in trades)
    results = []
    for st in strategies:
        st_trades = [t for t in trades if t.strategies == st]
        results.append(_calculate_attribution(st_trades, "Strategy", st))
    return sorted(results, key=lambda x: x.total_pnl, reverse=True)

def analyze_regime_attribution(trades: List[BacktestTrade]) -> List[AttributionMetrics]:
    regimes = set(t.regime or "UNKNOWN" for t in trades)
    results = []
    for r in regimes:
        r_trades = [t for t in trades if t.regime == r]
        results.append(_calculate_attribution(r_trades, "Regime", r))
    return sorted(results, key=lambda x: x.total_pnl, reverse=True)

def analyze_signal_bucket_attribution(trades: List[BacktestTrade]) -> List[AttributionMetrics]:
    buckets = {"0-19": [], "20-39": [], "40-59": [], "60-79": [], "80-100": [], "UNKNOWN": []}
    
    for t in trades:
        if t.score is None:
            buckets["UNKNOWN"].append(t)
        else:
            if t.score < 20: buckets["0-19"].append(t)
            elif t.score < 40: buckets["20-39"].append(t)
            elif t.score < 60: buckets["40-59"].append(t)
            elif t.score < 80: buckets["60-79"].append(t)
            else: buckets["80-100"].append(t)
            
    results = []
    for k, v in buckets.items():
        if v:
            results.append(_calculate_attribution(v, "Signal Score", k))
            
    return results

def analyze_intelligence_attribution(trades: List[BacktestTrade]) -> List[AttributionMetrics]:
    results = []
    
    # Sentiment
    sentiments = set(t.sentiment_label or "UNKNOWN" for t in trades)
    for s in sentiments:
        results.append(_calculate_attribution([t for t in trades if t.sentiment_label == s], "Sentiment", s))
        
    # Fakeout Risk
    fakeouts = set(t.fakeout_risk or "UNKNOWN" for t in trades)
    for f in fakeouts:
        results.append(_calculate_attribution([t for t in trades if t.fakeout_risk == f], "Fakeout Risk", f))
        
    # Anomaly Flags
    all_flags = set()
    for t in trades:
        if t.anomaly_flags:
            all_flags.update(t.anomaly_flags.split(","))
    
    for flag in all_flags:
        if flag:
            results.append(_calculate_attribution([t for t in trades if t.anomaly_flags and flag in t.anomaly_flags], "Anomaly", flag))
            
    return results
