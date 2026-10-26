import logging
from typing import Optional, List
from datetime import datetime
from app.core.models import MarketBar, TradingSignal
from app.decision.models import TraderDecision
from app.risk.portfolio import PortfolioState
from app.execution.paper_repository import PaperRepository
from app.backtesting.models import CostConfig
from app.backtesting.costs import apply_entry_costs, apply_exit_costs
from app.risk.engine import RiskEngine

logger = logging.getLogger(__name__)

class ExecutionSafetyException(Exception):
    pass

def calculate_take_profit_1_to_3(entry_price: float, stop_loss: float, direction: str) -> float:
    """
    Calculates 1:3 Risk-to-Reward ratio take profit:
    Risk = abs(entry_price - stop_loss)
    Target Take Profit = entry_price + (3 * Risk) for BUY/LONG
                       = entry_price - (3 * Risk) for SELL/SHORT
    """
    risk = abs(entry_price - stop_loss)
    if direction.upper() in ("LONG", "BUY"):
        return entry_price + (3.0 * risk)
    else:
        return max(0.01, entry_price - (3.0 * risk))

class StreamingPaperBroker:
    """
    Streaming paper execution adapter backed by `PaperRepository`.
    Executes simulated trades safely and idempotently.
    Enforces passed-in RiskEngine authority as the final pre-trade validation.
    """
    
    def __init__(self, repository: PaperRepository, risk_engine: RiskEngine, cost_config: CostConfig = CostConfig(), portfolio_id: str = "default_paper"):
        if not risk_engine:
            raise ValueError("StreamingPaperBroker requires an authoritative RiskEngine instance.")
        self.repo = repository
        self.risk_engine = risk_engine
        self.cost_config = cost_config
        self.portfolio_id = portfolio_id
        self.latest_prices: dict = {}
        
        # Ensure portfolio exists
        self.repo.get_or_create_portfolio(self.portfolio_id)

    def get_realtime_portfolio(self) -> PortfolioState:
        """
        Retrieves the persistent paper portfolio state.
        """
        rows = self.repo.get_open_positions(self.portfolio_id)
        portfolio = self.repo.get_or_create_portfolio(self.portfolio_id)
        cash = float(portfolio['current_cash']) if 'current_cash' in portfolio.keys() else float(portfolio['current_equity'])
        state = PortfolioState(current_cash=cash)
        for r in rows:
            # Handle backwards compatibility for unmigrated rows
            strategy = r['strategy'] if 'strategy' in r.keys() else None
            state.add_position({
                'position_id': r['position_id'],
                'symbol': r['symbol'],
                'direction': r['direction'],
                'entry_time': r['entry_time'],
                'entry_price': r['entry_price'],
                'quantity': r['quantity'],
                'stop_loss': r['stop_loss'],
                'take_profit': r['take_profit'],
                'current_price': self.latest_prices.get(r['symbol']),
                'signal_metadata': {'strategies': strategy}
            })
        return state

    def monitor_positions(self, current_bar: MarketBar) -> List[dict]:
        """
        Runtime SL/TP monitoring: evaluates open positions against current_bar.
        Automatically executes exits when target or stop-loss is touched,
        logging with proper exit reason: SL_HIT or TP_HIT.
        """
        self.latest_prices[current_bar.symbol] = current_bar.close
        self.repo.sync_dynamic_equity(self.portfolio_id, current_prices=self.latest_prices)
        exits_executed = []
        open_pos = [p for p in self.repo.get_open_positions(self.portfolio_id) if p['symbol'] == current_bar.symbol]
        
        for pos in open_pos:
            sl_hit = False
            tp_hit = False
            exit_price = None
            
            if pos['direction'] == 'LONG':
                if pos['stop_loss'] is not None and current_bar.open < pos['stop_loss']:
                    sl_hit = True
                    exit_price = current_bar.open
                elif pos['stop_loss'] is not None and current_bar.low <= pos['stop_loss']:
                    sl_hit = True
                    exit_price = pos['stop_loss']
                    
                if pos['take_profit'] is not None and current_bar.open > pos['take_profit']:
                    tp_hit = True
                    exit_price = current_bar.open if not exit_price else exit_price
                elif pos['take_profit'] is not None and current_bar.high >= pos['take_profit']:
                    tp_hit = True
                    exit_price = pos['take_profit'] if not exit_price else exit_price
            else: # SHORT
                if pos['stop_loss'] is not None and current_bar.open > pos['stop_loss']:
                    sl_hit = True
                    exit_price = current_bar.open
                elif pos['stop_loss'] is not None and current_bar.high >= pos['stop_loss']:
                    sl_hit = True
                    exit_price = pos['stop_loss']
                    
                if pos['take_profit'] is not None and current_bar.open < pos['take_profit']:
                    tp_hit = True
                    exit_price = current_bar.open if not exit_price else exit_price
                elif pos['take_profit'] is not None and current_bar.low <= pos['take_profit']:
                    tp_hit = True
                    exit_price = pos['take_profit'] if not exit_price else exit_price
                    
            if sl_hit and tp_hit:
                # Same-bar conflict: conservative worst-case Stop Loss
                exit_price = exit_price if exit_price is not None else pos['stop_loss']
                success = self.execute_exit(pos['position_id'], exit_price, current_bar.timestamp, reason="SL_HIT")
                exits_executed.append({"position_id": pos['position_id'], "reason": "SL_HIT", "price": exit_price, "success": success})
            elif sl_hit:
                success = self.execute_exit(pos['position_id'], exit_price, current_bar.timestamp, reason="SL_HIT")
                exits_executed.append({"position_id": pos['position_id'], "reason": "SL_HIT", "price": exit_price, "success": success})
            elif tp_hit:
                success = self.execute_exit(pos['position_id'], exit_price, current_bar.timestamp, reason="TP_HIT")
                exits_executed.append({"position_id": pos['position_id'], "reason": "TP_HIT", "price": exit_price, "success": success})
                
        return exits_executed

    def execute_decision(self, decision: TraderDecision, position_size: float, stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> bool:
        """
        Processes a single point-in-time TraderDecision.
        Uses injected self.risk_engine as authoritative pre-trade validation.
        """
        actual_strategy = "PaperBroker"
        if decision.strategy_signals:
            actual_strategy = ",".join(sorted(set(s.get("strategy", "Unknown") for s in decision.strategy_signals)))
            
        decision_id = self.repo.generate_decision_id(
            decision.symbol, 
            decision.timestamp, 
            decision=decision.decision, 
            strategy_name=actual_strategy
        )
            
        if decision.decision in ("WAIT", "NO TRADE"):
            logger.info(f"Execution rejected: Decision is {decision.decision}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, f"Decision is {decision.decision}", decision.timestamp, actual_strategy, decision.regime)
            return False
            
        if not decision.risk_gate_approved:
            logger.info(f"Execution rejected: Risk gate not approved for {decision.symbol}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, "Risk gate not approved", decision.timestamp, actual_strategy, decision.regime)
            return False
            
        # Re-evaluate Risk against current persistent state before execution
        portfolio = self.repo.get_or_create_portfolio(self.portfolio_id)
        current_equity = portfolio['current_equity']
        state = self.get_realtime_portfolio()

        # Check for Signal Reversal on existing opposite position for the same symbol
        for p in state.open_positions:
            if p['symbol'] == decision.symbol:
                is_opposite = (p['direction'] == 'LONG' and decision.decision in ('SHORT', 'SELL')) or \
                              (p['direction'] == 'SHORT' and decision.decision in ('LONG', 'BUY'))
                if is_opposite:
                    logger.info(f"Signal reversal detected for {decision.symbol}. Closing existing {p['direction']} position.")
                    self.execute_exit(
                        position_id=p['position_id'],
                        exit_price=decision.evaluated_price,
                        timestamp=decision.timestamp,
                        reason="SIGNAL_REVERSAL"
                    )
        # Refresh state and open positions after any reversal exits
        state = self.get_realtime_portfolio()

        # Dynamically calculate and sync true dynamic equity (Cash + Open Unrealized PnL)
        price_map = dict(self.latest_prices)
        if decision.evaluated_price and decision.evaluated_price > 0:
            price_map[decision.symbol] = decision.evaluated_price
            self.latest_prices[decision.symbol] = decision.evaluated_price

        current_equity = self.repo.sync_dynamic_equity(self.portfolio_id, current_prices=price_map)
        current_exposure = sum(p['quantity'] * p['entry_price'] for p in state.open_positions)
        
        # Align SL / TP with 1:3 RR if not explicitly set
        if stop_loss is None and decision.stop_loss is not None:
            stop_loss = decision.stop_loss
        if take_profit is None:
            if decision.take_profit is not None:
                take_profit = decision.take_profit
            elif stop_loss is not None and decision.evaluated_price is not None:
                take_profit = calculate_take_profit_1_to_3(decision.evaluated_price, stop_loss, decision.decision)

        dummy_signal = TradingSignal(
            symbol=decision.symbol, timestamp=decision.timestamp, direction=decision.decision,
            strategy=actual_strategy, confidence=decision.confidence, reason=decision.rationale,
            entry_price=decision.evaluated_price,
            stop_loss=stop_loss, take_profit=take_profit
        )
        
        # Hydrate limits from paper repository before evaluating
        closed_positions = self.repo.get_closed_positions(self.portfolio_id, limit=1000)
        self.risk_engine.limits.rehydrate_from_paper_ledger(closed_positions, as_of=decision.timestamp)
        
        # Calculate current drawdown for RiskEngine check using true dynamic equity
        snapshots = self.repo.get_equity_snapshots(self.portfolio_id)
        from app.risk.drawdown import DrawdownService, DrawdownStatus
        dd_svc = DrawdownService()
        dd_result = dd_svc.calculate(
            snapshots, 
            has_partial_history=(len(snapshots) < 3),
            current_equity=current_equity,
            as_of=decision.timestamp.isoformat() if hasattr(decision.timestamp, 'isoformat') else str(decision.timestamp)
        )
        
        dd_approved, dd_reason = self.risk_engine.check_drawdown(dd_result)
        if not dd_approved:
            logger.warning(f"Authoritative RiskEngine drawdown veto: {dd_reason}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, f"RiskEngine: {dd_reason}", decision.timestamp, actual_strategy, decision.regime)
            return False
            
        current_dd_pct = dd_result.current_drawdown_pct / 100.0 if dd_result.status == DrawdownStatus.OK else 0.0

        risk_decision = self.risk_engine.evaluate_trade(
            signal=dummy_signal,
            current_equity=current_equity,
            current_positions_count=len(state.open_positions),
            current_exposure=current_exposure,
            current_drawdown=current_dd_pct,
            current_loss_streak=self.risk_engine.limits.loss_streak
        )
        
        if not risk_decision.approved:
            logger.warning(f"Authoritative RiskEngine rejected execution: {risk_decision.rejection_reason}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, f"RiskEngine: {risk_decision.rejection_reason}", decision.timestamp, actual_strategy, decision.regime)
            return False
            
        final_position_size = risk_decision.position_size
        if final_position_size <= 0:
            logger.warning(f"RiskEngine approved trade but returned invalid position size: {final_position_size}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, "Invalid zero position size", decision.timestamp, actual_strategy, decision.regime)
            return False
            
        # Calculate unrealized PnL based on the price of the symbol being traded (if an open position exists for it)
        unrealized_pnl = 0.0
        for p in state.open_positions:
            if p['symbol'] == decision.symbol:
                if p['direction'] == 'LONG':
                    unrealized_pnl += (decision.evaluated_price - p['entry_price']) * p['quantity']
                else:
                    unrealized_pnl += (p['entry_price'] - decision.evaluated_price) * p['quantity']
            
        # Execute
        actual_price, commission, slippage = apply_entry_costs(
            decision.evaluated_price, final_position_size, decision.decision, self.cost_config
        )
        
        return self.repo.execute_order(
            portfolio_id=self.portfolio_id,
            decision_id=decision_id,
            symbol=decision.symbol,
            direction=decision.decision,
            quantity=final_position_size,
            price=decision.evaluated_price,
            actual_price=actual_price,
            commission=commission,
            slippage=slippage,
            timestamp=decision.timestamp,
            stop_loss=stop_loss,
            take_profit=take_profit,
            strategy=actual_strategy,
            unrealized_pnl=unrealized_pnl,
            regime=decision.regime
        )

    def execute_exit(self, position_id: str, exit_price: float, timestamp: datetime, reason: str = "MANUAL_EXIT") -> bool:
        """
        Exits a specific open position by its position_id.
        Returns True if closed successfully, False otherwise.
        """
        # Find the specific position
        positions = self.repo.get_open_positions(self.portfolio_id)
        pos = next((p for p in positions if p['position_id'] == position_id), None)
        
        if not pos:
            logger.info(f"No open position found with ID {position_id}")
            return False
            
        actual_price, commission, slippage = apply_exit_costs(
            exit_price, pos['quantity'], pos['direction'], self.cost_config
        )
        
        unrealized_pnl = 0.0
        for p in positions:
            if p['symbol'] == pos['symbol'] and p['position_id'] != position_id:
                if p['direction'] == 'LONG':
                    unrealized_pnl += (exit_price - p['entry_price']) * p['quantity']
                else:
                    unrealized_pnl += (p['entry_price'] - exit_price) * p['quantity']

        success = self.repo.execute_exit(
            portfolio_id=self.portfolio_id,
            position_id=position_id,
            exit_price=exit_price,
            actual_price=actual_price,
            commission=commission,
            slippage=slippage,
            timestamp=timestamp,
            unrealized_pnl=unrealized_pnl,
            reason=reason
        )
        if success:
            self.latest_prices[pos['symbol']] = exit_price
            self.repo.sync_dynamic_equity(self.portfolio_id, current_prices=self.latest_prices)
        return success
