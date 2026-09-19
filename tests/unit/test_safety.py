import pytest
from unittest import mock
from app.execution.safety import ExecutionSafetyGate, ExecutionSafetyError
import app.execution.safety as safety_module

def test_live_trading_safety_gate_defaults_to_false():
    """Ensure that by default, live trading is blocked."""
    assert ExecutionSafetyGate.is_live_trading_allowed() is False

def test_live_trading_blocked_if_not_production():
    """Even if LIVE_TRADING=true, it should block if ENVIRONMENT!=production."""
    # Mock config at the module level where it's used
    with mock.patch.object(safety_module.config, 'ENVIRONMENT', 'development'):
        with mock.patch.object(safety_module.config, 'LIVE_TRADING', True):
            assert ExecutionSafetyGate.is_live_trading_allowed() is False

def test_live_trading_blocked_if_paper_trading_enabled():
    """Live trading must be blocked if paper trading is concurrently true."""
    with mock.patch.object(safety_module.config, 'ENVIRONMENT', 'production'):
        with mock.patch.object(safety_module.config, 'LIVE_TRADING', True):
            with mock.patch.object(safety_module.config, 'PAPER_TRADING', True):
                assert ExecutionSafetyGate.is_live_trading_allowed() is False

def test_assert_safe_for_live_order_raises_error():
    """The assert method should raise an error when safety check fails."""
    # Since it's false by default in phase 1, this should raise
    with pytest.raises(ExecutionSafetyError, match="CRITICAL"):
        ExecutionSafetyGate.assert_safe_for_live_order()

def test_paper_trading_allowed_check():
    """Check paper trading state."""
    with mock.patch.object(safety_module.config, 'PAPER_TRADING', True):
        assert ExecutionSafetyGate.is_paper_trading_allowed() is True
        
    with mock.patch.object(safety_module.config, 'PAPER_TRADING', False):
        assert ExecutionSafetyGate.is_paper_trading_allowed() is False
