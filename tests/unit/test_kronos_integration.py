import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import pandas as pd
from app.core.models import MarketBar
from app.forecasting.kronos import KronosAdapter

@pytest.fixture
def sample_history():
    return [
        MarketBar(symbol="TEST", timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc), open=10, high=12, low=9, close=11, volume=100),
        MarketBar(symbol="TEST", timestamp=datetime(2023, 1, 2, tzinfo=timezone.utc), open=11, high=13, low=10, close=12, volume=110),
    ]

def test_kronos_adapter_fallback_on_import_error():
    # Force import failure by pretending 'model' doesn't exist
    with patch.dict('sys.modules', {'torch': MagicMock()}):
        KronosAdapter._import_failed = False
        KronosAdapter._predictor_cache = None
        
        # Override the _load_kronos to simulate failure gracefully as it would
        with patch.object(KronosAdapter, '_load_kronos', side_effect=ImportError("Failed")):
            try:
                adapter = KronosAdapter()
            except ImportError:
                adapter = KronosAdapter.__new__(KronosAdapter)
                adapter._available = False
                adapter._import_failed = True
                adapter._predictor_cache = None
        
            assert not adapter.is_available()
            
            with pytest.raises(RuntimeError, match="Kronos predictor unavailable"):
                adapter.predict(history=[], horizon=5)

@patch('app.forecasting.kronos.sys.path')
def test_kronos_adapter_successful_prediction(mock_sys_path, sample_history):
    with patch.dict('sys.modules', {'torch': MagicMock(), 'model': MagicMock()}):
        import torch
        from model import Kronos, KronosTokenizer, KronosPredictor
        
        torch.cuda.is_available.return_value = False
        
        mock_predictor_instance = MagicMock()
        # Create a return object that does NOT have 'values' attr (not a DataFrame)
        mock_pred = MagicMock(spec=[])
        mock_pred.squeeze = MagicMock(return_value=MagicMock(spec=[], tolist=MagicMock(return_value=[12.5, 13.0, 13.5])))
        mock_predictor_instance.predict.return_value = mock_pred
        KronosPredictor.return_value = mock_predictor_instance
        
        KronosAdapter._import_failed = False
        KronosAdapter._predictor_cache = None
        
        adapter = KronosAdapter()
        
        assert adapter.is_available()
        
        res = adapter.predict(history=sample_history, horizon=3)
        assert res.predicted_values == [12.5, 13.0, 13.5]
        
        args, kwargs = mock_predictor_instance.predict.call_args
        assert kwargs["pred_len"] == 3
        assert kwargs["df"].shape[0] == 2
        assert list(kwargs["df"].columns) == ["open", "high", "low", "close", "volume", "amount"]
