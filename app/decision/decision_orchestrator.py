import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService

logger = logging.getLogger(__name__)

from app.risk.drawdown import DrawdownService
from app.execution.paper_repository import PaperRepository

class DecisionOrchestrator:
    """
    Lightweight orchestration component that unifies Strategy, Forecasting, 
    Intelligence, and Risk into a final deterministic decision.
    """
    
    def __init__(
        self,
        ensemble: StrategyEnsemble,
        risk_engine: RiskEngine,
        intelligence_service: IntelligenceService,
        forecasting_service: ForecastingService,
        paper_repository: Optional[PaperRepository] = None,
        drawdown_service: Optional[DrawdownService] = None,
        weighting_service: Optional['StrategyWeightingService'] = None,
        data_provider: Optional[Any] = None
    ):
        self.ensemble = ensemble
        self.risk_engine = risk_engine
        self.intelligence_service = intelligence_service
        self.forecasting_service = forecasting_service
        self.paper_repository = paper_repository
        self.drawdown_service = drawdown_service
        self.weighting_service = weighting_service
        self.data_provider = data_provider
        
    def _generate_scenario_analysis(
        self, 
        regime: MarketRegimeResult, 
        forecast_direction: str, 
        signal: Optional[TradingSignal], 
        intelligence: Optional[MarketIntelligence]
    ) -> ScenarioAnalysis:
        
        bullish = "Bullish continuation if trend holds and resistance breaks."
        bearish = "Bearish reversal if support fails or momentum diverges."
        neutral = "Range-bound chop expected if volume drops."
        
        if regime.regime == "TRENDING_UP":
            bullish = "Strong bullish continuation expected based on observed uptrend."
            bearish = "Bearish pullback possible if overextended."
        elif regime.regime == "TRENDING_DOWN":
            bearish = "Strong bearish continuation expected based on observed downtrend."
            bullish = "Relief rally possible but remains bounded by downward structure."
        elif regime.regime == "HIGH_VOLATILITY":
            neutral = "Elevated volatility conditions. Whiplash risk is high."
            bullish = "Sharp upward squeeze possible."
            bearish = "Sudden crash risk due to unstable liquidity."
            
        if intelligence and intelligence.sentiment.label == "NEGATIVE":
            bearish += " Amplified by negative world intelligence."
        if intelligence and intelligence.sentiment.label == "POSITIVE":
            bullish += " Amplified by positive world intelligence."
            
        if not signal:
            bullish = "Insufficient evidence for bullish scenario."
            bearish = "Insufficient evidence for bearish scenario."
            neutral = "Conflicting or insufficient evidence leads to neutral expectation."
            
        return ScenarioAnalysis(
            bullish_scenario=bullish,
            bearish_scenario=bearish,
            neutral_scenario=neutral
        )

    def evaluate(
        self,
        symbol: str,
        bars: List[MarketBar],
        current_equity: float,
        current_positions_count: int,
        current_exposure: float,
        portfolio_id: str = "default_paper"
    ) -> TraderDecision:
        if not bars:
            return self._build_no_trade(symbol, "INSUFFICIENT", "No market bars provided.")
            
        latest_bar = bars[-1]
        timestamp = latest_bar.timestamp
        
        # 1. Market Context / Regime
        from app.analysis.regime import detect_market_regime
        regime = detect_market_regime(bars)
                
        # 2. Intelligence
        intelligence = None
        try:
            intelligence = self.intelligence_service.generate_intelligence(symbol, timestamp)
        except Exception as e:
            logger.warning(f"Failed to fetch intelligence: {e}")
        
        # Pseudo-MTF check inline on existing bars
        mtf_alignment = "UNKNOWN"
        if len(bars) >= 50:
            sma20 = sum(b.close for b in bars[-20:]) / 20
            sma50 = sum(b.close for b in bars[-50:]) / 50
            if sma20 > sma50 * 1.02:
                mtf_alignment = "ALIGNED_BULLISH"
            elif sma20 < sma50 * 0.98:
                mtf_alignment = "ALIGNED_BEARISH"
            else:
                mtf_alignment = "NEUTRAL"
                
        # Portfolio Correlation Awareness
        portfolio_correlation = "UNKNOWN"
        if self.paper_repository:
            try:
                open_positions = self.paper_repository.get_open_positions(portfolio_id)
                open_symbols = [p['symbol'] for p in open_positions if p['symbol'] != symbol]
                if not open_symbols:
                    portfolio_correlation = "LOW_CORRELATION"
                elif self.data_provider:
                    from app.analysis.correlation import calculate_historical_correlation, get_correlation_status
                    if len(bars) >= 30:
                        start_time = bars[-30].timestamp
                        symbol_data = {symbol: bars[-30:]}
                        for osym in open_symbols:
                            obars = self.data_provider.get_historical_bars(
                                symbol=osym, 
                                timeframe="1D", # Simplified for evaluation
                                start_time=start_time,
                                end_time=timestamp
                            )
                            if obars:
                                symbol_data[osym] = obars
                        
                        corr_matrix = calculate_historical_correlation(symbol_data, min_periods=10)
                        
                        max_corr_status = "LOW_CORRELATION"
                        for osym in open_symbols:
                            status = get_correlation_status(corr_matrix, symbol, osym, threshold=0.7)
                            if status == "HIGH_CORRELATION":
                                max_corr_status = "HIGH_CORRELATION"
                                break
                            elif status == "INSUFFICIENT_DATA" and max_corr_status != "HIGH_CORRELATION":
                                max_corr_status = "INSUFFICIENT_DATA"
                                
                        portfolio_correlation = max_corr_status
                    else:
                        portfolio_correlation = "INSUFFICIENT_DATA"
                else:
                    portfolio_correlation = "UNKNOWN_NO_DATA"
            except Exception as e:
                logger.warning(f"Failed correlation check: {e}")
                portfolio_correlation = "INSUFFICIENT_DATA"
        
        # 3. Strategy Signals
        raw_signals = []
        if hasattr(self.ensemble, "strategies"):
            for strategy in self.ensemble.strategies:
                sig = strategy.generate_signal(bars)
                if sig:
                    # Add default strategy attribution if missing
                    if not sig.strategy:
                        sig.strategy = strategy.__class__.__name__
                    raw_signals.append(sig)
                
        # 3.5 Bounded Weighting
        if self.weighting_service and raw_signals:
            weights = self.weighting_service.calculate_weights(raw_signals, timestamp, current_mtf=mtf_alignment, current_corr=portfolio_correlation)
            for sig in raw_signals:
                w_res = weights.get(sig.strategy)
                if w_res:
                    # Apply weight to base confidence (clamped to 1.0)
                    sig.confidence = min(1.0, sig.confidence * w_res.weight_multiplier)
                    # Expose reasoning
                    sig.reason += f" [Weight: {w_res.weight_multiplier:.2f}x - {w_res.reason}]"
                    
        signal = self.ensemble.evaluate(bars, regime, intelligence, pre_generated_signals=raw_signals if raw_signals else None)
        
        # 4. Forecast
        forecast_dir = "UNKNOWN"
        forecast_unc = 1.0
        try:
            forecast_rec = self.forecasting_service.generate_forecast(symbol, "1D", min(100, len(bars)), 5, model_choice="kronos")
            if forecast_rec and forecast_rec.predicted_values_json:
                import json
                preds = json.loads(forecast_rec.predicted_values_json)
                if preds and len(preds) > 0:
                    if preds[-1] > latest_bar.close:
                        forecast_dir = "UP"
                    else:
                        forecast_dir = "DOWN"
                    forecast_unc = 0.5
        except Exception as e:
            logger.warning(f"Forecast failed: {e}")
            
        # 5. Scenarios
        scenarios = self._generate_scenario_analysis(regime, forecast_dir, signal, intelligence)
        
        # 5.5 Portfolio Drawdown Risk Check
        drawdown_veto = False
        drawdown_reason = None
        if self.paper_repository and self.drawdown_service:
            snapshots = self.paper_repository.get_equity_snapshots(portfolio_id, as_of=timestamp)
            dd_result = self.drawdown_service.calculate(snapshots, has_partial_history=(len(snapshots) < 3))
            dd_approved, dd_reason = self.risk_engine.check_drawdown(dd_result)
            if not dd_approved:
                drawdown_veto = True
                drawdown_reason = dd_reason
        
        # 6. Risk Gate & Decision
        decision_val = "NO TRADE"
        risk_approved = False
        risk_reason = None
        main_risks = ["Market risk"]
        rationale = "No strategy signal generated."
        confidence = 0.0
        
        if signal:
            decision_val = signal.direction
            rationale = signal.reason
            confidence = signal.confidence
            
            # 6.1 Kronos Secondary Evidence (bounded, deterministic)
            # Forecast agreement/disagreement adjusts confidence by at most 0.05.
            # UNKNOWN or unavailable forecast has zero effect.
            KRONOS_MAX_BOOST = 0.05
            forecast_agrees = (
                (forecast_dir == "UP" and signal.direction == "LONG") or
                (forecast_dir == "DOWN" and signal.direction == "SHORT")
            )
            forecast_conflicts = (
                (forecast_dir == "UP" and signal.direction == "SHORT") or
                (forecast_dir == "DOWN" and signal.direction == "LONG")
            )
            if forecast_agrees:
                confidence = min(1.0, confidence + KRONOS_MAX_BOOST)
                rationale += f" [Kronos forecast confirms {forecast_dir}]"
            elif forecast_conflicts:
                confidence = max(0.0, confidence - KRONOS_MAX_BOOST)
                rationale += f" [Kronos forecast conflicts: {forecast_dir}]"
            # else: forecast_dir is UNKNOWN — no adjustment
            
            risk_decision = self.risk_engine.evaluate_trade(
                signal=signal,
                current_equity=current_equity,
                current_positions_count=current_positions_count,
                current_exposure=current_exposure
            )
            
            if drawdown_veto:
                risk_approved = False
                risk_reason = drawdown_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Drawdown Gate: {risk_reason}"
                main_risks.append("Portfolio Drawdown Halt")
            elif not risk_decision.approved:
                risk_approved = False
                risk_reason = risk_decision.rejection_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Risk Gate: {risk_reason}"
                main_risks.append("Risk limit hit")
            else:
                risk_approved = True
                risk_reason = None
        
        return TraderDecision(
            symbol=symbol,
            timestamp=timestamp,
            data_freshness="FRESH",
            regime=regime.regime,
            trend_context=regime.regime,
            volatility_context="NORMAL",
            multi_timeframe_alignment=mtf_alignment if 'mtf_alignment' in locals() else "UNKNOWN",
            portfolio_correlation=portfolio_correlation if 'portfolio_correlation' in locals() else "UNKNOWN",
            strategy_signals=[{"strategy": s.strategy, "direction": s.direction} for s in raw_signals] if raw_signals else [],
            forecast_direction=forecast_dir,
            forecast_uncertainty=forecast_unc,
            world_context=intelligence.sentiment.label if intelligence else "UNKNOWN",
            scenario_analysis=scenarios,
            main_risks=main_risks,
            invalidation_conditions=["Stop loss hit", "Regime change"],
            rationale=rationale,
            confidence=confidence,
            decision=decision_val,
            evaluated_price=latest_bar.close,
            risk_gate_approved=risk_approved,
            risk_gate_reason=risk_reason,
            paper_execution_eligible=risk_approved,
            strategy_weighting_audit={
                k: {
                    "weight_multiplier": v.weight_multiplier, 
                    "reason": v.reason, 
                    "evidence_age_days": v.evidence_age_days,
                    "meta_conclusion": v.meta_conclusion.model_dump() if hasattr(v, 'meta_conclusion') and v.meta_conclusion else None
                } for k,v in weights.items()
            } if 'weights' in locals() else {}
        )
        
    def _build_no_trade(self, symbol: str, freshness: str, rationale: str) -> TraderDecision:
        return TraderDecision(
            symbol=symbol,
            timestamp=datetime.utcnow(),
            data_freshness=freshness,
            regime="UNKNOWN",
            trend_context="UNKNOWN",
            volatility_context="UNKNOWN",
            multi_timeframe_alignment="UNKNOWN",
            strategy_signals=[],
            forecast_direction="UNKNOWN",
            forecast_uncertainty=1.0,
            world_context="UNKNOWN",
            scenario_analysis=ScenarioAnalysis(
                bullish_scenario="N/A", bearish_scenario="N/A", neutral_scenario="N/A"
            ),
            main_risks=[],
            invalidation_conditions=[],
            rationale=rationale,
            confidence=0.0,
            decision="NO TRADE",
            evaluated_price=0.0,
            risk_gate_approved=False,
            risk_gate_reason="No data or no signal",
            paper_execution_eligible=False
        )
