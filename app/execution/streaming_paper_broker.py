import logging
from typing import Optional
from datetime import datetime
from app.decision.models import TraderDecision
from app.risk.portfolio import PortfolioState
from app.execution.paper_repository import PaperRepository
from app.backtesting.models import CostConfig
from app.backtesting.costs import apply_entry_costs
from app.risk.engine import RiskEngine

logger = logging.getLogger(__name__)

class ExecutionSafetyException(Exception):
    pass

class StreamingPaperBroker:
    """
    Streaming paper execution adapter backed by `PaperRepository`.
    Executes simulated trades safely and idempotently.
    """
    
    def __init__(self, repository: PaperRepository, risk_engine: RiskEngine, cost_config: CostConfig = CostConfig(), portfolio_id: str = "default_paper"):
        self.repo = repository
        self.risk_engine = risk_engine
        self.cost_config = cost_config
        self.portfolio_id = portfolio_id
        
        # Ensure portfolio exists
        self.repo.get_or_create_portfolio(self.portfolio_id)

    def get_realtime_portfolio(self) -> PortfolioState:
        """
        Retrieves the persistent paper portfolio state.
        """
        rows = self.repo.get_open_positions(self.portfolio_id)
        state = PortfolioState()
        for r in rows:
            # Handle backwards compatibility for unmigrated rows
            strategy = r['strategy'] if 'strategy' in r.keys() else None
            state.add_position({
                'symbol': r['symbol'],
                'direction': r['direction'],
                'entry_time': r['entry_time'],
                'entry_price': r['entry_price'],
                'quantity': r['quantity'],
                'stop_loss': r['stop_loss'],
                'take_profit': r['take_profit'],
                'signal_metadata': {'strategies': strategy}
            })
        return state

    def execute_decision(self, decision: TraderDecision, position_size: float, stop_loss: Optional[float] = None, take_profit: Optional[float] = None) -> bool:
        """
        Processes a single point-in-time TraderDecision.
        """
        decision_id = self.repo.generate_decision_id(decision.symbol, decision.timestamp)
        actual_strategy = "PaperBroker"
        if decision.strategy_signals:
            actual_strategy = ",".join(sorted(set(s.get("strategy", "Unknown") for s in decision.strategy_signals)))
            
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
        
        current_exposure = sum(p['quantity'] * p['entry_price'] for p in state.open_positions)
        
        from app.risk.portfolio import PortfolioRiskManager, PortfolioRiskConfig
        port_mgr = PortfolioRiskManager(PortfolioRiskConfig())
        port_mgr.state = state
        
        from app.core.models import TradingSignal
        dummy_signal = TradingSignal(
            symbol=decision.symbol, timestamp=decision.timestamp, direction=decision.decision,
            strategy=actual_strategy, confidence=decision.confidence, reason=decision.rationale,
            entry_price=decision.evaluated_price,
            stop_loss=stop_loss, take_profit=take_profit
        )
        
        approved, reason, limit = port_mgr.can_open_position(dummy_signal, position_size, current_equity)
        if not approved:
            logger.warning(f"Portfolio limit rejected execution: {reason}")
            self.repo.record_rejected_trade(self.portfolio_id, decision_id, decision.symbol, decision.decision, f"Portfolio Limit: {reason}", decision.timestamp, actual_strategy, decision.regime)
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
            decision.evaluated_price, position_size, decision.decision, self.cost_config
        )
        
        return self.repo.execute_order(
            portfolio_id=self.portfolio_id,
            decision_id=decision_id,
            symbol=decision.symbol,
            direction=decision.decision,
            quantity=position_size,
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

    def execute_exit(self, position_id: str, exit_price: float, timestamp: datetime, reason: str = "SIGNAL") -> bool:
        """
        Exits a specific open position by its position_id.
        Returns True if closed successfully, False otherwise.
        """
        from app.backtesting.costs import apply_exit_costs
        
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

        return self.repo.execute_exit(
            portfolio_id=self.portfolio_id,
            position_id=position_id,
            exit_price=exit_price,
            actual_price=actual_price,
            commission=commission,
            slippage=slippage,
            timestamp=timestamp,
            unrealized_pnl=unrealized_pnl
        )
