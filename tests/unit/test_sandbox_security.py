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
    assert "Sandbox error: Use of dunder methods (__) is strictly prohibited." in result.stderr

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

def test_sandbox_bare_import_load_rejected():
    validator = ASTSecurityValidator()
    code = "f = __import__"
    is_safe, errs = validator.validate(code)
    assert not is_safe
    assert any("Illegal dunder name access: __import__" in e or "Illegal builtin access" in e for e in errs)

def test_sandbox_attribute_on_dunder_rejected():
    validator = ASTSecurityValidator()
    code = "x = ().__class__"
    is_safe, errs = validator.validate(code)
    assert not is_safe
    assert any("Illegal dunder attribute access" in e for e in errs)

def test_sandbox_ast_blocks_to_csv():
    validator = ASTSecurityValidator()
    code = "df.to_csv('out.csv')"
    is_safe, errs = validator.validate(code)
    assert not is_safe
    assert any("Potentially dangerous attribute access detected: to_csv" in e for e in errs)

def test_sandbox_dataframe_to_csv_blocked():
    executor = SandboxExecutor()
    code = """
def entrypoint(bars, params):
    df = pd.DataFrame({'a': [1, 2]})
    df.to_csv('escape.csv')
    return None
"""
    result = executor.test_execution(code, "entrypoint", [], {})
    assert not result.is_safe
    assert result.status.name == "FAILED"
    assert "disabled in sandbox" in result.stderr
