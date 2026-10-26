import pytest
from datetime import datetime, timezone
from app.core.models import MarketBar
from run_oos_validation import OOSValidator
from app.backtesting.models import BacktestResult

class DummyProvider:
    def get_historical_bars(self, symbol, timeframe, start_time):
        # Generate dummy bars
        bars = []
        base_price = 1000.0 if "BTC" in symbol else 100.0
        for i in range(10):
            bars.append(MarketBar(
                symbol=symbol,
                timestamp=datetime(2023, 1, 1, i, tzinfo=timezone.utc),
                open=base_price,
                high=base_price + 10,
                low=base_price - 10,
                close=base_price + (i % 2),
                volume=1.0
            ))
        return bars

def test_oos_validator_isolation(monkeypatch):
    validator = OOSValidator(data_dir="dummy")
    validator.provider = DummyProvider()
    
    # Restrict to two to test isolation
    validator.assets = ["BTC_USDT"]
    validator.timeframes = ["1H", "4H"]
    
    # We will patch engine.run to return a deterministic BacktestResult
    # and to verify it only gets one symbol
    class DummyEngine:
        def run(self, bars):
            symbols = set(b.symbol for b in bars)
            assert len(symbols) == 1, "Engine received multiple symbols!"
            
            # Check chronology
            for i in range(1, len(bars)):
                assert bars[i].timestamp >= bars[i-1].timestamp, "Chronology violated"
                
            return BacktestResult(
                initial_capital=10000.0,
                final_equity=10100.0,
                total_return_pct=1.0,
                number_of_trades=5,
                winning_trades=3,
                losing_trades=2,
                win_rate=60.0,
                gross_profit=200.0,
                gross_loss=100.0,
                net_profit=100.0,
                max_drawdown_pct=2.0,
                average_trade_result=20.0,
                profit_factor=2.0,
                average_holding_period_hours=1.0,
                trades=[]
            )
            
    monkeypatch.setattr("run_oos_validation.create_engine_factory", lambda **kwargs: DummyEngine())
    
    agg = validator.run_all()
    
    assert agg["cycles"] == 2
    assert agg["closed_trades"] == 10
    assert agg["wins"] == 6
    assert agg["losses"] == 4
    assert agg["realized_pnl"] == 200.0
    assert agg["max_dd"] == 2.0
    assert agg["profit_factor"] == 2.0
    assert agg["expectancy"] == 20.0
