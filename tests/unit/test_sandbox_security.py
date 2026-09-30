import pytest
from app.sandbox.analyzer import ASTSecurityValidator
from app.sandbox.executor import SandboxExecutor
from app.core.models import MarketBar

def test_sandbox_dunder_name_bypass():
    validator = ASTSecurityValidator()
    code = "import os\nprint(__builtins__['__import__']('os').system('dir'))"
    is_safe, errs = validator.validate(code)
    assert not is_safe
    assert any("Illegal dunder name access: __builtins__" in str(e) for e in errs) or any("Illegal import" in str(e) for e in errs)
    
def test_sandbox_dunder_attr_bypass():
    validator = ASTSecurityValidator()
    code = "import builtins; builtins.__import__('os').system('dir')"
    is_safe, errs = validator.validate(code)
    assert not is_safe

def test_sandbox_executor_no_import():
    executor = SandboxExecutor()
    code = """
def entrypoint(bars, params):
    os = __import__('os')
    return None
"""
    result = executor.test_execution(code, "entrypoint", [], {})
    assert not result.is_safe
    assert result.status.name == "FAILED"
    assert "NameError: name '__import__' is not defined" in result.stderr

def test_sandbox_executor_pandas_io():
    executor = SandboxExecutor()
    code = """
def entrypoint(bars, params):
    pd.read_csv('test.csv')
    return None
"""
    result = executor.test_execution(code, "entrypoint", [], {})
    assert not result.is_safe
    assert result.status.name == "FAILED"
    assert "disabled in sandbox" in result.stderr
