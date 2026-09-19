import logging
from typing import List, Optional, Set, Dict, Any
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence, SignalScore
from app.strategies.base import Strategy
from app.diagnostics.telemetry import telemetry
from app.diagnostics.models import RejectionReason
from app.config import config

from app.strategies.adaptive import AdaptiveIntelligence

logger = logging.getLogger(__name__)

class StrategyEnsemble:
    """
    Evaluates multiple strategies, calculates signal confluence,
    adapts to market regime, and deterministically scores the final signal.
    """
    def __init__(self, strategies: List[Strategy], min_score: float = None, adaptive_intelligence: Optional[AdaptiveIntelligence] = None):
        self.strategies = strategies
        # min_score is kept for backward compatibility but dynamic strategy threshold is preferred
        self.min_score = min_score if min_score is not None else config.MIN_SIGNAL_SCORE
        self.adaptive = adaptive_intelligence
        
    def evaluate(self, bars: List[MarketBar], regime: MarketRegimeResult, intelligence: Optional[MarketIntelligence] = None, pre_generated_signals: Optional[List[TradingSignal]] = None) -> Optional[TradingSignal]:
        if regime.regime == "INSUFFICIENT_DATA":
            telemetry.record_rejection(RejectionReason.INSUFFICIENT_DATA, regime.regime)
            return None
            
        if pre_generated_signals is not None:
            signals = pre_generated_signals
            for sig in signals:
                telemetry.record_strategy_eval(sig.strategy, sig.direction)
        else:
            signals = []
            for strategy in self.strategies:
                sig = strategy.generate_signal(bars)
                telemetry.record_strategy_eval(strategy.__class__.__name__, sig.direction if sig else None)
                if sig:
                    signals.append(sig)
                
        if not signals:
            telemetry.record_rejection(RejectionReason.NO_STRATEGY_SIGNAL, regime.regime)
            return None
            
        directions = {s.direction for s in signals}
        final_direction = None
        
        if self.adaptive:
            weights, confidence = self.adaptive.get_strategy_weights(regime.regime)
            
            # Telemetry for adaptive model
            if hasattr(telemetry, 'record_adaptive_decision'):
                telemetry.record_adaptive_decision(regime.regime, weights, confidence)
                
            if confidence != "INSUFFICIENT_EVIDENCE":
                preferred = self.adaptive.current_preferred_strategy.get(regime.regime)
                if preferred:
                    # Filter signals to only the preferred strategy
                    preferred_signals = [s for s in signals if s.strategy == preferred]
                    if preferred_signals:
                        signals = preferred_signals
                        directions = {s.direction for s in signals}
                        final_direction = list(directions)[0]
                        
        if final_direction is None:
            if len(directions) > 1:
                best = max(signals, key=lambda s: s.confidence)
                ties = [s for s in signals if s.confidence == best.confidence]
                if len({s.direction for s in ties}) > 1:
                    telemetry.record_rejection(RejectionReason.STRATEGY_CONFLICT, regime.regime)
                    return None # Tie across different directions -> Wait
                signals = ties
                directions = {s.direction for s in signals}
                final_direction = best.direction
            else:
                final_direction = list(directions)[0]
            
        telemetry.record_stage("STRATEGY_SIGNALS")
        
        # 1. Base Strategy Score
        components = {"base": 50.0}
        
        # 2. Market Regime Alignment
        regime_alignment = 0.0
        if final_direction == "LONG" and regime.regime == "TRENDING_UP":
            regime_alignment = 40.0
        elif final_direction == "SHORT" and regime.regime == "TRENDING_DOWN":
            regime_alignment = 40.0
        elif final_direction == "LONG" and regime.regime == "TRENDING_DOWN":
            telemetry.record_rejection(RejectionReason.REGIME_VETO, regime.regime)
            return None # Veto
        elif final_direction == "SHORT" and regime.regime == "TRENDING_UP":
            telemetry.record_rejection(RejectionReason.REGIME_VETO, regime.regime)
            return None # Veto
        elif regime.regime == "HIGH_VOLATILITY":
            telemetry.record_rejection(RejectionReason.REGIME_VETO, regime.regime)
            return None # Veto
        else:
            regime_alignment = 10.0 # Range bound or neutral
            
        components["regime_alignment"] = regime_alignment
        
        if intelligence:
            # Negative News Filter
            if final_direction == "LONG" and intelligence.sentiment.label == "NEGATIVE":
                telemetry.record_rejection(RejectionReason.NEGATIVE_NEWS_FILTER, regime.regime)
                return None # Veto LONG on negative news
            elif final_direction == "SHORT" and intelligence.sentiment.label == "POSITIVE":
                telemetry.record_rejection(RejectionReason.NEGATIVE_NEWS_FILTER, regime.regime)
                return None # Veto SHORT on positive news
            elif intelligence.sentiment.label in ["POSITIVE", "NEGATIVE"]:
                # Agreeing news adds score
                components["news_alignment"] = 20.0
                
            # Fakeout Risk Filter
            if intelligence.fakeout_risk == "POSSIBLE_FAKEOUT":
                telemetry.record_rejection(RejectionReason.FAKEOUT_FILTER, regime.regime)
                return None # Veto on fakeout risk
                
            # Anomaly Filter
            if intelligence.anomaly_status:
                components["anomaly_penalty"] = -20.0
                
        score_val = sum(components.values())
        
        telemetry.record_stage("ENSEMBLE_SIGNALS")
        best_signal = max(signals, key=lambda s: s.confidence)
        
        # Use strategy-specific min score or fallback
        strategy_min = config.get_strategy_min_score(best_signal.strategy)
        dynamic_min = max(self.min_score, strategy_min)
        
        if self.adaptive:
            dynamic_min = max(dynamic_min, self.adaptive.get_calibrated_min_score())
            
        if score_val < dynamic_min:
            telemetry.record_rejection(RejectionReason.LOW_SIGNAL_SCORE, regime.regime)
            return None
            
        best_signal.score = SignalScore(score=score_val, components=components)
        best_signal.regime = regime
        best_signal.intelligence = intelligence
        # Add ensemble attribution to reason instead of overwriting the specific strategy
        best_signal.reason += f" | Ensemble({','.join([s.strategy for s in signals])})"
        
        return best_signal
        
    def _score_regime_alignment(self, direction: str, regime: str) -> float:
        """
        Determines how aligned a direction is with the current regime.
        0 means strongly misaligned (veto trade).
        """
        if regime == "HIGH_VOLATILITY":
            return 10.0 # Caution
            
        if direction == "LONG":
            if regime == "TRENDING_UP":
                return 40.0
            elif regime == "TRENDING_DOWN":
                return 0.0 # Veto
            elif regime == "RANGE_BOUND":
                return 20.0
                
        elif direction == "SHORT":
            if regime == "TRENDING_DOWN":
                return 40.0
            elif regime == "TRENDING_UP":
                return 0.0 # Veto
            elif regime == "RANGE_BOUND":
                return 20.0
                
        return 0.0
