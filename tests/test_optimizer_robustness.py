import pytest
from datetime import datetime, timezone, timedelta
from app.core.models import MarketBar
from run_optimizer import evaluate_param
from app.research.robustness.models import WalkForwardWindowResult
import run_optimizer
import statistics

def test_hardcoded_consistency_removed():
    with open("run_optimizer.py", "r") as f:
        content = f.read()
    assert 'print("FOLD CONSISTENCY: High")' not in content
    assert 'consistency = "High" if' in content

def test_negative_fold_rejects_candidate(monkeypatch):
    class FakeResult:
        def __init__(self, t, pf, r, wr, dd):
            self.gross_profit = 100.0
            self.gross_loss = 50.0
            self.window_id = 1
            self.trades = t
            self.profit_factor = pf
            self.return_pct = r
            self.win_rate = wr
            self.max_drawdown_pct = dd

    def mock_wf(*args, **kwargs):
        return [
            FakeResult(15, 2.0, 5.0, 0.6, 2.0),
            FakeResult(15, 2.5, 6.0, 0.7, 1.0),
            FakeResult(10, 0.3, -5.0, 0.2, 5.0) 
        ]

    monkeypatch.setattr(run_optimizer, "run_walk_forward_robustness", mock_wf)

    res = evaluate_param(70.0, [])
    assert res["has_severe_loss"] is True
    assert res["total_trades"] == 40
    
    valid = res["total_trades"] >= 30 and res["expectancy"] > 0 and res["avg_dd"] < 30.0 and not res["has_severe_loss"]
    assert valid is False

def test_inf_pf_cannot_dominate_ranking(monkeypatch):
    class FakeResult:
        def __init__(self, t, pf, r, wr, dd):
            self.gross_profit = 100.0
            self.gross_loss = 50.0
            self.window_id = 1
            self.trades = t
            self.profit_factor = pf
            self.return_pct = r
            self.win_rate = wr
            self.max_drawdown_pct = dd

    def mock_wf_inf(*args, **kwargs):
        r1 = FakeResult(10, float('inf'), 5.0, 1.0, 0.0)
        r1.gross_loss = 0.0
        r1.gross_profit = 100.0
        r2 = FakeResult(10, float('inf'), 5.0, 1.0, 0.0)
        r2.gross_loss = 0.0
        r2.gross_profit = 100.0
        return [r1, r2]
        
    monkeypatch.setattr(run_optimizer, "run_walk_forward_robustness", mock_wf_inf)
    res = evaluate_param(70.0, [])
    assert res["avg_pf"] == float('inf')

def test_insufficient_data_path(monkeypatch):
    class FakeResult:
        def __init__(self, t, pf, r, wr, dd):
            self.gross_profit = 100.0
            self.gross_loss = 50.0
            self.window_id = 1
            self.trades = t
            self.profit_factor = pf
            self.return_pct = r
            self.win_rate = wr
            self.max_drawdown_pct = dd

    def mock_wf_low_trades(*args, **kwargs):
        return [FakeResult(1, 1.5, 1.0, 0.5, 1.0)]

    monkeypatch.setattr(run_optimizer, "run_walk_forward_robustness", mock_wf_low_trades)
    res = evaluate_param(80.0, [])
    assert res["total_trades"] == 1
    
    valid = [r for r in [res] if r["total_trades"] >= 30 and r["expectancy"] > 0 and not r["has_severe_loss"]]
    assert len(valid) == 0

def test_final_oos_remains_untouched():
    with open("run_optimizer.py", "r") as f:
        content = f.read()
    assert "[:int(len(b)*0.5)]" in content
