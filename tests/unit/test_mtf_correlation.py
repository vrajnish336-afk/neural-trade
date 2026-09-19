import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock
import pandas as pd

from app.core.models import TradingSignal, MarketBar, MarketRegimeResult
from app.decision.weighting import StrategyWeightingService, BoundedWeightingResult
from app.learning.paper_evolution_models import PaperResearchLesson, LessonState
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.decision.decision_orchestrator import DecisionOrchestrator
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.decision.models import TraderDecision
from app.strategies.base import Strategy

class DummyStrategy(Strategy):
    def __init__(self, strat_name: str, direction: str):
        self._name = strat_name
        self.direction = direction
        
    @property
    def name(self):
        return self._name
        
    def generate_signal(self, bars):
        return TradingSignal(
            symbol="BTC",
            strategy=self.name,
            direction=self.direction,
            reason="Test",
            confidence=0.8,
            entry_price=100.0,
            stop_loss=90.0 if self.direction == "LONG" else 110.0,
            take_profit=120.0 if self.direction == "LONG" else 80.0,
            timestamp=datetime.now(timezone.utc)
        )

@pytest.fixture
def mock_evo_repo():
    repo = MagicMock(spec=PaperEvolutionRepository)
    repo.get_lessons.return_value = []
    return repo

def test_mtf_correlation_weighting_match(mock_evo_repo):
    as_of = datetime.now(timezone.utc)
    
    lesson_match = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=10, wins=9, losses=1, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        mtf_alignment="ALIGNED_BULLISH",
        portfolio_correlation="LOW_CORRELATION"
    )
    
    lesson_match2 = PaperResearchLesson(
        lesson_id="2", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=10, wins=9, losses=1, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        mtf_alignment="ALIGNED_BULLISH",
        portfolio_correlation="LOW_CORRELATION",
        cross_asset_symbols=["ETH"]
    )
    
    lesson_match3 = PaperResearchLesson(
        lesson_id="3", source_trade_ids=[], strategy="Breakout", regime="TRENDING_DOWN",
        observation="", sample_count=10, wins=9, losses=1, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        mtf_alignment="ALIGNED_BULLISH",
        portfolio_correlation="LOW_CORRELATION",
        cross_asset_symbols=["SOL"]
    )
    
    mock_evo_repo.get_lessons.return_value = [lesson_match, lesson_match2, lesson_match3]
    svc = StrategyWeightingService(mock_evo_repo)
    
    signals = [TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=as_of)]
    weights = svc.calculate_weights(signals, as_of, current_mtf="ALIGNED_BULLISH", current_corr="LOW_CORRELATION")
    assert weights["Breakout"].weight_multiplier > 1.0

def test_orchestrator_correlation_calculation():
    s1 = DummyStrategy("DummyBreakout", "LONG")
    ensemble = StrategyEnsemble([s1])
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    intel_mock = MagicMock()
    intel_mock.generate_intelligence.return_value = None
    
    mock_paper_repo = MagicMock()
    mock_paper_repo.get_open_positions.return_value = [{"symbol": "ETH"}, {"symbol": "SOL"}]
    
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel_mock,
        forecasting_service=MagicMock(),
        paper_repository=mock_paper_repo,
        weighting_service=None
    )
    
    as_of = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC", timestamp=as_of, open=1, high=1, low=1, close=100, volume=1)] * 55
        
    decision = orchestrator.evaluate("BTC", bars, 10000.0, 0, 0.0)
    assert decision.portfolio_correlation == "UNKNOWN_NO_DATA"

def test_orchestrator_low_correlation():
    s1 = DummyStrategy("DummyBreakout", "LONG")
    ensemble = StrategyEnsemble([s1])
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    intel_mock = MagicMock()
    intel_mock.generate_intelligence.return_value = None
    
    mock_paper_repo = MagicMock()
    mock_paper_repo.get_open_positions.return_value = []
    
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel_mock,
        forecasting_service=MagicMock(),
        paper_repository=mock_paper_repo,
        weighting_service=None
    )
    
    as_of = datetime.now(timezone.utc)
    bars = [MarketBar(symbol="BTC", timestamp=as_of, open=1, high=1, low=1, close=100, volume=1)] * 55
    decision = orchestrator.evaluate("BTC", bars, 10000.0, 0, 0.0)
    assert decision.portfolio_correlation == "LOW_CORRELATION"

def test_orchestrator_real_data_provider_high_correlation():
    s1 = DummyStrategy("DummyBreakout", "LONG")
    ensemble = StrategyEnsemble([s1])
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    intel_mock = MagicMock()
    intel_mock.generate_intelligence.return_value = None
    
    mock_paper_repo = MagicMock()
    mock_paper_repo.get_open_positions.return_value = [{"symbol": "ETH"}]
    
    mock_data_provider = MagicMock()
    # Mock identical bars to force correlation
    as_of = datetime.now(timezone.utc)
    btc_bars = [MarketBar(symbol="BTC", timestamp=as_of - timedelta(days=50-i), open=1, high=1, low=1, close=100+i, volume=1) for i in range(50)]
    eth_bars = [MarketBar(symbol="ETH", timestamp=as_of - timedelta(days=50-i), open=1, high=1, low=1, close=50+i*0.5, volume=1) for i in range(50)]
    mock_data_provider.get_historical_bars.return_value = eth_bars
    
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel_mock,
        forecasting_service=MagicMock(),
        paper_repository=mock_paper_repo,
        data_provider=mock_data_provider,
        weighting_service=None
    )
    
    decision = orchestrator.evaluate("BTC", btc_bars, 10000.0, 0, 0.0)
    assert decision.portfolio_correlation == "HIGH_CORRELATION"
