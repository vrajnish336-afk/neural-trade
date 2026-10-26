import logging
import math
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, MarketIntelligence
from app.decision.models import TraderDecision, ScenarioAnalysis
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.services.intelligence import IntelligenceService
from app.forecasting.service import ForecastingService

logger = logging.getLogger(__name__)

from app.config import config
from app.risk.drawdown import DrawdownService
from app.execution.paper_repository import PaperRepository

from app.analysis.mtf_engine import MultiTimeframeEngine

from app.intelligence.service import WorldIntelligenceService

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
        data_provider: Optional[Any] = None,
        market_data_engine: Optional[Any] = None,
        execution_adapter: Optional[Any] = None,
        mtf_engine: Optional[MultiTimeframeEngine] = None,
        world_intelligence_service: Optional[WorldIntelligenceService] = None
    ):
        self.ensemble = ensemble
        self.risk_engine = risk_engine
        self.intelligence_service = intelligence_service
        self.forecasting_service = forecasting_service
        self.paper_repository = paper_repository
        self.drawdown_service = drawdown_service
        self.weighting_service = weighting_service
        self.market_data_engine = market_data_engine
        self.data_provider = data_provider or market_data_engine
        self.execution_adapter = execution_adapter
        self.mtf_engine = mtf_engine or MultiTimeframeEngine()
        self.world_intelligence_service = world_intelligence_service
        
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
        arg3: Any = 10000.0,
        arg4: Any = 0,
        arg5: Any = 0.0,
        portfolio_id: str = "default_paper",
        **kwargs
    ) -> TraderDecision:
        if not bars:
            return self._build_no_trade(symbol, "INSUFFICIENT", "No market bars provided.")
            
        latest_bar = bars[-1]
        timestamp = latest_bar.timestamp

        # Handle flexible calling conventions (with or without as_of timestamp as 3rd arg)
        if isinstance(arg3, (datetime, str)) and isinstance(arg4, (int, float)):
            timestamp = arg3 if isinstance(arg3, datetime) else latest_bar.timestamp
            current_equity = float(arg4)
            current_positions_count = int(arg5) if isinstance(arg5, (int, float)) else 0
            current_exposure = float(kwargs.get("current_exposure", 0.0))
        else:
            current_equity = float(arg3) if isinstance(arg3, (int, float)) else 10000.0
            current_positions_count = int(arg4) if isinstance(arg4, (int, float)) else 0
            current_exposure = float(arg5) if isinstance(arg5, (int, float)) else 0.0
        
        # 1. Market Context / Regime
        from app.analysis.regime import detect_market_regime
        regime = detect_market_regime(bars)
                
        # 2. Intelligence
        intelligence = None
        try:
            intelligence = self.intelligence_service.generate_intelligence(symbol, timestamp, bars)
        except Exception as e:
            logger.warning(f"Failed to fetch intelligence: {e}")
        
        # Multi-Timeframe Synchronization via MultiTimeframeEngine & resample_bars
        from app.analysis.timeframes import resample_to_market_bars

        h4_bars = None
        d1_bars = None
        if self.data_provider:
            try:
                from datetime import timedelta
                raw_h4 = self.data_provider.get_historical_bars(symbol, "4h", start_time=timestamp - timedelta(days=30), end_time=timestamp)
                if isinstance(raw_h4, list) and raw_h4:
                    h4_bars = raw_h4
                raw_d1 = self.data_provider.get_historical_bars(symbol, "1d", start_time=timestamp - timedelta(days=100), end_time=timestamp)
                if isinstance(raw_d1, list) and raw_d1:
                    d1_bars = raw_d1
            except Exception as e:
                logger.warning(f"Failed to fetch HTF bars for {symbol}: {e}")

        # Determine bar step/frequency to avoid downsampling higher-timeframe inputs
        bar_step_seconds = 3600
        if len(bars) >= 2:
            t1 = bars[0].timestamp
            t2 = bars[1].timestamp
            delta = abs((t2 - t1).total_seconds())
            if delta > 0:
                bar_step_seconds = delta

        # If HTF bars not supplied by data_provider, synthesize from lower-timeframe bars using resample_bars
        if not h4_bars and bars and bar_step_seconds < 14400 and len(bars) >= 8:
            try:
                h4_bars = resample_to_market_bars(bars, '4h')
            except Exception as e:
                logger.warning(f"Failed to resample 4H bars for {symbol}: {e}")

        if not d1_bars and bars and bar_step_seconds < 86400 and len(bars) >= 48:
            try:
                d1_bars = resample_to_market_bars(bars, '1d')
            except Exception as e:
                logger.warning(f"Failed to resample 1D bars for {symbol}: {e}")
                
        mtf_context = self.mtf_engine.align_timeframes(
            symbol=symbol,
            current_timestamp=timestamp,
            h1_bars=bars,
            h4_bars=h4_bars,
            d1_bars=d1_bars
        )
        mtf_alignment = mtf_context.alignment
                
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
        eval_equity = current_equity
        if self.paper_repository and self.drawdown_service:
            # Dynamically compute open unrealized PnL based on latest market price
            unrealized = self.paper_repository.calculate_unrealized_pnl(
                portfolio_id, 
                current_prices={symbol: latest_bar.close}
            )
            eval_equity = current_equity + unrealized
            self.paper_repository.sync_dynamic_equity(
                portfolio_id,
                current_prices={symbol: latest_bar.close}
            )
            snapshots = self.paper_repository.get_equity_snapshots(portfolio_id, as_of=timestamp)
            dd_result = self.drawdown_service.calculate(
                snapshots, 
                has_partial_history=(len(snapshots) < 3),
                current_equity=eval_equity,
                as_of=timestamp.isoformat() if hasattr(timestamp, 'isoformat') else str(timestamp)
            )
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
            
            # 6.2 Kronos Strong-Veto Gate (LONG-specific safety filter)
            kronos_veto = False
            kronos_veto_reason = None
            if config.KRONOS_STRONG_VETO_ENABLED and signal.direction == "LONG":
                if forecast_dir == "DOWN":
                    kronos_veto = True
                    kronos_veto_reason = "Kronos predicts DOWN against new LONG signal."
                elif forecast_dir in ["UNKNOWN", "ERROR", None]:
                    kronos_veto = True
                    kronos_veto_reason = f"Kronos forecast is {forecast_dir} (fail-closed in strong-veto mode)."

            # 6.3 Blow-Off-Top Circuit Breaker (High Price + Extreme Volatility)
            circuit_breaker_veto = False
            circuit_breaker_reason = None
            price_threshold = getattr(config, "CIRCUIT_BREAKER_PRICE_THRESHOLD", 100000.0)
            
            if latest_bar.close >= price_threshold:
                is_missing_volatility = (regime is None or regime.regime == "INSUFFICIENT_DATA")
                is_high_volatility = (regime and regime.regime == "HIGH_VOLATILITY")
                
                if is_missing_volatility or is_high_volatility:
                    if "TrendFollowing" not in signal.strategy:
                        circuit_breaker_veto = True
                        circuit_breaker_reason = "Blow-Off-Top Circuit Breaker Active: Price >= Threshold and Volatility is Extreme/Missing."

            # 6.4 Multi-Timeframe Alignment Gate
            mtf_veto = False
            mtf_veto_reason = None
            is_long = signal.direction in ("LONG", "BUY")
            is_short = signal.direction in ("SHORT", "SELL")
            
            htf_trends = [t for t in (mtf_context.h4_trend, mtf_context.d1_trend) if t != "UNKNOWN"]
            
            if is_long:
                # A LONG signal should only pass if the higher timeframe is also bullish
                # (or at least not strictly bearish)
                if any(t == "BEARISH" for t in htf_trends):
                    mtf_veto = True
                    conflicts = [f"{tf} is {t}" for tf, t in [("4H", mtf_context.h4_trend), ("1D", mtf_context.d1_trend)] if t == "BEARISH"]
                    mtf_veto_reason = f"LONG signal rejected: Higher timeframe trend is conflicting ({', '.join(conflicts)})."
            elif is_short:
                # A SHORT signal should only pass if the higher timeframe is also bearish
                # (or at least not strictly bullish)
                if any(t == "BULLISH" for t in htf_trends):
                    mtf_veto = True
                    conflicts = [f"{tf} is {t}" for tf, t in [("4H", mtf_context.h4_trend), ("1D", mtf_context.d1_trend)] if t == "BULLISH"]
                    mtf_veto_reason = f"SHORT signal rejected: Higher timeframe trend is conflicting ({', '.join(conflicts)})."

            risk_decision = self.risk_engine.evaluate_trade(
                signal=signal,
                current_equity=eval_equity,
                current_positions_count=current_positions_count,
                current_exposure=current_exposure
            )
            
            if drawdown_veto:
                risk_approved = False
                risk_reason = drawdown_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Drawdown Gate: {risk_reason}"
                main_risks.append("Portfolio Drawdown Halt")
            elif kronos_veto:
                risk_approved = False
                risk_reason = kronos_veto_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Kronos Strong-Veto Gate: {risk_reason}"
                main_risks.append("Kronos Strong-Veto Halt")
            elif circuit_breaker_veto:
                risk_approved = False
                risk_reason = circuit_breaker_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Circuit Breaker: {risk_reason}"
                main_risks.append("Blow-Off-Top Circuit Breaker")
            elif mtf_veto:
                risk_approved = False
                risk_reason = mtf_veto_reason
                decision_val = "WAIT"
                rationale = f"Signal generated but blocked by Multi-Timeframe Alignment: {risk_reason}"
                main_risks.append("Multi-Timeframe Conflict")
                main_risks.append(mtf_veto_reason)
            elif not risk_decision.approved:
                risk_approved = False
                risk_reason = risk_decision.rejection_reason
                decision_val = "WAIT"
                if risk_decision.relevant_limit == "DEATH_MODE":
                    rationale = f"Signal generated but blocked by Death Mode Gate: {risk_reason}"
                    main_risks.append("Risk-Off Death Mode Halt (New Entries Blocked)")
                else:
                    rationale = f"Signal generated but blocked by Risk Gate: {risk_reason}"
                    main_risks.append("Risk limit hit")
            else:
                risk_approved = True
                risk_reason = None
        
        # Resolve World Context
        world_ctx_str = "UNKNOWN"
        if getattr(config, "MACRO_INTELLIGENCE_ENABLED", False):
            if self.world_intelligence_service:
                try:
                    w_ctx = self.world_intelligence_service.aggregate_context(as_of=timestamp)
                    if w_ctx and w_ctx.sentiment_summary is not None:
                        world_ctx_str = f"Score:{w_ctx.sentiment_summary:.2f}"
                    else:
                        world_ctx_str = "NOT_AVAILABLE"
                except Exception as e:
                    logger.warning(f"Failed to fetch WorldContext: {e}")
                    world_ctx_str = "NOT_AVAILABLE"
            else:
                world_ctx_str = "NOT_AVAILABLE"
        else:
            world_ctx_str = intelligence.sentiment.label if intelligence else "UNKNOWN"

        # Compute data_freshness dynamically by comparing latest bar's timestamp against current UTC time
        now_utc = datetime.now(timezone.utc)
        bar_ts = latest_bar.timestamp
        if getattr(bar_ts, "tzinfo", None) is None:
            bar_ts = bar_ts.replace(tzinfo=timezone.utc)
        else:
            bar_ts = bar_ts.astimezone(timezone.utc)

        age_seconds = (now_utc - bar_ts).total_seconds()
        if len(bars) < 5:
            dynamic_freshness = "INSUFFICIENT"
        elif age_seconds <= 86400 * 2:  # within 48h considered fresh
            dynamic_freshness = "FRESH"
        else:
            dynamic_freshness = "STALE"

        # Compute volatility_context logically based on price variance from the provided bars
        if len(bars) >= 2:
            closes = [b.close for b in bars]
            mean_close = sum(closes) / len(closes)
            if mean_close > 0:
                variance = sum((c - mean_close) ** 2 for c in closes) / len(closes)
                std_dev = math.sqrt(variance)
                vol_ratio = std_dev / mean_close
                if vol_ratio > 0.08:
                    computed_volatility_context = "HIGH"
                elif vol_ratio < 0.015:
                    computed_volatility_context = "LOW"
                else:
                    computed_volatility_context = "NORMAL"
            else:
                computed_volatility_context = "UNKNOWN"
        else:
            computed_volatility_context = "UNKNOWN"

        return TraderDecision(
            symbol=symbol,
            timestamp=timestamp,
            data_freshness=dynamic_freshness,
            regime=regime.regime,
            trend_context=regime.regime,
            volatility_context=computed_volatility_context,
            multi_timeframe_alignment=mtf_alignment if 'mtf_alignment' in locals() else "UNKNOWN",
            portfolio_correlation=portfolio_correlation if 'portfolio_correlation' in locals() else "UNKNOWN",
            strategy_signals=[
                {"strategy": s.strategy, "direction": s.direction} 
                for s in raw_signals 
                if not (getattr(config, "QUARANTINE_MEAN_REVERSION", True) and "MeanReversion" in s.strategy)
            ] if raw_signals else [],
            forecast_direction=forecast_dir,
            forecast_uncertainty=forecast_unc,
            world_context=world_ctx_str,
            scenario_analysis=scenarios,
            main_risks=main_risks,
            invalidation_conditions=["Stop loss hit", "Regime change"],
            rationale=rationale,
            confidence=confidence,
            decision=decision_val,
            evaluated_price=latest_bar.close,
            stop_loss=signal.stop_loss if signal else None,
            take_profit=signal.take_profit if signal else None,
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
            stop_loss=None,
            take_profit=None,
            risk_gate_approved=False,
            risk_gate_reason="No data or no signal",
            paper_execution_eligible=False
        )
