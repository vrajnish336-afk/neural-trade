import pytest
from datetime import datetime, timezone
from app.core.models import MarketBar, TradingSignal
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from app.strategies.base import Strategy
from app.config import config
from app.forecasting.service import ForecastingService
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from unittest.mock import MagicMock

class MockStrategy(Strategy):
    def __init__(self, name, direction='LONG'):
        self._name = name
        self.direction = direction
    @property
    def name(self): return self._name
    def generate_signal(self, bars):
        return TradingSignal(symbol='BTC', timestamp=bars[-1].timestamp, direction=self.direction, strategy=self.name, confidence=0.8, entry_price=10, stop_loss=9, take_profit=11, reason='test')
    def get_parameters(self): return {}

class MockForecastingService(ForecastingService):
    def __init__(self): pass
    def generate_forecast(self, *args, **kwargs): return None

def test_quarantine_telemetry_leak():
    config.QUARANTINE_MEAN_REVERSION = True
    bars = [MarketBar(symbol='BTC', timestamp=datetime.now(timezone.utc), open=10, high=10, low=10, close=10, volume=10)]
    strategies = [MockStrategy('Breakout_20'), MockStrategy('MeanReversion_20')]
    ensemble = StrategyEnsemble(strategies=strategies, min_score=0.0)
    risk_engine = RiskEngine(PortfolioRiskLimits(initial_equity=1000))
    mock_intel = MagicMock()
    mock_intel.generate_intelligence.return_value = None
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=mock_intel,
        forecasting_service=MockForecastingService()
    )
    
    decision = orchestrator.evaluate('BTC', bars, 1000, 0, 0)
    
    strategies_in_signals = [s['strategy'] for s in decision.strategy_signals]
    assert 'Breakout_20' in strategies_in_signals
    assert 'MeanReversion_20' not in strategies_in_signals
    assert len(strategies_in_signals) == 1

