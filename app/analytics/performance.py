from typing import List, Dict, Any
from app.backtesting.models import BacktestTrade
from app.analytics.models import TradeMetrics, EquityMetrics

def calculate_trade_metrics(trades: List[BacktestTrade]) -> TradeMetrics:
    if not trades:
        return TradeMetrics(
            total_trades=0, winning_trades=0, losing_trades=0, win_rate=0.0,
            gross_pnl=0.0, net_pnl=0.0, total_commission=0.0, total_slippage=0.0,
            average_pnl=0.0, average_win=0.0, average_loss=0.0,
            profit_factor=0.0, largest_win=0.0, largest_loss=0.0,
            max_consecutive_wins=0, max_consecutive_losses=0, average_holding_hours=0.0
        )
        
    winning_trades = [t for t in trades if (t.realized_pnl - t.entry_cost) > 0]
    losing_trades = [t for t in trades if (t.realized_pnl - t.entry_cost) <= 0]
    
    total_pnl = sum(t.realized_pnl - t.entry_cost for t in trades)
    total_commission = sum(t.entry_cost + t.exit_cost for t in trades)
    total_slippage = sum(t.slippage_cost for t in trades)
    total_gross_pnl = total_pnl + total_commission
    
    # Calculate profit factor based on true net PnL per trade
    true_pnls = [t.realized_pnl - t.entry_cost for t in trades]
    gross_profit = sum(p for p in true_pnls if p > 0)
    gross_loss = abs(sum(p for p in true_pnls if p <= 0))
    
    current_win_streak = 0
    current_loss_streak = 0
    max_win_streak = 0
    max_loss_streak = 0
    
    for t in trades:
        true_pnl = t.realized_pnl - t.entry_cost
        if true_pnl > 0:
            current_win_streak += 1
            max_loss_streak = max(max_loss_streak, current_loss_streak)
            current_loss_streak = 0
            max_win_streak = max(max_win_streak, current_win_streak)
        else:
            current_loss_streak += 1
            max_win_streak = max(max_win_streak, current_win_streak)
            current_win_streak = 0
            max_loss_streak = max(max_loss_streak, current_loss_streak)
            
    max_win_streak = max(max_win_streak, current_win_streak)
    max_loss_streak = max(max_loss_streak, current_loss_streak)
    
    holding_hours = [(t.exit_time - t.entry_time).total_seconds() / 3600.0 for t in trades]
    
    return TradeMetrics(
        total_trades=len(trades),
        winning_trades=len(winning_trades),
        losing_trades=len(losing_trades),
        win_rate=(len(winning_trades) / len(trades)) * 100.0,
        gross_pnl=total_gross_pnl,
        net_pnl=total_pnl,
        total_commission=total_commission,
        total_slippage=total_slippage,
        average_pnl=total_pnl / len(trades),
        average_win=gross_profit / len(winning_trades) if winning_trades else 0.0,
        average_loss=-gross_loss / len(losing_trades) if losing_trades else 0.0,
        profit_factor=gross_profit / gross_loss if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0),
        largest_win=max(true_pnls + [0.0]),
        largest_loss=min(true_pnls + [0.0]),
        max_consecutive_wins=max_win_streak,
        max_consecutive_losses=max_loss_streak,
        average_holding_hours=sum(holding_hours) / len(holding_hours)
    )

def calculate_equity_metrics(equity_curve: List[Dict[str, Any]], initial_capital: float) -> EquityMetrics:
    if not equity_curve:
        return EquityMetrics(
            initial_capital=initial_capital, final_equity=initial_capital, absolute_pnl=0.0,
            total_return_pct=0.0, max_drawdown_pct=0.0, max_drawdown_amount=0.0,
            average_drawdown_pct=0.0, time_in_drawdown_pct=0.0, recovery_periods=0
        )
        
    last_pt = equity_curve[-1]
    final_equity = last_pt.get('equity', last_pt.get('current_equity', 0.0)) + last_pt.get('unrealized_pnl', 0.0)
    
    peak = equity_curve[0].get('equity', equity_curve[0].get('current_equity', 0.0)) + equity_curve[0].get('unrealized_pnl', 0.0)
    max_dd_pct = 0.0
    max_dd_amount = 0.0
    drawdown_sum_pct = 0.0
    periods_in_dd = 0
    recovery_count = 0
    in_drawdown = False
    
    for pt in equity_curve:
        eq = pt.get('equity', pt.get('current_equity', 0.0))
        # Add unrealized PnL if present (defaults to 0 for old rows)
        eq += pt.get('unrealized_pnl', 0.0)
        
        if eq >= peak:
            if in_drawdown:
                recovery_count += 1
                in_drawdown = False
            peak = eq
        else:
            in_drawdown = True
            dd_amount = peak - eq
            dd_pct = dd_amount / peak
            max_dd_amount = max(max_dd_amount, dd_amount)
            max_dd_pct = max(max_dd_pct, dd_pct)
            drawdown_sum_pct += dd_pct
            periods_in_dd += 1
            
    return EquityMetrics(
        initial_capital=initial_capital,
        final_equity=final_equity,
        absolute_pnl=final_equity - initial_capital,
        total_return_pct=((final_equity - initial_capital) / initial_capital) * 100.0,
        max_drawdown_pct=max_dd_pct * 100.0,
        max_drawdown_amount=max_dd_amount,
        average_drawdown_pct=(drawdown_sum_pct / len(equity_curve)) * 100.0,
        time_in_drawdown_pct=(periods_in_dd / len(equity_curve)) * 100.0,
        recovery_periods=recovery_count
    )
