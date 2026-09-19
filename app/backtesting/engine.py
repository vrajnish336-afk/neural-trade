import logging
from typing import List, Optional, Dict
from datetime import datetime

from app.core.models import MarketBar, TradingSignal, RiskDecision
from datetime import datetime, timezone

from app.core.models import MarketBar, TradingSignal, RiskDecision, MarketRegimeResult, MarketIntelligence
from app.strategies.base import Strategy
from app.strategies.ensemble import StrategyEnsemble
from app.analysis.regime import detect_market_regime
from app.backtesting.models import BacktestResult, BacktestTrade, CostConfig
from app.backtesting.costs import apply_entry_costs, apply_exit_costs
from app.backtesting.metrics import calculate_drawdown, calculate_profit_factor
from app.analysis.signal_validation import is_valid_signal
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

from app.risk.portfolio import PortfolioRiskManager, PortfolioRiskConfig
from app.diagnostics.models import RejectionReason

logger = logging.getLogger(__name__)

class BacktestEngine:
    """
    Deterministic event-based historical backtesting engine.
    Simulates chronological progression strictly to prevent look-ahead bias.
    Fully integrated with RiskEngine, StrategyEnsemble, and Regime Detection.
    """
    def __init__(
        self,
        ensemble: StrategyEnsemble,
        risk_engine: RiskEngine,
        intelligence_service = None,
        initial_capital: float = 10000.0,
        cost_config: Optional[CostConfig] = None,
        portfolio_config: Optional[PortfolioRiskConfig] = None
    ):
        self.ensemble = ensemble
        self.risk_engine = risk_engine
        self.intelligence_service = intelligence_service
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.current_capital = initial_capital
        self.cost_config = cost_config or CostConfig()
        self.portfolio = PortfolioRiskManager(portfolio_config or PortfolioRiskConfig())
        
        # Internal state
        self.equity_curve: List[dict] = []
        self.closed_trades: List[BacktestTrade] = []
        self.current_day: Optional[datetime] = None
        
        # Risk tracking & Metrics
        self.risk_engine.limits.initial_equity = initial_capital
        self.peak_equity = initial_capital
        self.max_drawdown = 0.0

    def run(self, bars: List[MarketBar]) -> BacktestResult:
        logger.info("Starting backtest with %d bars.", len(bars))
        
        if not bars:
            return self._generate_empty_result()
            
        symbol_history = {bar.symbol: [] for bar in bars}
            
        for current_bar in bars:
            symbol_history[current_bar.symbol].append(current_bar)
            historical_slice = symbol_history[current_bar.symbol]
            
            # Daily resets
            if self.current_day is None or current_bar.timestamp.date() != self.current_day:
                self.current_day = current_bar.timestamp.date()
                self.risk_engine.limits.reset_daily_loss()
                
            self.risk_engine.limits.step_bar()
            
            # Step 1: Manage Open Positions
            self._evaluate_exits(current_bar)
            
            # Step 2: New Opportunities
            has_symbol_position = any(p['symbol'] == current_bar.symbol for p in self.portfolio.state.open_positions)
            if not has_symbol_position:
                from app.diagnostics.telemetry import telemetry
                telemetry.record_stage("MARKET_BARS")
                
                regime_result = detect_market_regime(historical_slice)
                telemetry.record_regime(regime_result.regime)
                
                intelligence = None
                if self.intelligence_service:
                    intelligence = self.intelligence_service.generate_intelligence(
                        symbol=current_bar.symbol,
                        timestamp=current_bar.timestamp,
                        bars=historical_slice,
                        signal=None
                    )
                
                signal = self.ensemble.evaluate(historical_slice, regime_result, intelligence)
                
                if signal:
                    # If we got a signal and have intelligence, update fakeout risk
                    if self.intelligence_service:
                        from app.analysis.fakeout import assess_breakout_quality
                        if signal.entry_price:
                            fakeout = assess_breakout_quality(historical_slice, signal.direction, signal.entry_price)
                            intelligence.fakeout_risk = fakeout
                            signal.intelligence = intelligence
                            if fakeout == "POSSIBLE_FAKEOUT":
                                logger.debug("Signal rejected due to POSSIBLE_FAKEOUT.")
                                telemetry.record_rejection(RejectionReason.FAKEOUT_FILTER)
                                signal = None # Veto
                                
                if signal:
                    if signal.stop_loss is None or signal.entry_price is None:
                        telemetry.record_rejection(RejectionReason.MISSING_SL_OR_ENTRY)
                        logger.debug("Signal missing SL or entry price, rejected by engine.")
                    else:
                        current_exposure = sum(p['quantity'] * p['entry_price'] for p in self.portfolio.state.open_positions)
                        decision = self.risk_engine.evaluate_trade(
                            signal=signal,
                            current_equity=self.equity,
                            current_positions_count=len(self.portfolio.state.open_positions),
                            current_exposure=current_exposure
                        )
                        
                        if decision.approved:
                            port_approved, port_reason, port_limit = self.portfolio.can_open_position(signal, decision.position_size, self.equity)
                            if port_approved:
                                telemetry.record_stage("RISK_APPROVED")
                                self._enter_position(signal, current_bar, decision)
                                telemetry.record_stage("PAPER_TRADES")
                            else:
                                reason_code = getattr(RejectionReason, port_limit, RejectionReason.OTHER)
                                telemetry.record_rejection(reason_code)
                                logger.debug("Trade rejected by Portfolio: %s", port_reason)
                        else:
                            logger.debug("Trade rejected by Risk Engine: %s", decision.rejection_reason)
                            
            # Update equity curve
            mtm_equity = self.equity
            for pos in self.portfolio.state.open_positions:
                if pos['direction'] == 'LONG':
                    unrealized_pnl = (current_bar.close - pos['entry_price']) * pos['quantity']
                else:
                    unrealized_pnl = (pos['entry_price'] - current_bar.close) * pos['quantity']
                mtm_equity += unrealized_pnl
                
            self.equity_curve.append({
                'timestamp': current_bar.timestamp.isoformat(),
                'equity': mtm_equity,
                'cash': self.equity,
                'exposure': mtm_equity - self.equity
            })

        for pos in list(self.portfolio.state.open_positions):
            self._force_close_position(pos, bars[-1], reason="End of backtest")
            
        logger.info("Backtest completed. Final equity: %.2f", self.equity)
        return self._generate_result()

    def _evaluate_exits(self, current_bar: MarketBar) -> None:
        pos_list = [p for p in self.portfolio.state.open_positions if p['symbol'] == current_bar.symbol]
        for pos in pos_list:
            sl_hit = False
            tp_hit = False
            exit_price = None
            
            if pos['direction'] == 'LONG':
                # Gap stress: open price gap through stop
                if pos['stop_loss'] and current_bar.open < pos['stop_loss']:
                    sl_hit = True
                    exit_price = current_bar.open
                elif pos['stop_loss'] and current_bar.low <= pos['stop_loss']:
                    sl_hit = True
                    exit_price = pos['stop_loss']
                    
                # Gap through target
                if pos['take_profit'] and current_bar.open > pos['take_profit']:
                    tp_hit = True
                    exit_price = current_bar.open if not exit_price else exit_price
                elif pos['take_profit'] and current_bar.high >= pos['take_profit']:
                    tp_hit = True
                    exit_price = pos['take_profit'] if not exit_price else exit_price
            else:
                if pos['stop_loss'] and current_bar.open > pos['stop_loss']:
                    sl_hit = True
                    exit_price = current_bar.open
                elif pos['stop_loss'] and current_bar.high >= pos['stop_loss']:
                    sl_hit = True
                    exit_price = pos['stop_loss']
                    
                if pos['take_profit'] and current_bar.open < pos['take_profit']:
                    tp_hit = True
                    exit_price = current_bar.open if not exit_price else exit_price
                elif pos['take_profit'] and current_bar.low <= pos['take_profit']:
                    tp_hit = True
                    exit_price = pos['take_profit'] if not exit_price else exit_price

            if sl_hit and tp_hit:
                # Same-bar ambiguity assumed worst -> Stop Loss
                # Gap-through-stop price is used if it was a gap.
                exit_price = exit_price if exit_price is not None else pos['stop_loss']
                self._close_position(current_bar.timestamp, exit_price, pos, "Stop Loss (Ambiguity assumed Worst)")
            elif sl_hit:
                self._close_position(current_bar.timestamp, exit_price, pos, "Stop Loss")
            elif tp_hit:
                self._close_position(current_bar.timestamp, exit_price, pos, "Take Profit")

    def _enter_position(self, signal: TradingSignal, bar: MarketBar, decision: RiskDecision) -> None:
        quantity = decision.position_size
        target_price = signal.entry_price or bar.close
        
        actual_price, comm, slippage = apply_entry_costs(target_price, quantity, signal.direction, self.cost_config)
        
        # Slippage is embedded in actual_price, so only commission is a separate cash deduction
        self.equity -= comm
        
        pos = {
            'symbol': signal.symbol,
            'direction': signal.direction,
            'entry_time': signal.timestamp,
            'entry_price': actual_price,
            'quantity': quantity,
            'stop_loss': signal.stop_loss,
            'take_profit': signal.take_profit,
            'entry_cost': comm,
            'slippage_entry': slippage,
            'signal_metadata': {
                'regime': signal.regime.regime if signal.regime else None,
                'score': signal.score.score if signal.score else None,
                'strategies': signal.strategy,
                'sentiment_label': signal.intelligence.sentiment.label if signal.intelligence and signal.intelligence.sentiment else None,
                'anomaly_flags': ",".join(signal.intelligence.anomaly_status) if signal.intelligence and signal.intelligence.anomaly_status else None,
                'fakeout_risk': signal.intelligence.fakeout_risk if signal.intelligence else None
            }
        }
        self.portfolio.state.add_position(pos)

    def _close_position(self, exit_time: datetime, exit_price: float, pos: Dict, reason: str) -> None:
            
        actual_price, comm, slippage = apply_exit_costs(exit_price, pos['quantity'], pos['direction'], self.cost_config)
        
        if pos['direction'] == 'LONG':
            gross_pnl = (actual_price - pos['entry_price']) * pos['quantity']
        else:
            gross_pnl = (pos['entry_price'] - actual_price) * pos['quantity']
            
        # Slippage is embedded in actual_price, so only commission reduces net PnL further
        net_pnl = gross_pnl - comm
        self.equity += net_pnl
        
        trade = BacktestTrade(
            symbol=pos['symbol'],
            direction=pos['direction'],
            entry_time=pos['entry_time'],
            entry_price=pos['entry_price'],
            exit_time=exit_time,
            exit_price=actual_price,
            quantity=pos['quantity'],
            entry_cost=pos['entry_cost'],
            exit_cost=comm,
            slippage_cost=pos['slippage_entry'] + slippage,
            realized_pnl=net_pnl,
            exit_reason=reason,
            regime=pos['signal_metadata'].get('regime'),
            score=pos['signal_metadata'].get('score'),
            strategies=pos['signal_metadata'].get('strategies'),
            sentiment_label=pos['signal_metadata'].get('sentiment_label'),
            anomaly_flags=pos['signal_metadata'].get('anomaly_flags'),
            fakeout_risk=pos['signal_metadata'].get('fakeout_risk')
        )
        self.closed_trades.append(trade)
        
        # Update risk limits
        self.risk_engine.limits.update_from_closed_trade(trade)
        
        # Online Learning / Adaptive Feedback (No Look-ahead!)
        if hasattr(self, 'ensemble') and hasattr(self.ensemble, 'adaptive') and self.ensemble.adaptive:
            self.ensemble.adaptive.record_trade(trade)
            
        self.portfolio.state.remove_position(pos['symbol'], pos['direction'])

    def _force_close_position(self, pos: Dict, current_bar: MarketBar, reason: str) -> None:
        self._close_position(current_bar.timestamp, current_bar.close, pos, reason)

    def _generate_result(self) -> BacktestResult:
        if not self.closed_trades:
            return self._generate_empty_result()
            
        winning_trades = [t for t in self.closed_trades if t.realized_pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.realized_pnl <= 0]
        
        gross_profit = sum(t.realized_pnl for t in winning_trades)
        gross_loss = abs(sum(t.realized_pnl for t in losing_trades))
        net_profit = gross_profit - gross_loss
        
        total_return_pct = ((self.equity - self.initial_capital) / self.initial_capital) * 100
        win_rate = (len(winning_trades) / len(self.closed_trades)) * 100
        
        holding_periods = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self.closed_trades]
        avg_holding = sum(holding_periods) / len(holding_periods) if holding_periods else 0.0
        
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_equity=self.equity,
            total_return_pct=total_return_pct,
            number_of_trades=len(self.closed_trades),
            winning_trades=len(winning_trades),
            losing_trades=len(losing_trades),
            win_rate=win_rate,
            gross_profit=gross_profit,
            gross_loss=gross_loss,
            net_profit=net_profit,
            max_drawdown_pct=calculate_drawdown([pt['equity'] for pt in self.equity_curve]),
            average_trade_result=net_profit / len(self.closed_trades),
            profit_factor=calculate_profit_factor(gross_profit, gross_loss),
            average_holding_period_hours=avg_holding,
            trades=self.closed_trades,
            telemetry_snapshot=telemetry.export_snapshot() if 'telemetry' in globals() or 'telemetry' in locals() else __import__('app.diagnostics.telemetry', fromlist=['telemetry']).telemetry.export_snapshot()
        )

    def _generate_empty_result(self) -> BacktestResult:
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_equity=self.initial_capital,
            total_return_pct=0.0,
            number_of_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            gross_profit=0.0,
            gross_loss=0.0,
            net_profit=0.0,
            max_drawdown_pct=0.0,
            average_trade_result=0.0,
            profit_factor=0.0,
            average_holding_period_hours=0.0,
            trades=[],
            telemetry_snapshot=__import__('app.diagnostics.telemetry', fromlist=['telemetry']).telemetry.export_snapshot()
        )
