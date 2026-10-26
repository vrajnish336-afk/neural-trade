import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from app.backtesting.engine import BacktestEngine
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.strategies.ensemble import StrategyEnsemble

def test_force_close_uses_correct_symbol_price():
    ensemble = StrategyEnsemble([])
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
    engine = BacktestEngine(ensemble, risk_engine)
    
    # Pre-populate last_prices and last_timestamps which run() normally sets
    engine.last_prices = {'BTC': 60000.0, 'ETH': 3000.0}
    engine.last_timestamps = {
        'BTC': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'ETH': datetime(2021, 1, 2, tzinfo=timezone.utc)
    }
    
    # LONG BTC
    pos_btc = {
        'symbol': 'BTC',
        'direction': 'LONG',
        'entry_time': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'entry_price': 50000.0,
        'quantity': 0.1,  # $5000 worth
        'stop_loss': None,
        'take_profit': None,
        'entry_cost': 0.0,
        'slippage_entry': 0.0,
        'signal_metadata': {}
    }
    
    # SHORT ETH
    pos_eth = {
        'symbol': 'ETH',
        'direction': 'SHORT',
        'entry_time': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'entry_price': 4000.0,
        'quantity': 1.0,  # $4000 worth
        'stop_loss': None,
        'take_profit': None,
        'entry_cost': 0.0,
        'slippage_entry': 0.0,
        'signal_metadata': {}
    }
    
    engine.portfolio.state.add_position(pos_btc)
    engine.portfolio.state.add_position(pos_eth)
    
    # Let's say the final bar is a SOL bar
    final_bar = MarketBar(symbol='SOL', timestamp=datetime(2021, 1, 3, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=1)
    
    # Force close all
    for pos in list(engine.portfolio.state.open_positions):
        engine._force_close_position(pos, final_bar, "End of backtest")
        
    assert len(engine.closed_trades) == 2
    
    btc_trade = next(t for t in engine.closed_trades if t.symbol == 'BTC')
    eth_trade = next(t for t in engine.closed_trades if t.symbol == 'ETH')
    
    # Verify exact prices were used (BTC 60000, ETH 3000) instead of SOL (100)
    assert btc_trade.exit_price == 60000.0
    assert eth_trade.exit_price == 3000.0
    
    # Verify LONG/SHORT PnL
    # LONG BTC: (60000 - 50000) * 0.1 = +1000.0
    assert btc_trade.realized_pnl == 1000.0
    # SHORT ETH: (4000 - 3000) * 1.0 = +1000.0
    assert eth_trade.realized_pnl == 1000.0

def test_missing_price_fails_safely():
    ensemble = StrategyEnsemble([])
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=10000.0))
    engine = BacktestEngine(ensemble, risk_engine)
    
    engine.last_prices = {}
    engine.last_timestamps = {}
    
    pos_btc = {
        'symbol': 'BTC',
        'direction': 'LONG',
        'entry_time': datetime(2021, 1, 1, tzinfo=timezone.utc),
        'entry_price': 50000.0,
        'quantity': 0.1,
        'stop_loss': None,
        'take_profit': None,
        'entry_cost': 0.0,
        'slippage_entry': 0.0,
        'signal_metadata': {}
    }
    engine.portfolio.state.add_position(pos_btc)
    
    final_bar = MarketBar(symbol='SOL', timestamp=datetime(2021, 1, 3, tzinfo=timezone.utc), open=100.0, high=100.0, low=100.0, close=100.0, volume=1)
    
    # Should safely return without crashing and leave position unresolved
    for pos in list(engine.portfolio.state.open_positions):
        engine._force_close_position(pos, final_bar, "End of backtest")
        
    assert len(engine.closed_trades) == 0
    assert len(engine.portfolio.state.open_positions) == 1
