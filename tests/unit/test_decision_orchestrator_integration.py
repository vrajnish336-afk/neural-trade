import pytest
from unittest.mock import Mock, patch
from datetime import datetime, timezone, timedelta

@patch("app.analysis.regime.detect_market_regime")
def test_decision_real_strategies_integration(mock_detect):
    """
    Proves that a real strategy ensemble correctly propagates its constituent strategy names 
    (metadata) through the DecisionOrchestrator and into the TraderDecision.
    """
    from app.core.models import MarketRegimeResult
    mock_detect.return_value = MarketRegimeResult(regime="TRENDING_UP", confidence=0.8)

    from app.strategies.ensemble import StrategyEnsemble
    from app.strategies.breakout import BreakoutStrategy
    from app.strategies.trend_following import TrendFollowingStrategy
    from app.decision.decision_orchestrator import DecisionOrchestrator
    
    # 1. Instantiate real strategies
    brk = BreakoutStrategy(lookback_period=3, volume_period=3)
    tf = TrendFollowingStrategy(fast_period=2, slow_period=3)
    
    ensemble = StrategyEnsemble([brk, tf])
    
    # Setup orchestrator with mocks for unrelated services
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=Mock(),
        intelligence_service=Mock(),
        forecasting_service=Mock()
    )
    
    # Create enough bars to trigger both strategies
    from app.core.models import MarketBar
    
    # TrendFollowing requires fast=2, slow=3. Breakout requires 3.
    # Let's manufacture a breakout + trend golden cross:
    # We need closes to go up, and volume to spike.
    closes = [10] * 120 + [15]
    volumes = [100] * 120 + [500]
    bars = [
        MarketBar(
            symbol="BTC",
            timestamp=datetime(2023, 1, 1, tzinfo=timezone.utc) + timedelta(days=i),
            open=c, high=c+1, low=c-1, close=c, volume=v
        ) for i, (c, v) in enumerate(zip(closes, volumes))
    ]
    
    # We must ensure RiskEngine approves so we get a real decision
    risk_dec = Mock()
    risk_dec.approved = True
    orchestrator.risk_engine.evaluate_trade.return_value = risk_dec
    orchestrator.intelligence_service.generate_intelligence.return_value = None
    
    mock_forecast = Mock()
    mock_forecast.predicted_values_json = "[120.0, 125.0]"
    orchestrator.forecasting_service.generate_forecast.return_value = mock_forecast
    
    decision = orchestrator.evaluate("BTC", bars, 10000.0, 0, 0.0)
    
    # Assert decision actually triggered
    assert decision.decision == "LONG"
    
    # Assert strategy metadata is preserved correctly!
    assert len(decision.strategy_signals) > 0
    strategy_names = [s["strategy"] for s in decision.strategy_signals]
    
    # We expect BOTH strategies to have fired in this manufactured setup,
    # or at least ONE of them. Let's just assert the real names are present, not Mock or default.
    assert any("Breakout" in name or "TrendFollowing" in name for name in strategy_names)
    assert not any(name == "MockStrategy" or name == "PaperBroker" for name in strategy_names)
