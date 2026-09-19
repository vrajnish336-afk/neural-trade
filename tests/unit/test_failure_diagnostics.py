import pytest
from datetime import datetime, timezone
from app.backtesting.models import BacktestTrade
from app.analysis.failure_diagnostics import FailureDiagnosticEngine

def test_failure_feature_extraction_and_outcome_attachment():
    t = datetime(2022, 1, 1, tzinfo=timezone.utc)
    trades = [
        BacktestTrade(
            symbol="TEST", direction="LONG", entry_time=t, entry_price=100.0,
            exit_time=t, exit_price=110.0, quantity=1.0, entry_cost=0.0,
            exit_cost=0.0, slippage_cost=0.0, realized_pnl=10.0, exit_reason="Stop Loss",
            regime="TRENDING_UP", strategies="Ensemble(Breakout_20)", score=85.0
        ),
        BacktestTrade(
            symbol="TEST", direction="SHORT", entry_time=t, entry_price=100.0,
            exit_time=t, exit_price=105.0, quantity=1.0, entry_cost=0.0,
            exit_cost=0.0, slippage_cost=0.0, realized_pnl=-5.0, exit_reason="Stop Loss",
            regime="TRENDING_UP", strategies="Ensemble(Breakout_20)", score=45.0
        )
    ]
    
    engine = FailureDiagnosticEngine(trades)
    df = engine._df
    
    assert len(df) == 2
    assert df.iloc[0]['is_win'] == True
    assert df.iloc[1]['is_win'] == False
    assert df.iloc[0]['score_bucket'] == "80-100"
    assert df.iloc[1]['score_bucket'] == "40-59"

def test_regime_matrix_and_sample_classification():
    t = datetime(2022, 1, 1, tzinfo=timezone.utc)
    # Create 4 wins, 1 loss for TRENDING_DOWN (5 trades -> VERY_LOW_SAMPLE)
    trades = [
        BacktestTrade(
            symbol="TEST", direction="LONG", entry_time=t, entry_price=100.0,
            exit_time=t, exit_price=110.0, quantity=1.0, entry_cost=0.0,
            exit_cost=0.0, slippage_cost=0.0, realized_pnl=10.0, exit_reason="TP",
            regime="TRENDING_DOWN", strategies="S1", score=80.0
        )
    ] * 4
    trades.append(
        BacktestTrade(
            symbol="TEST", direction="LONG", entry_time=t, entry_price=100.0,
            exit_time=t, exit_price=90.0, quantity=1.0, entry_cost=0.0,
            exit_cost=0.0, slippage_cost=0.0, realized_pnl=-10.0, exit_reason="SL",
            regime="TRENDING_DOWN", strategies="S1", score=80.0
        )
    )
    
    engine = FailureDiagnosticEngine(trades)
    matrix = engine.get_regime_failure_matrix()
    
    assert len(matrix) == 1
    res = matrix[0]
    assert res['strategy'] == "S1"
    assert res['regime'] == "TRENDING_DOWN"
    assert res['sample_count'] == 5
    assert res['wins'] == 4
    assert res['losses'] == 1
    assert res['win_rate'] == 80.0
    assert res['profit_factor'] == 40.0 / 10.0
    assert res['sample_classification'] == "LOW_SAMPLE"
    assert res['quality_status'] == "INSUFFICIENT_DATA"

def test_trending_up_diagnostics():
    t = datetime(2022, 1, 1, tzinfo=timezone.utc)
    trades = [
        BacktestTrade(
            symbol="TEST", direction="LONG", entry_time=t, entry_price=100.0,
            exit_time=t, exit_price=90.0, quantity=1.0, entry_cost=0.0,
            exit_cost=0.0, slippage_cost=0.0, realized_pnl=-10.0, exit_reason="SL",
            regime="TRENDING_UP", strategies="S1", score=80.0
        )
    ] * 3
    
    engine = FailureDiagnosticEngine(trades)
    diag = engine.diagnose_trending_up()
    
    assert diag["status"] == "DIAGNOSED"
    assert diag["total_trades"] == 3
    assert diag["loss_count"] == 3
    assert diag["loss_by_exit_reason"]["SL"] == 3
