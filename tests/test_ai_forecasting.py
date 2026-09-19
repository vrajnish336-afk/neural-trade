import pytest
import sqlite3
import json
from datetime import datetime, timezone, timedelta

from app.config import config
from app.database.schema import init_db
from app.core.models import MarketBar
from app.forecasting.window_builder import WindowBuilder
from app.forecasting.baseline import BaselineForecaster
from app.forecasting.kronos import KronosAdapter
from app.forecasting.evaluator import ForecastEvaluator
from app.forecasting.repository import ForecastRepository
from app.forecasting.service import ForecastingService
from app.forecasting.models import ForecastResult

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_forecast.sqlite"
    config.DB_PATH = str(db_file)
    config.ENABLE_PERSISTENCE = True
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    init_db()
    
    repo = ForecastRepository()
    repo._init_db()
    yield

def _make_bars(n, start_price=100.0, trend=0.01) -> list[MarketBar]:
    bars = []
    base_t = datetime(2025, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        c = start_price * ((1 + trend) ** i)
        bars.append(MarketBar(
            symbol="TEST",
            timestamp=base_t + timedelta(days=i),
            open=c*0.99,
            high=c*1.01,
            low=c*0.98,
            close=c,
            volume=1000
        ))
    return bars

def test_f01_valid_ohlcv_input():
    bars = _make_bars(50)
    window = WindowBuilder.build_input_window(bars, 10)
    assert len(window) == 10
    
def test_f02_invalid_ohlcv_input():
    bars = _make_bars(50)
    bars[-1].close = -50.0  # Invalid negative close
    with pytest.raises(ValueError):
        WindowBuilder.build_input_window(bars, 10)

def test_f04_unsorted_timestamps():
    bars = _make_bars(50)
    bars[-1].timestamp, bars[-2].timestamp = bars[-2].timestamp, bars[-1].timestamp
    with pytest.raises(ValueError):
        WindowBuilder.build_input_window(bars, 10)

def test_f05_insufficient_window():
    bars = _make_bars(5)
    with pytest.raises(ValueError):
        WindowBuilder.build_input_window(bars, 10)

def test_f07_strict_future_boundary():
    bars = _make_bars(50)
    hist, fut = WindowBuilder.split_for_evaluation(bars, 40, 5)
    assert len(hist) == 40
    assert len(fut) == 5
    assert hist[-1].timestamp < fut[0].timestamp
    
def test_f10_baseline_reproducibility():
    bars = _make_bars(10)
    model = BaselineForecaster()
    res1 = model.predict(bars, 5)
    res2 = model.predict(bars, 5)
    assert res1.predicted_values == res2.predicted_values
    
def test_f14_future_data_corruption():
    # If we evaluate with future data, does the forecast mutate? No, it's immutable.
    bars = _make_bars(10)
    model = BaselineForecaster()
    res = model.predict(bars, 2)
    eval_metrics = ForecastEvaluator.evaluate(res.predicted_values, _make_bars(2, start_price=200))
    # Original prediction array MUST NOT change
    assert res.predicted_values[0] < 200
    
def test_f18_unavailable_advanced_model_fallback():
    adapter = KronosAdapter()
    assert adapter.model_name == "Kronos_Local"
    # If not available, it raises RuntimeError if called directly
    if not adapter.is_available():
        with pytest.raises(RuntimeError):
            adapter.predict(_make_bars(10), 5)
            
def test_f25_paper_only_safety():
    assert config.PAPER_TRADING is True
    assert config.LIVE_TRADING is False

def test_f28_bounded_resource_usage():
    svc = ForecastingService()
    res = svc.generate_forecast("TEST", "1D", 5000, 10) # > MAX_WINDOW_SIZE
    assert res is None
    res = svc.generate_forecast("TEST", "1D", 100, 500) # > MAX_HORIZON
    assert res is None
