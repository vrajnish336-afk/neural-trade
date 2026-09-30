import pytest
from unittest.mock import MagicMock
from app.broker.interfaces import IOrderExecutionAdapter
from app.broker.adapters import PaperExecutionAdapter
from app.risk.portfolio import PortfolioState

def test_paper_execution_adapter_implements_interface():
    mock_broker = MagicMock()
    adapter = PaperExecutionAdapter(streaming_broker=mock_broker)
    assert isinstance(adapter, IOrderExecutionAdapter)

def test_paper_execution_adapter_delegates_execute_decision():
    mock_broker = MagicMock()
    mock_broker.execute_decision.return_value = True
    mock_decision = MagicMock()
    
    adapter = PaperExecutionAdapter(streaming_broker=mock_broker)
    res = adapter.execute_decision(mock_decision, position_size=2.0)
    
    assert res is True
    mock_broker.execute_decision.assert_called_once_with(
        mock_decision, position_size=2.0, stop_loss=None, take_profit=None
    )

def test_paper_execution_adapter_delegates_get_portfolio_state():
    mock_broker = MagicMock()
    expected_state = PortfolioState()
    mock_broker.get_realtime_portfolio.return_value = expected_state
    
    adapter = PaperExecutionAdapter(streaming_broker=mock_broker)
    state = adapter.get_portfolio_state()
    
    assert state == expected_state
    mock_broker.get_realtime_portfolio.assert_called_once()
