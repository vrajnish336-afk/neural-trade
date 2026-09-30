import pytest
from datetime import datetime
from unittest.mock import MagicMock
from app.core.models import MarketBar
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.broker.adapters import ReadOnlyLiveMarketDataAdapter, PaperExecutionAdapter

def test_decision_orchestrator_accepts_broker_adapters():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    
    mock_provider = MagicMock()
    mock_broker = MagicMock()
    
    read_only_adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_provider)
    execution_adapter = PaperExecutionAdapter(streaming_broker=mock_broker)
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        market_data_engine=read_only_adapter,
        execution_adapter=execution_adapter
    )
    
    assert orchestrator.market_data_engine == read_only_adapter
    assert orchestrator.data_provider == read_only_adapter
    assert orchestrator.execution_adapter == execution_adapter

def test_decision_orchestrator_evaluation_with_broker_adapters():
    mock_ensemble = MagicMock()
    mock_risk = MagicMock()
    mock_intel = MagicMock()
    mock_forecast = MagicMock()
    mock_intel.generate_intelligence.return_value = None
    mock_forecast.generate_forecast.return_value = None
    
    mock_ensemble.evaluate.return_value = None
    
    now = datetime.utcnow()
    bars = [
        MarketBar(symbol="BTC/USD", timestamp=now, open=50000.0, high=51000.0, low=49000.0, close=50500.0, volume=10.0)
    ]
    
    mock_provider = MagicMock()
    mock_provider.get_historical_bars.return_value = bars
    
    read_only_adapter = ReadOnlyLiveMarketDataAdapter(provider=mock_provider)
    execution_adapter = PaperExecutionAdapter(streaming_broker=MagicMock())
    
    orchestrator = DecisionOrchestrator(
        ensemble=mock_ensemble,
        risk_engine=mock_risk,
        intelligence_service=mock_intel,
        forecasting_service=mock_forecast,
        market_data_engine=read_only_adapter,
        execution_adapter=execution_adapter
    )
    
    decision = orchestrator.evaluate("BTC/USD", bars, now, 10000.0, 0, 0.0)
    assert decision.symbol == "BTC/USD"
    assert decision.decision == "NO TRADE"
