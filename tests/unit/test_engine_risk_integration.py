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

class LosingStrategy(Strategy):
    @property
    def name(self): return "LosingStrategy"
    def generate_signal(self, bars):
        if len(bars) >= 1:
            # Always buy at 100, stop at 90 (loss)
            return TradingSignal(
                symbol="BTC", timestamp=bars[-1].timestamp, direction="LONG", strategy=self.name,
                confidence=1.0, entry_price=100, stop_loss=90, take_profit=110, reason="test"
            )
        return None

def test_daily_loss_limit_and_cooldown():
    # We will generate enough bars to hit multiple losses.
    # Entry at 100, SL at 90. Risk is 10%.
    # 1st trade: -100 PNL. Equity 900.
    
    bars = [
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,10,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10),
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,11,tzinfo=timezone.utc), open=100, high=100, low=80, close=95, volume=10), # hits SL 90 -> -1 loss
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,12,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10), # Should enter again
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,13,tzinfo=timezone.utc), open=100, high=100, low=80, close=95, volume=10), # hits SL -> -2 loss
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,14,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10), # Enter again
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,15,tzinfo=timezone.utc), open=100, high=100, low=80, close=95, volume=10), # hits SL -> -3 loss -> Cooldown trigger
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,16,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10), # Should be REJECTED by cooldown
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,17,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10), # REJECTED by cooldown
    ]
    
    ensemble = StrategyEnsemble([LosingStrategy()], min_score=0.0)
    limits = PortfolioRiskLimits(initial_equity=1000.0, loss_streak_threshold=3, cooldown_bars=3, daily_loss_limit_pct=1.0) # set daily limit high to avoid interference
    risk_engine = RiskEngine(limits=limits, risk_per_trade_pct=0.10)
    
    engine = BacktestEngine(ensemble=ensemble, risk_engine=risk_engine, initial_capital=1000.0, portfolio_config=PortfolioRiskConfig(max_symbol_exposure_pct=10.0, max_gross_exposure_pct=10.0, max_strategy_exposure_pct=10.0, max_net_exposure_pct=10.0, max_aggregate_stop_risk_pct=1.0))
    with patch('app.backtesting.engine.detect_market_regime', return_value=MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)):
        res = engine.run(bars)
    
    assert res.number_of_trades == 3
    assert res.losing_trades == 3
    # Trades at 11:00, 13:00, 15:00. Cooldown hits at 15:00. 16:00 and 17:00 are blocked.

def test_daily_loss_limit_blocks_entry():
    bars = [
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,10,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10),
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,11,tzinfo=timezone.utc), open=100, high=100, low=80, close=95, volume=10), # hits SL 90 -> -100 loss
        MarketBar(symbol="BTC", timestamp=datetime(2023,1,1,12,tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10), # Daily limit is 0.05 (5%). 100 > 50. Should be BLOCKED.
    ]
    
    ensemble = StrategyEnsemble([LosingStrategy()], min_score=0.0)
    limits = PortfolioRiskLimits(initial_equity=1000.0, daily_loss_limit_pct=0.05) # 5% max daily
    risk_engine = RiskEngine(limits=limits, risk_per_trade_pct=0.10) # Risking 10% per trade (100)
    
    engine = BacktestEngine(ensemble=ensemble, risk_engine=risk_engine, initial_capital=1000.0, portfolio_config=PortfolioRiskConfig(max_symbol_exposure_pct=10.0, max_gross_exposure_pct=10.0, max_strategy_exposure_pct=10.0, max_net_exposure_pct=10.0, max_aggregate_stop_risk_pct=1.0))
    with patch('app.backtesting.engine.detect_market_regime', return_value=MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)):
        res = engine.run(bars)
    
    assert res.number_of_trades == 1 # Second entry was blocked
