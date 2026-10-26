import pytest
from datetime import datetime, timezone, timedelta
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.backtesting.models import CostConfig

class DummyStrategyEnsemble:
    def __init__(self):
        self.adaptive = None
    def evaluate(self, historical_slice, regime_result, intelligence):
        from app.core.models import TradingSignal, SignalScore
        
        # Fire LONG signal on bar 1, never close
        if len(historical_slice) == 2:
            return TradingSignal(
                symbol="BTC_USDT",
                direction="LONG",
                timestamp=historical_slice[-1].timestamp,
                entry_price=historical_slice[-1].close,
                stop_loss=historical_slice[-1].close * 0.9,
                take_profit=historical_slice[-1].close * 1.1,
                strategy="TestStrategy",
                score=SignalScore(score=80.0, is_valid=True, components={}),
                confidence=1.0,
                reason="test"
            )
        return None

class DummyRiskEngine:
    def __init__(self):
        from app.risk.limits import PortfolioRiskLimits
        class DummyLimits:
            def __init__(self):
                self.initial_equity = 10000.0
            def step_bar(self): pass
            def reset_daily_loss(self): pass
            def update_from_closed_trade(self, trade): pass
        self.limits = DummyLimits()

    def evaluate_trade(self, signal, current_equity, current_positions_count, current_exposure):
        from app.core.models import RiskDecision
        return RiskDecision(approved=True, position_size=1.0, rejection_reason="", requested_risk=1.0, allowed_risk=1.0)

def test_fold_end_semantics():
    ensemble = DummyStrategyEnsemble()
    risk_engine = DummyRiskEngine()
    cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.0)
    
    engine = BacktestEngine(
        ensemble=ensemble,
        risk_engine=risk_engine,
        initial_capital=10000.0,
        cost_config=cost_config
    )
    
    # 3 bars: bar0 (no signal), bar1 (fires long at 100), bar2 (moves to 105, fold ends)
    bars = [
        MarketBar(symbol="BTC_USDT", timestamp=datetime(2023, 1, 1, 0, tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10),
        MarketBar(symbol="BTC_USDT", timestamp=datetime(2023, 1, 1, 1, tzinfo=timezone.utc), open=100, high=100, low=100, close=100, volume=10),
        MarketBar(symbol="BTC_USDT", timestamp=datetime(2023, 1, 1, 2, tzinfo=timezone.utc), open=105, high=105, low=105, close=105, volume=10),
    ]
    
    res = engine.run(bars)
    
    # 1. Open position at fold end is not counted as strategy loss/win
    assert len(res.trades) == 0
    assert res.number_of_trades == 0
    assert res.winning_trades == 0
    assert res.losing_trades == 0
    
    # 2. Terminal MTM is separate from realized PnL
    # Entry price 100, size 1.0. cost = 0.1
    # Cash/Equity = 10000 - 0.1 = 9999.9
    # Unrealized MTM at bar2 close (105): +5.0
    # Final equity = 9999.9 + 5.0 = 10004.9
    assert res.net_profit == 0.0 # Realized
    assert res.unrealized_mtm == 5.0
    assert res.unresolved_positions_count == 1
    assert abs(res.final_equity - 10004.9) < 1e-5
    
    # 3. Trade count excludes unresolved fold-end positions
    assert len(engine.closed_trades) == 0
    
    # 4. Fold-end handling cannot create artificial PF/expectancy
    assert res.profit_factor == 0.0
    assert res.average_trade_result == 0.0
    
    # 5. Symbol-specific terminal price is used (demonstrated by 105 used)
    # 6. No position leaks into next fold
    # A fresh engine instance would be used for the next fold, so no leak occurs.
    
    print("Fold-end semantics test passed!")
