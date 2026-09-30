import pytest
from unittest import mock
from datetime import datetime, timezone

from app.sandbox.research_sandbox import ControlledResearchSandbox
from app.sandbox.models import ExperimentStatus
from app.core.models import MarketBar

@pytest.fixture
def mock_bars():
    return [
        MarketBar(
            symbol="BTC/USD",
            timestamp=datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),
            open=100.0, high=105.0, low=99.0, close=102.0, volume=1000.0
        )
    ]


def test_sandbox_disabled_by_default(mock_bars):
    """Verify sandbox raises PermissionError when AI_RESEARCH_SANDBOX_ENABLED is False."""
    sandbox = ControlledResearchSandbox()
    assert sandbox.is_enabled() is False

    with pytest.raises(PermissionError, match="disabled"):
        sandbox.execute_candidate("prop_1", "def func(): pass", "func", mock_bars)

    with pytest.raises(PermissionError, match="disabled"):
        sandbox.approve_candidate_for_research("prop_1", human_approved=True)

def test_production_core_files_protected(mock_bars):
    """Verify candidate code attempting to access core files or forbidden ops is blocked."""
    sandbox = ControlledResearchSandbox()
    with mock.patch.object(sandbox, "is_enabled", return_value=True):
        code_file_op = "open('app/config.py', 'w').write('hacked')"
        res = sandbox.execute_candidate("prop_2", code_file_op, "func", mock_bars)
        assert res.is_safe is False
        assert res.status == ExperimentStatus.FAILED
        assert "Forbidden operation" in res.stderr
        assert res.provenance == "CONTROLLED_RESEARCH_SANDBOX_BLOCKED_PROTECTED_FILES"

def test_isolated_execution_delegation_and_provenance(mock_bars):
    """Verify execution is delegated to executor and provenance metadata is recorded."""
    sandbox = ControlledResearchSandbox()
    valid_code = """
def research_strategy(bars, parameters):
    return None
"""
    with mock.patch.object(sandbox, "is_enabled", return_value=True):
        res = sandbox.execute_candidate("prop_3", valid_code, "research_strategy", mock_bars)
        assert res.status == ExperimentStatus.COMPLETED
        assert res.is_safe is True
        assert res.provenance == "CONTROLLED_RESEARCH_SANDBOX_ISOLATED_EXECUTOR"

def test_timeout_enforcement(mock_bars):
    """Verify timeout restrictions are enforced during execution."""
    sandbox = ControlledResearchSandbox()
    infinite_loop_code = """
def research_strategy(bars, parameters):
    while True:
        pass
"""
    with mock.patch.object(sandbox, "is_enabled", return_value=True):
        res = sandbox.execute_candidate("prop_4", infinite_loop_code, "research_strategy", mock_bars, timeout_seconds=1)
        assert res.status == ExperimentStatus.TIMEOUT
        assert res.is_safe is False
        assert "timed out" in res.stderr.lower()

def test_human_approval_required():
    """Verify explicit human approval is required to approve candidate for research."""
    sandbox = ControlledResearchSandbox()
    with mock.patch.object(sandbox, "is_enabled", return_value=True):
        assert sandbox.approve_candidate_for_research("prop_5", human_approved=False) is False
        assert sandbox.is_candidate_approved("prop_5") is False

        assert sandbox.approve_candidate_for_research("prop_5", human_approved=True) is True
        assert sandbox.is_candidate_approved("prop_5") is True

def test_execute_live_blocked():
    """Verify live trade execution is explicitly forbidden."""
    sandbox = ControlledResearchSandbox()
    with pytest.raises(PermissionError, match="strictly forbidden"):
        sandbox.execute_live()
