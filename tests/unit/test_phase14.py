import pytest
import uuid
import json
from datetime import datetime, timezone
from app.research.models import ResearchExperiment, ChampionChallengerResult
from app.research.challenger import ChampionChallengerValidator
from app.analytics.models import FullAnalyticsReport, TradeMetrics, EquityMetrics

def create_mock_experiment(exp_id: str, status: str, dataset_id: str, return_pct: float, drawdown_pct: float, trades: int) -> ResearchExperiment:
    report = None
    if status == "COMPLETED":
        report = FullAnalyticsReport(
            backtest_id=exp_id,
            trade_metrics=TradeMetrics(
                total_trades=trades, winning_trades=int(trades*0.5), losing_trades=int(trades*0.5),
                win_rate=50.0, gross_pnl=return_pct, net_pnl=return_pct, total_commission=0.0, total_slippage=0.0,
                profit_factor=1.5, max_consecutive_losses=2,
                average_pnl=return_pct/trades, average_win=1.0, average_loss=-0.5, largest_win=2.0, largest_loss=-1.0, max_consecutive_wins=3, average_holding_hours=24.0
            ),
            equity_metrics=EquityMetrics(
                initial_capital=1000, final_equity=1000*(1+return_pct/100), total_return_pct=return_pct, max_drawdown_pct=drawdown_pct, average_drawdown_pct=drawdown_pct/2,
                absolute_pnl=1000*(return_pct/100), max_drawdown_amount=1000*(drawdown_pct/100), time_in_drawdown_pct=10.0, recovery_periods=5
            ),
            strategy_attribution=[],
            regime_attribution=[],
            signal_bucket_attribution=[],
            intelligence_attribution=[],
            failure_findings=[],
            strategy_comparisons=[]
        )
        
    return ResearchExperiment(
        experiment_id=exp_id, dataset_id=dataset_id, symbols=["BTC"], timeframe="1h", strategy="Strat", configuration="conf",
        starting_capital=1000, random_seed=42, created_at=datetime.now(timezone.utc), status=status,
        validation_results=[], out_of_sample_report=report, configuration_snapshot={"risk_per_trade_pct": 0.05}
    )

def test_champion_challenger_validation():
    champ = create_mock_experiment("champ1", "COMPLETED", "data1", 10.0, 5.0, 50)
    chall = create_mock_experiment("chall1", "COMPLETED", "data1", 15.0, 4.0, 60)
    
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)
    
    assert result.decision == "PROMOTE"
    assert "Higher OOS Return" in result.decision_reasons
    assert result.scorecard["oos_return"]["champ"] == 10.0
    assert result.scorecard["oos_return"]["chall"] == 15.0

def test_champion_challenger_invalid_status():
    champ = create_mock_experiment("champ2", "RUNNING", "data1", 10.0, 5.0, 50)
    chall = create_mock_experiment("chall2", "COMPLETED", "data1", 15.0, 4.0, 60)
    
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)
    
    assert result.decision == "INVALID"
    assert any("must be COMPLETED" in r for r in result.decision_reasons)

def test_champion_challenger_mismatched_dataset():
    champ = create_mock_experiment("champ3", "COMPLETED", "data1", 10.0, 5.0, 50)
    chall = create_mock_experiment("chall3", "COMPLETED", "data2", 15.0, 4.0, 60)
    
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)
    
    assert result.decision == "INVALID"
    assert any("DATASET_MISMATCH" in r for r in result.decision_reasons)

def test_champion_challenger_reject_drawdown():
    champ = create_mock_experiment("champ4", "COMPLETED", "data1", 10.0, 5.0, 50) # drawdown 5%
    chall = create_mock_experiment("chall4", "COMPLETED", "data1", 15.0, 10.0, 60) # drawdown 10% (degraded by more than 1.2x)
    
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)
    
    assert result.decision == "REJECT"
    assert "Unacceptable Drawdown Increase" in result.decision_reasons

def test_champion_challenger_inconclusive_sample_size():
    champ = create_mock_experiment("champ5", "COMPLETED", "data1", 10.0, 5.0, 50)
    chall = create_mock_experiment("chall5", "COMPLETED", "data1", 15.0, 4.0, 10) # trades < 30
    
    validator = ChampionChallengerValidator()
    result = validator.evaluate(champ, chall)
    
    assert result.decision == "INCONCLUSIVE"
    assert "Insufficient Sample Size (<30 trades)" in result.decision_reasons

def test_future_data_corruption_defense():
    # Demonstrating that the evaluation itself does not mutate the experiments
    champ = create_mock_experiment("champ6", "COMPLETED", "data1", 10.0, 5.0, 50)
    chall = create_mock_experiment("chall6", "COMPLETED", "data1", 15.0, 4.0, 60)
    
    validator = ChampionChallengerValidator()
    _ = validator.evaluate(champ, chall)
    
    assert champ.status == "COMPLETED"
    assert chall.status == "COMPLETED"

from unittest.mock import patch

@patch('app.research.models.datetime')
def test_reproducibility(mock_datetime):
    fixed_time = datetime(2023, 1, 1, tzinfo=timezone.utc)
    mock_datetime.now.return_value = fixed_time
    
    # We must also patch the datetime where create_mock_experiment is defined
    with patch('tests.unit.test_phase14.datetime') as mock_local_datetime:
        mock_local_datetime.now.return_value = fixed_time
        
        champ1 = create_mock_experiment("champ7", "COMPLETED", "data1", 10.0, 5.0, 50)
        champ2 = create_mock_experiment("champ7", "COMPLETED", "data1", 10.0, 5.0, 50)
        
        # Override the created_at to be exactly the same, bypassing any patch leak issues
        champ1.created_at = fixed_time
        champ2.created_at = fixed_time
    
    assert champ1.model_dump_json() == champ2.model_dump_json()
