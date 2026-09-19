import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from app.core.models import MarketBar, TradingSignal, MarketRegimeResult
from app.backtesting.engine import BacktestEngine
from app.risk.portfolio import PortfolioRiskConfig
from app.backtesting.models import CostConfig
from app.strategies.base import Strategy
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

class DummyStrategy(Strategy):
    @property
    def name(self): return "Dummy"
    
    def generate_signal(self, bars):
        if len(bars) == 1:
            return TradingSignal(
                symbol="BTC", timestamp=bars[-1].timestamp, direction="LONG", strategy=self.name,
                confidence=1.0, entry_price=100, stop_loss=90, take_profit=120, reason="test"
            )
        return None

def generate_bars():
    return [
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,tzinfo=timezone.utc), open=100, high=105, low=95, close=100, volume=100),
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,2,tzinfo=timezone.utc), open=100, high=110, low=95, close=105, volume=100),
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,3,tzinfo=timezone.utc), open=105, high=125, low=100, close=120, volume=100)
    ]

@pytest.fixture
def base_engine():
    strategy = DummyStrategy()
    ensemble = StrategyEnsemble([strategy], min_score=0.0) # 0 to bypass regime veto in simple tests
    limits = PortfolioRiskLimits(initial_equity=1000.0)
    risk_engine = RiskEngine(limits=limits, risk_per_trade_pct=0.10) # 10% risk to mirror old behavior closely
    return BacktestEngine(ensemble=ensemble, risk_engine=risk_engine, initial_capital=1000.0, portfolio_config=PortfolioRiskConfig(max_symbol_exposure_pct=10.0, max_gross_exposure_pct=10.0, max_strategy_exposure_pct=10.0, max_net_exposure_pct=10.0, max_aggregate_stop_risk_pct=1.0))

def test_backtest_engine_winning_trade(base_engine):
    bars = generate_bars()
    with patch('app.backtesting.engine.detect_market_regime', return_value=MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)):
        result = base_engine.run(bars)
    
    assert result.number_of_trades == 1
    assert result.winning_trades == 1
    assert result.losing_trades == 0
    # Entry at 100. Stop is 90. Risk distance = 10. Risk amt = 1000 * 0.10 = 100.
    # Qty = 100 / 10 = 10.
    # TP at 120. PNL = (120 - 100) * 10 = 200.
    assert result.net_profit == 200.0
    assert result.final_equity == 1200.0
    
def test_transaction_costs_and_slippage():
    strategy = DummyStrategy()
    ensemble = StrategyEnsemble([strategy], min_score=0.0)
    limits = PortfolioRiskLimits(initial_equity=1000.0)
    risk_engine = RiskEngine(limits=limits, risk_per_trade_pct=0.10)
    
    cost_config = CostConfig(commission_rate=0.01, slippage_rate=0.01)
    port_cfg = PortfolioRiskConfig(max_symbol_exposure_pct=10.0, max_gross_exposure_pct=10.0, max_strategy_exposure_pct=10.0, max_aggregate_stop_risk_pct=1.0)
    engine = BacktestEngine(ensemble=ensemble, risk_engine=risk_engine, initial_capital=1000.0, cost_config=cost_config, portfolio_config=port_cfg)
    bars = generate_bars()
    
    with patch('app.backtesting.engine.detect_market_regime', return_value=MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)):
        result = engine.run(bars)
    
    assert result.number_of_trades == 1
    assert result.net_profit < 200.0
    
def test_intrabar_ambiguity_conservative():
    class AmbiguousStrategy(Strategy):
        @property
        def name(self): return "Ambiguous"
        def generate_signal(self, bars):
            if len(bars) == 1:
                return TradingSignal(
                    symbol="BTC", timestamp=bars[-1].timestamp, direction="LONG", strategy=self.name,
                    confidence=1.0, entry_price=100, stop_loss=90, take_profit=110, reason="test"
                )
            return None
            
    ensemble = StrategyEnsemble([AmbiguousStrategy()], min_score=0.0)
    limits = PortfolioRiskLimits(initial_equity=1000.0)
    risk_engine = RiskEngine(limits=limits, risk_per_trade_pct=0.10)
    
    engine = BacktestEngine(ensemble=ensemble, risk_engine=risk_engine, initial_capital=1000.0, portfolio_config=PortfolioRiskConfig(max_symbol_exposure_pct=10.0, max_gross_exposure_pct=10.0, max_strategy_exposure_pct=10.0, max_net_exposure_pct=10.0, max_aggregate_stop_risk_pct=1.0))
    bars = [
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=100),
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,2,tzinfo=timezone.utc), open=100, high=110, low=90, close=105, volume=100)
    ]
    
    with patch('app.backtesting.engine.detect_market_regime', return_value=MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)):
        result = engine.run(bars)
    
    assert result.number_of_trades == 1
    assert result.winning_trades == 0
    assert result.losing_trades == 1
    # Qty = 100 risk / 10 distance = 10 units. Loss = 10 * -10 = -100.
    assert result.net_profit == -100.0
    assert result.trades[0].exit_reason.startswith("Stop Loss")
