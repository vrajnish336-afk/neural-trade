import pytest
import os
import sys
import platform
import subprocess
from app.research.models import (
    ResearchExperiment, 
    ResearchLineage, 
    EnvironmentLineage, 
    CodeLineage, 
    StrategyLineage, 
    ConfigurationLineage
)
from app.analytics.models import TradeMetrics

def test_legacy_experiment_loads_without_lineage():
    # Simulate a JSON from database that has no lineage field
    legacy_json = """
    {
        "experiment_id": "test_legacy_123",
        "experiment_name": "Legacy Run",
        "experiment_type": "BACKTEST",
        "dataset_id": "test_ds",
        "symbols": ["BTC"],
        "timeframe": "1h",
        "strategy": "breakout",
        "configuration": "snapshot",
        "starting_capital": 10000.0,
        "random_seed": 42,
        "created_at": "2024-01-01T00:00:00Z",
        "status": "COMPLETED",
        "validation_results": []
    }
    """
    exp = ResearchExperiment.model_validate_json(legacy_json)
    assert exp.experiment_id == "test_legacy_123"
    assert exp.lineage is None

def test_legacy_trade_metrics_defaults():
    # Make sure old TradeMetrics parses cleanly missing the new Phase 7/8 fields
    legacy_trade_metrics_json = """
    {
        "total_trades": 10,
        "winning_trades": 6,
        "losing_trades": 4,
        "win_rate": 60.0,
        "average_pnl": 1.0,
        "average_win": 2.0,
        "average_loss": -1.0,
        "profit_factor": 1.5,
        "largest_win": 3.0,
        "largest_loss": -2.0,
        "max_consecutive_wins": 3,
        "max_consecutive_losses": 2,
        "average_holding_hours": 24.0
    }
    """
    tm = TradeMetrics.model_validate_json(legacy_trade_metrics_json)
    assert tm.gross_pnl == 0.0
    assert tm.net_pnl == 0.0
    assert tm.total_commission == 0.0
    assert tm.total_slippage == 0.0

def test_new_experiment_with_lineage_serializes():
    env_lineage = EnvironmentLineage(python_version="3.11", os_name="Linux")
    code_lineage = CodeLineage(commit_hash="abc1234", is_dirty=False)
    strat_lineage = StrategyLineage(strategy_name="breakout", parameters={"lookback_period": 20})
    config_lineage = ConfigurationLineage(
        cost_model={"commission_rate": 0.001, "slippage_rate": 0.0005},
        risk_model={"risk_per_trade_pct": 0.05},
        capital=10000.0
    )
    
    lineage = ResearchLineage(
        environment=env_lineage,
        code=code_lineage,
        strategy=strat_lineage,
        configuration=config_lineage
    )
    
    exp = ResearchExperiment(
        experiment_id="test_new_123",
        dataset_id="test_ds",
        symbols=["BTC"],
        timeframe="1h",
        strategy="breakout",
        configuration="snapshot",
        starting_capital=10000.0,
        random_seed=42,
        created_at="2024-01-01T00:00:00Z",
        status="COMPLETED",
        validation_results=[],
        lineage=lineage
    )
    
    json_str = exp.model_dump_json()
    assert "environment" in json_str
    assert "abc1234" in json_str
    assert "lookback_period" in json_str
    
    # Reload
    reloaded = ResearchExperiment.model_validate_json(json_str)
    assert reloaded.lineage.code.commit_hash == "abc1234"
    assert reloaded.lineage.strategy.parameters["lookback_period"] == 20

def test_actual_strategy_parameters_captured():
    from app.strategies.breakout import BreakoutStrategy
    from app.strategies.mean_reversion import MeanReversionStrategy
    from app.strategies.trend_following import TrendFollowingStrategy
    
    b = BreakoutStrategy(lookback_period=50)
    assert b.get_parameters()["lookback_period"] == 50
    
    m = MeanReversionStrategy(sma_period=100)
    assert m.get_parameters()["sma_period"] == 100
    
    t = TrendFollowingStrategy(fast_period=15)
    assert t.get_parameters()["fast_period"] == 15
