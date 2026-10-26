import os

filepath = 'app/backtesting/engine.py'
with open(filepath, 'r') as f:
    content = f.read()

# Replace the force close block
old_force_close_block = """        for pos in list(self.portfolio.state.open_positions):
            self._force_close_position(pos, bars[-1], reason="End of backtest")
            
        logger.info("Backtest completed. Final equity: %.2f", self.equity)
        return self._generate_result()"""

new_force_close_block = """        # Fold-end handling: Do NOT force close unresolved positions.
        # Leave them in open_positions so they don't contaminate realized strategy stats.
        logger.info("Backtest completed. Realized cash: %.2f, Open positions: %d", self.equity, len(self.portfolio.state.open_positions))
        return self._generate_result()"""

content = content.replace(old_force_close_block, new_force_close_block)

old_generate_result = """    def _generate_result(self) -> BacktestResult:
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
        )"""

new_generate_result = """    def _generate_result(self) -> BacktestResult:
        unrealized_mtm = 0.0
        for pos in self.portfolio.state.open_positions:
            sym_price = self.last_prices.get(pos['symbol'], pos['entry_price'])
            if pos['direction'] == 'LONG':
                unrealized_mtm += (sym_price - pos['entry_price']) * pos['quantity']
            else:
                unrealized_mtm += (pos['entry_price'] - sym_price) * pos['quantity']
                
        final_equity_mtm = self.equity + unrealized_mtm
        total_return_pct = ((final_equity_mtm - self.initial_capital) / self.initial_capital) * 100

        if not self.closed_trades:
            return BacktestResult(
                initial_capital=self.initial_capital,
                final_equity=final_equity_mtm,
                total_return_pct=total_return_pct,
                number_of_trades=0,
                winning_trades=0,
                losing_trades=0,
                win_rate=0.0,
                gross_profit=0.0,
                gross_loss=0.0,
                net_profit=0.0,
                max_drawdown_pct=calculate_drawdown([pt['equity'] for pt in self.equity_curve]) if self.equity_curve else 0.0,
                average_trade_result=0.0,
                profit_factor=0.0,
                average_holding_period_hours=0.0,
                unresolved_positions_count=len(self.portfolio.state.open_positions),
                unrealized_mtm=unrealized_mtm,
                trades=[],
                equity_curve=self.equity_curve,
                telemetry_snapshot=telemetry.export_snapshot() if 'telemetry' in globals() or 'telemetry' in locals() else __import__('app.diagnostics.telemetry', fromlist=['telemetry']).telemetry.export_snapshot()
            )
            
        winning_trades = [t for t in self.closed_trades if t.realized_pnl > 0]
        losing_trades = [t for t in self.closed_trades if t.realized_pnl <= 0]
        
        gross_profit = sum(t.realized_pnl for t in winning_trades)
        gross_loss = abs(sum(t.realized_pnl for t in losing_trades))
        net_profit = gross_profit - gross_loss
        
        win_rate = (len(winning_trades) / len(self.closed_trades)) * 100
        
        holding_periods = [(t.exit_time - t.entry_time).total_seconds() / 3600 for t in self.closed_trades]
        avg_holding = sum(holding_periods) / len(holding_periods) if holding_periods else 0.0
        
        return BacktestResult(
            initial_capital=self.initial_capital,
            final_equity=final_equity_mtm,
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
            unresolved_positions_count=len(self.portfolio.state.open_positions),
            unrealized_mtm=unrealized_mtm,
            trades=self.closed_trades,
            equity_curve=self.equity_curve,
            telemetry_snapshot=telemetry.export_snapshot() if 'telemetry' in globals() or 'telemetry' in locals() else __import__('app.diagnostics.telemetry', fromlist=['telemetry']).telemetry.export_snapshot()
        )

    def _generate_empty_result(self) -> BacktestResult:
        return self._generate_result() # Refactored to handle empty trades above"""

content = content.replace(old_generate_result, new_generate_result)

with open(filepath, 'w') as f:
    f.write(content)
print("Updated engine.py")
