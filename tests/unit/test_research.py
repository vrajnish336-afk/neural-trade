import pytest
from datetime import datetime, timezone
from app.research.dataset import generate_synthetic_data
from app.research.validation import validate_dataset
from app.research.splits import split_research_windows
from app.core.models import MarketBar

def test_generate_synthetic_data():
    datasets = generate_synthetic_data(["A", "B"], num_bars=500, seed=1)
    assert len(datasets) == 2
    assert "A" in datasets
    assert len(datasets["A"]) == 500
    
    # Check deterministic seed
    datasets2 = generate_synthetic_data(["A"], num_bars=500, seed=1)
    assert datasets["A"][10].close == datasets2["A"][10].close

def test_dataset_validation():
    bars = []
    # Test valid
    for i in range(150):
        bars.append(MarketBar(symbol="A", timestamp=datetime(2022, 1, 1, tzinfo=timezone.utc), open=10, high=12, low=8, close=11, volume=100))
        
    res = validate_dataset(bars, "A")
    # Will have duplicate timestamp errors since timestamp is the same
    assert not res.is_valid
    assert len(res.errors) > 0
    assert "Duplicate timestamp" in res.errors[0] or "ordering" in res.errors[0]

def test_research_splits():
    datasets = generate_synthetic_data(["A"], num_bars=1000, seed=1)
    bars = datasets["A"]
    
    train, val, test, tr_s, val_s, ts_s = split_research_windows(bars, 0.5, 0.25, 0.25)
    
    assert len(train) == 500
    assert len(val) == 250
    assert len(test) == 250
    
    # Non overlapping
    assert train[-1].timestamp < val[0].timestamp
    assert val[-1].timestamp < test[0].timestamp
    
    assert tr_s.row_count == 500
