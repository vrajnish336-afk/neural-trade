from typing import Dict, List, Optional, Tuple
from app.backtesting.models import BacktestTrade
import logging

logger = logging.getLogger(__name__)

class StrategyRegimePerformance:
    def __init__(self):
        self.trades: List[BacktestTrade] = []
        
    def add_trade(self, trade: BacktestTrade):
        self.trades.append(trade)
        
    @property
    def trade_count(self) -> int:
        return len(self.trades)
        
    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        winners = sum(1 for t in self.trades if t.realized_pnl > 0)
        return winners / len(self.trades)
        
    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.realized_pnl for t in self.trades if t.realized_pnl > 0)
        gross_loss = sum(abs(t.realized_pnl) for t in self.trades if t.realized_pnl <= 0)
        if gross_loss == 0.0:
            return gross_profit if gross_profit > 0 else 0.0
        return gross_profit / gross_loss
        
    @property
    def sample_size_label(self) -> str:
        count = self.trade_count
        if count < 5: return "VERY_LOW"
        if count < 15: return "LOW"
        if count < 30: return "MODERATE"
        return "SUFFICIENT"

class AdaptiveIntelligence:
    def __init__(self, min_trades_for_adaptation: int = 5):
        # regime -> strategy -> performance
        self.performance: Dict[str, Dict[str, StrategyRegimePerformance]] = {}
        self.min_trades = min_trades_for_adaptation
        self.current_preferred_strategy: Dict[str, str] = {} # regime -> strategy
        self.trade_history: List[BacktestTrade] = []
        
    def record_trade(self, trade: BacktestTrade):
        regime = trade.regime or "UNKNOWN"
        strategy = trade.strategies or "UNKNOWN"
        
        self.trade_history.append(trade)
        
        if regime not in self.performance:
            self.performance[regime] = {}
            
        if strategy not in self.performance[regime]:
            self.performance[regime][strategy] = StrategyRegimePerformance()
            
        self.performance[regime][strategy].add_trade(trade)
        
    def calculate_effectiveness(self, regime: str) -> Dict[str, float]:
        if regime not in self.performance:
            return {}
            
        scores = {}
        for strategy, perf in self.performance[regime].items():
            if perf.trade_count < self.min_trades:
                scores[strategy] = 0.0 # Insufficient evidence
            else:
                # Deterministic scoring logic: 
                # Profit factor capped at 3.0 (baseline 1.0) + Win rate component
                pf_score = min(perf.profit_factor, 3.0) * 10
                wr_score = perf.win_rate * 20
                scores[strategy] = pf_score + wr_score
                
        return scores
        
    def get_calibrated_min_score(self) -> float:
        """
        Dynamically calculates the minimum score threshold based on completed trades.
        Requires at least 20 trades to calibrate, otherwise returns 0.0 (Fallback).
        """
        if len(self.trade_history) < 20:
            return 0.0
            
        # Analyze performance in bins
        bins = {"0-49": [], "50-69": [], "70-100": []}
        for t in self.trade_history:
            if t.score is None: continue
            
            pnl = t.realized_pnl
            if t.score < 50:
                bins["0-49"].append(pnl)
            elif t.score < 70:
                bins["50-69"].append(pnl)
            else:
                bins["70-100"].append(pnl)
                
        # Find the lowest bin with a positive PF
        for b, pnls in reversed(bins.items()):
            if not pnls: continue
            wins = sum(p for p in pnls if p > 0)
            losses = abs(sum(p for p in pnls if p <= 0))
            pf = wins / losses if losses > 0 else float('inf')
            
            # If highest bin is profitable, we demand at least 70
            if b == "70-100" and pf > 1.2:
                return 70.0
            if b == "50-69" and pf > 1.2:
                return 50.0
                
        return 0.0

    def _get_fallback_weights(self) -> Dict[str, float]:
        return {}
        
    def get_strategy_weights(self, regime: str) -> Tuple[Dict[str, float], str]:
        """
        Returns normalized weights for each strategy and the confidence state.
        If disable_regime_switching is True, returns fallback weights with INSUFFICIENT_EVIDENCE.
        Anti-churn: We only switch preference if the new score exceeds the old by a margin.
        """
        if getattr(self, 'disable_regime_switching', False):
            return self._get_fallback_weights(), "INSUFFICIENT_EVIDENCE"
            
        scores = self.calculate_effectiveness(regime)
        if not scores or all(s == 0.0 for s in scores.values()):
            return {}, "INSUFFICIENT_EVIDENCE"
            
        # Check if we should switch preferred
        best_strategy = max(scores.items(), key=lambda x: x[1])
        current_preferred = self.current_preferred_strategy.get(regime)
        
        if current_preferred and current_preferred in scores:
            if best_strategy[0] != current_preferred:
                # Requires a minimum +1.0 score difference to switch (Anti-churn)
                if best_strategy[1] > scores[current_preferred] + 1.0:
                    self.current_preferred_strategy[regime] = best_strategy[0]
                else:
                    best_strategy = (current_preferred, scores[current_preferred])
        else:
            if best_strategy[1] > 0:
                self.current_preferred_strategy[regime] = best_strategy[0]
                
        total_score = sum(scores.values())
        weights = {s: (val / total_score) if total_score > 0 else 0.0 for s, val in scores.items()}
        
        # Confidence is derived from sample size of the preferred strategy
        perf = self.performance[regime].get(self.current_preferred_strategy.get(regime, ""))
        confidence = "LOW_CONFIDENCE"
        if perf:
            if perf.sample_size_label == "SUFFICIENT":
                confidence = "HIGH_CONFIDENCE"
            elif perf.sample_size_label == "MODERATE":
                confidence = "MODERATE_CONFIDENCE"
                
        return weights, confidence
