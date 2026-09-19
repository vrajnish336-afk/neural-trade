import pytest
import os
from app.sandbox.analyzer import ASTSecurityValidator
from app.sandbox.executor import SandboxExecutor
from app.sandbox.service import SandboxService, AISandboxStrategyWrapper
from app.sandbox.models import ProposalStatus
from app.core.models import MarketBar
from datetime import datetime

@pytest.fixture
def validator():
    return ASTSecurityValidator()
    
def test_ast_rejects_exec(validator):
    code = "exec('import os; os.system(\"echo bad\")')"
    safe, errors = validator.validate(code)
    assert not safe
    assert any("exec" in e for e in errors)
    
def test_ast_rejects_subprocess(validator):
    code = "import subprocess\nsubprocess.run(['ls'])"
    safe, errors = validator.validate(code)
    assert not safe
    
def test_ast_rejects_open(validator):
    code = "open('/etc/passwd', 'r')"
    safe, errors = validator.validate(code)
    assert not safe
    assert any("open" in e for e in errors)
    
def test_ast_allows_pandas_math(validator):
    code = "import pandas as pd\nimport math\ndef research_strategy(bars, p):\n    return None"
    safe, errors = validator.validate(code)
    assert safe
    
def test_sandbox_executor_timeout():
    executor = SandboxExecutor(timeout_seconds=1)
    code = """
def research_strategy(bars, parameters):
    while True:
        pass
"""
    res = executor.test_execution(code, "research_strategy", [], {})
    assert res.status == "TIMEOUT"
    assert res.is_safe is False
    
def test_sandbox_executor_crash():
    executor = SandboxExecutor()
    code = """
def research_strategy(bars, parameters):
    raise ValueError("Intentional crash")
"""
    res = executor.test_execution(code, "research_strategy", [], {})
    assert res.status == "FAILED"
    assert "Intentional crash" in res.stderr
    
def test_sandbox_executor_success():
    executor = SandboxExecutor()
    code = """
def research_strategy(bars, parameters):
    from datetime import datetime, timezone
    return TradingSignal(symbol="BTC", direction="LONG", confidence=0.8, timestamp=datetime.now(timezone.utc), strategy="S", reason="Test")
"""
    res = executor.test_execution(code, "research_strategy", [], {})
    assert res.status == "COMPLETED"
    assert res.is_safe is True
    
def test_sandbox_service_pipeline():
    svc = SandboxService()
    svc.repo._init_db()
    
    code = """def research_strategy(bars, parameters):
    if not bars: return None
    from datetime import datetime, timezone
    return TradingSignal(symbol=bars[-1].symbol, direction="LONG", confidence=1.0, timestamp=datetime.now(timezone.utc), strategy="S", reason="Test")
"""
    proposal = svc.propose_code("StratTest", "T", "D", code)
    assert proposal.status == ProposalStatus.VALIDATING
    
    bars = [MarketBar(symbol="BTC", timestamp=datetime.utcnow(), open=1, high=1, low=1, close=1, volume=1)]
    valid = svc.validate_proposal(proposal, bars)
    
    assert valid is True
    assert proposal.status == ProposalStatus.SANDBOX_READY
    
    exp = svc.run_backtest(proposal, "dummy", bars, {})
    assert exp.status == "COMPLETED"
    assert "historically observed" in exp.evidence.lower()
    
    svc.approve_for_research(proposal.proposal_id)
    props = svc.repo.get_proposals()
    assert props[0].status == ProposalStatus.APPROVED_FOR_RESEARCH
