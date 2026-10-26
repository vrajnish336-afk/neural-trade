import logging
from typing import List, Optional
from datetime import datetime
from pathlib import Path

from app.core.models import MarketBar
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.execution.streaming_paper_broker import StreamingPaperBroker

logger = logging.getLogger(__name__)

class PaperSimulationRunner:
    """
    Drives a deterministic chronological loop over historical data, feeding it sequentially
    into the true production paper-trading pipeline (DecisionOrchestrator -> StreamingPaperBroker).
    """
    
    def __init__(
        self,
        broker: StreamingPaperBroker,
        orchestrator: DecisionOrchestrator,
        portfolio_id: str = "default_paper"
    ):
        self.broker = broker
        self.orchestrator = orchestrator
        self.portfolio_id = portfolio_id
        
    def _evaluate_exits(self, current_bar: MarketBar) -> None:
        """
        Evaluate if current bar hits SL/TP for any open positions via broker monitoring.
        """
        self.broker.monitor_positions(current_bar)

    def run(self, symbol: str, bars: List[MarketBar], context_bars: Optional[List[MarketBar]] = None) -> None:
        """
        Execute simulation over a sequence of bars for a specific symbol.
        """
        if not bars:
            return
            
        logger.info(f"Starting paper simulation for {symbol} with {len(bars)} bars.")
        
        historical_slice = []
        if context_bars:
            historical_slice.extend(context_bars)
            
        for bar in bars:
            historical_slice.append(bar)
            
            # Step 1: Manage Exits
            self._evaluate_exits(bar)
            
            # Step 2: Ensure orchestrator evaluates fresh state
            portfolio = self.broker.repo.get_or_create_portfolio(self.portfolio_id)
            current_equity = portfolio['current_equity']
            
            state = self.broker.get_realtime_portfolio()
            current_positions_count = len(state.open_positions)
            current_exposure = sum(p['quantity'] * p['entry_price'] for p in state.open_positions)
            
            has_symbol_position = any(p['symbol'] == symbol for p in state.open_positions)
            
            # Only evaluate new entry if we don't already have one for this symbol
            if not has_symbol_position:
                decision = self.orchestrator.evaluate(
                    symbol=symbol,
                    bars=historical_slice.copy(),
                    current_equity=current_equity,
                    current_positions_count=current_positions_count,
                    current_exposure=current_exposure,
                    portfolio_id=self.portfolio_id
                )
                
                # Step 3: Route decision to broker
                if decision.paper_execution_eligible and decision.decision in ("LONG", "SHORT"):
                    # Calculate a dynamic risk size from orchestrator logic if needed,
                    # For paper simulation, we mock the signal since broker needs position_size.
                    from app.core.models import TradingSignal
                    sl = decision.stop_loss if decision.stop_loss is not None else (decision.evaluated_price * 0.95 if decision.decision == "LONG" else decision.evaluated_price * 1.05)
                    risk = abs(decision.evaluated_price - sl)
                    if decision.take_profit is not None:
                        tp = decision.take_profit
                    else:
                        tp = decision.evaluated_price + (3.0 * risk) if decision.decision == "LONG" else max(0.01, decision.evaluated_price - (3.0 * risk))

                    mock_sig = TradingSignal(
                        symbol=symbol, timestamp=bar.timestamp, direction=decision.decision,
                        strategy="Simulation", confidence=decision.confidence,
                        entry_price=decision.evaluated_price,
                        stop_loss=sl, take_profit=tp, reason="Simulation decision"
                    )
                    risk_dec = self.broker.risk_engine.evaluate_trade(
                        mock_sig, current_equity, current_positions_count, current_exposure
                    )
                    
                    if risk_dec.approved:
                        success = self.broker.execute_decision(
                            decision=decision,
                            position_size=risk_dec.position_size,
                            stop_loss=sl,
                            take_profit=tp
                        )
                        logger.info(f"Execution success: {success}")
                    else:
                        logger.warning(f"Risk rejected in runner: {risk_dec.rejection_reason}")
                else:
                    if decision.decision != "NO TRADE":
                        logger.warning(f"Decision not eligible: {decision.decision}, reason: {decision.rationale}")
