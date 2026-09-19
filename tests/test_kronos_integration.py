import pytest
from datetime import datetime, timezone
import pandas as pd

from app.core.models import MarketBar
from app.strategies.kronos.config import kronos_config
from app.strategies.kronos.engine import KronosEngineWrapper, is_kronos_available
from app.strategies.kronos.strategy import KronosStrategy
from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

def generate_mock_bars(count: int) -> list[MarketBar]:
    bars = []
    base_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    for i in range(count):
        ts = base_time + pd.Timedelta(minutes=5 * i)
        bars.append(MarketBar(
            symbol="TEST",
            timestamp=ts,
            open=100.0 + i,
            high=102.0 + i,
            low=99.0 + i,
            close=101.0 + i,
            volume=1000.0
        ))
    return bars

def test_kronos_unavailable_behavior():
    if is_kronos_available():
        pytest.skip("Kronos is available; skipping unavailability test.")
    
    with pytest.raises(RuntimeError, match="unavailable"):
        KronosEngineWrapper()
        
    strategy = KronosStrategy(threshold=0.0, mode="normal")
    assert strategy.engine is None
    with pytest.raises(RuntimeError, match="unavailable"):
        strategy.generate_signal(generate_mock_bars(kronos_config.lookback + 1))

@pytest.mark.skipif(not is_kronos_available(), reason="Kronos repository is unavailable")
def test_kronos_imports():
    from app.strategies.kronos.config import kronos_config
    from app.strategies.kronos.engine import KronosEngineWrapper
    from app.strategies.kronos.strategy import KronosStrategy
    from app.strategies.kronos.analytics import calculate_mae
    assert True

@pytest.mark.skipif(not is_kronos_available(), reason="Kronos repository is unavailable")
def test_kronos_engine_load():
    engine = KronosEngineWrapper()
    assert engine.model is not None
    assert engine.tokenizer is not None
    # Verify fallback logic
    assert "cpu" in engine.device or "cuda" in engine.device

@pytest.mark.skipif(not is_kronos_available(), reason="Kronos repository is unavailable")
def test_kronos_historical_prediction():
    engine = KronosEngineWrapper()
    bars = generate_mock_bars(kronos_config.lookback + 1)
    
    predicted_return = engine.predict(bars[:-1], pred_len=1)
    assert isinstance(predicted_return, float)

@pytest.mark.skipif(not is_kronos_available(), reason="Kronos repository is unavailable")
def test_kronos_strategy_signal():
    # threshold 0.0 means it should always generate a signal unless prediction is exactly 0.0
    strategy = KronosStrategy(threshold=0.0, mode="normal")
    bars = generate_mock_bars(kronos_config.lookback + 1)
    
    signal = strategy.generate_signal(bars[:-1])
    assert signal is not None
    assert signal.direction in ["LONG", "SHORT"]
    assert signal.strategy == "Kronos_normal_0.0"

@pytest.mark.skipif(not is_kronos_available(), reason="Kronos repository is unavailable")
def test_kronos_backtest_integration():
    strategy = KronosStrategy(threshold=0.0, mode="normal")
    ensemble = StrategyEnsemble([strategy], min_score=0.0)
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
    
    engine = BacktestEngine(
        ensemble=ensemble,
        risk_engine=risk_engine,
        initial_capital=10000.0,
        cost_config=CostConfig(commission_rate=0.0, slippage_rate=0.0)
    )
    
    bars = generate_mock_bars(kronos_config.lookback + 5)
    result = engine.run(bars)
    
    assert result is not None
    # We might or might not have trades depending on what Kronos predicts,
    # but the engine should run without errors.
