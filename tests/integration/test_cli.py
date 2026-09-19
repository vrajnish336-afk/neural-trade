import subprocess
import json
import pytest
from pathlib import Path
from app.config import config

CLI_PATH = Path(__file__).parent.parent.parent / "cli.py"

def run_cli(*args, **kwargs):
    env = kwargs.get("env", None)
    return subprocess.run(
        ["python", str(CLI_PATH)] + list(args),
        capture_output=True,
        text=True,
        env=env
    )

def test_cli_help():
    res = run_cli("--help")
    assert res.returncode == 0
    assert "Neural Trade Professional Research CLI" in res.stdout

def test_backtest_help():
    res = run_cli("backtest", "--help")
    assert res.returncode == 0
    assert "--strategy" in res.stdout

def test_research_help():
    res = run_cli("research", "--help")
    assert res.returncode == 0
    assert "--name" in res.stdout

def test_status():
    res = run_cli("status")
    assert res.returncode == 0
    assert "NEURAL TRADE SYSTEM STATUS" in res.stdout
    assert "PAPER_TRADING: ENABLED" in res.stdout

def test_valid_synthetic_backtest(tmp_path):
    out_json = tmp_path / "out.json"
    res = run_cli(
        "backtest",
        "--strategy", "breakout",
        "--dataset", "synthetic",
        "--symbol", "TEST",
        "--output-json", str(out_json),
        "--quiet"
    )
    assert res.returncode == 0
    assert "NEURAL TRADE — RESEARCH BACKTEST" in res.stdout
    assert "Status: COMPLETED" in res.stdout
    
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data["strategy"] == "breakout"
    assert data["symbol"] == "TEST"
    assert "net_profit" in data

def test_invalid_strategy():
    res = run_cli("backtest", "--strategy", "bogus")
    assert res.returncode == 2 # argparse error for invalid choice
    assert "invalid choice: 'bogus'" in res.stderr

def test_missing_required_research_name():
    res = run_cli("research", "--strategy", "breakout")
    assert res.returncode == 2
    assert "the following arguments are required: --name" in res.stderr

def test_invalid_numeric_capital():
    res = run_cli("backtest", "--strategy", "breakout", "--capital", "not_a_number")
    assert res.returncode == 2
    assert "invalid float value: 'not_a_number'" in res.stderr

def test_invalid_dataset_path():
    res = run_cli("backtest", "--strategy", "breakout", "--dataset", "nonexistent_dir")
    assert res.returncode == 1
    assert "Error: No data found" in res.stdout

def test_safety_gate_rejection(monkeypatch, tmp_path):
    import os
    env = os.environ.copy()
    env["LIVE_TRADING"] = "true"
    
    res = run_cli("status", env=env)
    assert res.returncode == 1
    assert "SAFETY ERROR: LIVE_TRADING is enabled" in res.stderr

def test_governed_research(tmp_path):
    out_json = tmp_path / "exp.json"
    res = run_cli(
        "research",
        "--name", "IntegrationTest",
        "--strategy", "trend_following",
        "--symbols", "TEST_A",
        "--seed", "99",
        "--output-json", str(out_json),
        "--quiet"
    )
    assert res.returncode == 0
    assert "NEURAL TRADE — GOVERNED RESEARCH" in res.stdout
    assert "Experiment: IntegrationTest" in res.stdout
    
    assert out_json.exists()
    data = json.loads(out_json.read_text())
    assert data["name"] == "IntegrationTest"
    assert "classification" in data

def test_deterministic_seed():
    # Run twice with same seed, outputs must match precisely
    res1 = run_cli("backtest", "--strategy", "breakout", "--seed", "123", "--quiet")
    res2 = run_cli("backtest", "--strategy", "breakout", "--seed", "123", "--quiet")
    assert res1.returncode == 0
    assert res2.returncode == 0
    
    # Check if Net PnL is the same
    def extract_pnl(stdout):
        for line in stdout.splitlines():
            if "Net PnL:" in line:
                return line
        return None
        
    pnl1 = extract_pnl(res1.stdout)
    pnl2 = extract_pnl(res2.stdout)
    assert pnl1 is not None
    assert pnl1 == pnl2
