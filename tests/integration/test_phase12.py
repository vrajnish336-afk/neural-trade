import pytest
from datetime import datetime, timedelta
import pandas as pd
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult, RiskDecision
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig, ExecutionAssumptions
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.trend_following import TrendFollowingStrategy
from app.strategies.breakout import BreakoutStrategy
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.portfolio import PortfolioRiskManager, PortfolioRiskConfig
from app.analysis.correlation import get_correlation_status, calculate_historical_correlation
from app.backtesting.drawdown import calculate_extended_drawdown_metrics

def generate_bars(symbol: str, count: int, base_price: float, start_time: datetime, gap_at: int = -1, gap_size: float = 0.0) -> list[MarketBar]:
    bars = []
    current_time = start_time
    for i in range(count):
        open_p = base_price
        if i == gap_at:
            open_p += gap_size
        
        bars.append(MarketBar(
            symbol=symbol,
            timestamp=current_time,
            open=open_p,
            high=open_p + 10,
            low=open_p - 10,
            close=open_p + 5,
            volume=1000
        ))
        current_time += timedelta(hours=1)
        base_price = open_p + 5
    return bars

def test_portfolio_exposure_limits():
    config = PortfolioRiskConfig(max_concurrent_positions=2, max_gross_exposure_pct=0.5)
    manager = PortfolioRiskManager(config)
    
    sig1 = TradingSignal(symbol="BTC", direction="LONG", strategy="T", timestamp=datetime.now(), entry_price=100, stop_loss=90, confidence=1.0, reason="test")
    sig2 = TradingSignal(symbol="ETH", direction="LONG", strategy="T", timestamp=datetime.now(), entry_price=50, stop_loss=45, confidence=1.0, reason="test")
    sig3 = TradingSignal(symbol="SOL", direction="LONG", strategy="T", timestamp=datetime.now(), entry_price=20, stop_loss=15, confidence=1.0, reason="test")
    
    # Add 1
    manager.state.add_position({'symbol': 'BTC', 'direction': 'LONG', 'entry_price': 100, 'quantity': 1, 'stop_loss': 90, 'signal_metadata': {}})
    
    # Test 2
    app, reason, lim = manager.can_open_position(sig2, 1.0, 1000)
    assert app is True
    manager.state.add_position({'symbol': 'ETH', 'direction': 'LONG', 'entry_price': 50, 'quantity': 1, 'stop_loss': 45, 'signal_metadata': {}})
    
    # Test 3 - should fail max concurrent
    app, reason, lim = manager.can_open_position(sig3, 1.0, 1000)
    assert app is False
    assert lim == "MAX_CONCURRENT_POSITIONS"
    
def test_correlation_calculation():
    bars_btc = generate_bars("BTC", 50, 1000, datetime(2023,1,1))
    bars_eth = generate_bars("ETH", 50, 100, datetime(2023,1,1))
    
    data = {"BTC": bars_btc, "ETH": bars_eth}
    corr_matrix = calculate_historical_correlation(data, min_periods=30)
    
    assert not corr_matrix.empty
    
    status = get_correlation_status(corr_matrix, "BTC", "ETH", threshold=0.7)
    assert status in ["HIGH_CORRELATION", "LOW_CORRELATION"]
    
    # Test insufficient data
    data_short = {"BTC": bars_btc[:10], "ETH": bars_eth[:10]}
    corr_matrix_short = calculate_historical_correlation(data_short, min_periods=30)
    assert corr_matrix_short.empty
    status_short = get_correlation_status(corr_matrix_short, "BTC", "ETH")
    assert status_short == "INSUFFICIENT_DATA"

def test_execution_slippage():
    from app.backtesting.costs import apply_entry_costs
    cost = ExecutionAssumptions.SLIPPAGE_2X # 0.2%
    actual, comm, slip = apply_entry_costs(100.0, 1.0, "LONG", cost)
    assert actual == 100.2
    assert slip == 100 * 0.002
    
def test_same_bar_ambiguity():
    # Gap stress and same bar
    engine = BacktestEngine(
        ensemble=StrategyEnsemble([TrendFollowingStrategy()]),
        risk_engine=RiskEngine(PortfolioRiskLimits(10000)),
        portfolio_config=PortfolioRiskConfig()
    )
    
    engine.equity = 10000
    engine.portfolio.state.add_position({
        'symbol': 'BTC', 'direction': 'LONG', 'entry_time': datetime.now(), 
        'entry_price': 100, 'quantity': 1, 'stop_loss': 90, 'take_profit': 110,
        'entry_cost': 0, 'slippage_entry': 0, 'signal_metadata': {}
    })
    
    bar = MarketBar(symbol='BTC', timestamp=datetime.now(), open=100, high=120, low=80, close=100, volume=100)
    engine._evaluate_exits(bar)
    
    assert len(engine.closed_trades) == 1
    assert engine.closed_trades[0].exit_reason == "Stop Loss (Ambiguity assumed Worst)"

def test_drawdown_metrics():
    eq_curve = [
        {'timestamp': datetime(2023,1,1), 'equity': 1000, 'exposure': 0},
        {'timestamp': datetime(2023,1,2), 'equity': 900, 'exposure': 0},
        {'timestamp': datetime(2023,1,3), 'equity': 800, 'exposure': 0},
        {'timestamp': datetime(2023,1,4), 'equity': 1100, 'exposure': 0},
    ]
    res = calculate_extended_drawdown_metrics(eq_curve)
    assert res['max_drawdown_pct'] == 20.0
    assert res['longest_drawdown_periods'] == 2
    assert res['max_recovery_periods'] == 2
