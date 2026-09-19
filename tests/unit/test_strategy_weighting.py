import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

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

def test_equal_weights_insufficient_evidence(mock_evo_repo):
    svc = StrategyWeightingService(mock_evo_repo)
    signals = [
        TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=datetime.now(timezone.utc)),
        TradingSignal(symbol="BTC", strategy="MeanReversion", direction="SHORT", reason="", confidence=0.8, entry_price=100, stop_loss=110, take_profit=90, timestamp=datetime.now(timezone.utc))
    ]
    weights = svc.calculate_weights(signals, datetime.now(timezone.utc))
    
    assert weights["Breakout"].weight_multiplier == 1.0
    assert "INSUFFICIENT_EVIDENCE" in weights["Breakout"].reason
    assert weights["MeanReversion"].weight_multiplier == 1.0

def test_chronological_as_of_filtering(mock_evo_repo):
    as_of = datetime(2023, 1, 15, tzinfo=timezone.utc)
    
    past_lesson1 = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime(2023, 1, 10, tzinfo=timezone.utc),
        data_window_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
        data_window_end=datetime(2023, 1, 9, tzinfo=timezone.utc),
        cross_asset_symbols=["BTC"]
    )
    past_lesson2 = PaperResearchLesson(
        lesson_id="1_b", source_trade_ids=[], strategy="Breakout", regime="TRENDING_DOWN",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime(2023, 1, 12, tzinfo=timezone.utc),
        data_window_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
        data_window_end=datetime(2023, 1, 9, tzinfo=timezone.utc),
        cross_asset_symbols=["ETH"]
    )
    
    future_lesson = PaperResearchLesson(
        lesson_id="2", source_trade_ids=[], strategy="MeanReversion", regime="TRENDING_UP",
        observation="", sample_count=10, wins=9, losses=1, observed_pnl=200,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime(2023, 1, 20, tzinfo=timezone.utc), # After as_of
        data_window_start=datetime(2023, 1, 11, tzinfo=timezone.utc),
        data_window_end=datetime(2023, 1, 19, tzinfo=timezone.utc)
    )
    
    mock_evo_repo.get_lessons.return_value = [past_lesson1, past_lesson2, future_lesson]
    
    svc = StrategyWeightingService(mock_evo_repo)
    signals = [
        TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=as_of),
        TradingSignal(symbol="BTC", strategy="MeanReversion", direction="SHORT", reason="", confidence=0.8, entry_price=100, stop_loss=110, take_profit=90, timestamp=as_of)
    ]
    
    weights = svc.calculate_weights(signals, as_of)
    
    # Breakout gets strong evidence
    assert weights["Breakout"].weight_multiplier > 1.0
    
    # MeanReversion future lesson ignored, falls back to insufficient evidence
    assert weights["MeanReversion"].weight_multiplier == 1.0
    assert "INSUFFICIENT_EVIDENCE" in weights["MeanReversion"].reason

def test_minimum_sample_gate(mock_evo_repo):
    as_of = datetime.now(timezone.utc)
    
    lesson = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=4, wins=4, losses=0, observed_pnl=100, # 100% WR but n=4
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2)
    )
    
    mock_evo_repo.get_lessons.return_value = [lesson]
    svc = StrategyWeightingService(mock_evo_repo)
    
    signals = [TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=as_of)]
    weights = svc.calculate_weights(signals, as_of)
    
    assert weights["Breakout"].weight_multiplier == 1.0
    # Because we only have 1 dataset and n=4, MetaAnalysisEngine correctly synthesizes PROMISING_BUT_FRAGILE
    # and leaves weighting at neutral 1.0
    assert "PROMISING_BUT_FRAGILE" in weights["Breakout"].reason

def test_stale_evidence_fallback(mock_evo_repo):
    as_of = datetime(2023, 5, 1, tzinfo=timezone.utc)
    
    stale_lesson = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc), # 4 months old
        data_window_start=datetime(2022, 12, 1, tzinfo=timezone.utc),
        data_window_end=datetime(2022, 12, 31, tzinfo=timezone.utc)
    )
    
    mock_evo_repo.get_lessons.return_value = [stale_lesson]
    svc = StrategyWeightingService(mock_evo_repo)
    
    signals = [TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=as_of)]
    weights = svc.calculate_weights(signals, as_of)
    
    assert weights["Breakout"].weight_multiplier == 1.0
    assert "STALE_EVIDENCE" in weights["Breakout"].reason

def test_bounds_min_max(mock_evo_repo):
    as_of = datetime.now(timezone.utc)
    
    lesson1 = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="Breakout", regime="TRENDING_UP",
        observation="", sample_count=100, wins=95, losses=5, observed_pnl=10000,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["BTC"]
    )
    lesson2 = PaperResearchLesson(
        lesson_id="2", source_trade_ids=[], strategy="Breakout", regime="TRENDING_DOWN",
        observation="", sample_count=100, wins=95, losses=5, observed_pnl=10000,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["ETH"]
    )
    
    lesson3 = PaperResearchLesson(
        lesson_id="3", source_trade_ids=[], strategy="Breakout", regime="HIGH_VOLATILITY",
        observation="", sample_count=100, wins=95, losses=5, observed_pnl=10000,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["SOL"]
    )
    
    mock_evo_repo.get_lessons.return_value = [lesson1, lesson2, lesson3]
    svc = StrategyWeightingService(mock_evo_repo)
    svc.max_weight = 1.25 # Artificial constraint
    
    signals = [TradingSignal(symbol="BTC", strategy="Breakout", direction="LONG", reason="", confidence=0.8, entry_price=100, stop_loss=90, take_profit=110, timestamp=as_of)]
    weights = svc.calculate_weights(signals, as_of)
    
    # Established gets base_mult 1.25, max_weight applies
    assert weights["Breakout"].weight_multiplier == 1.25

@patch("app.analysis.regime.detect_market_regime")
def test_decision_orchestrator_integration(mock_detect, mock_evo_repo):
    from app.core.models import MarketRegimeResult
    mock_detect.return_value = MarketRegimeResult(regime="TRENDING_UP", confidence=0.8)
    
    as_of = datetime.now(timezone.utc)
    
    lesson1 = PaperResearchLesson(
        lesson_id="1", source_trade_ids=[], strategy="DummyBreakout", regime="TRENDING_UP",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["BTC"]
    )
    lesson1_b = PaperResearchLesson(
        lesson_id="1_b", source_trade_ids=[], strategy="DummyBreakout", regime="TRENDING_DOWN",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["ETH"]
    )
    lesson2 = PaperResearchLesson(
        lesson_id="2", source_trade_ids=[], strategy="DummyReversion", regime="TRENDING_UP",
        observation="", sample_count=10, wins=2, losses=8, observed_pnl=-100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["BTC"]
    )
    lesson2_b = PaperResearchLesson(
        lesson_id="2_b", source_trade_ids=[], strategy="DummyReversion", regime="TRENDING_DOWN",
        observation="", sample_count=10, wins=2, losses=8, observed_pnl=-100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["ETH"]
    )
    
    lesson1_c = PaperResearchLesson(
        lesson_id="1_c", source_trade_ids=[], strategy="DummyBreakout", regime="HIGH_VOLATILITY",
        observation="", sample_count=10, wins=8, losses=2, observed_pnl=100,
        confidence_status=LessonState.VALIDATED,
        created_at=as_of - timedelta(days=1),
        data_window_start=as_of - timedelta(days=5),
        data_window_end=as_of - timedelta(days=2),
        cross_asset_symbols=["SOL"]
    )
    
    mock_evo_repo.get_lessons.return_value = [lesson1, lesson1_b, lesson1_c, lesson2, lesson2_b]
    
    svc = StrategyWeightingService(mock_evo_repo)
    
    s1 = DummyStrategy("DummyBreakout", "LONG")
    s2 = DummyStrategy("DummyReversion", "SHORT")
    ensemble = StrategyEnsemble([s1, s2])
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    intel_mock = MagicMock()
    intel_mock.generate_intelligence.return_value = None
    
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel_mock,
        forecasting_service=MagicMock(),
        weighting_service=svc
    )
    
    bars = [MarketBar(symbol="BTC", timestamp=as_of - timedelta(days=120-i), open=1, high=1, low=1, close=100+i, volume=1) for i in range(120)]
    
    decision = orchestrator.evaluate("BTC", bars, 10000.0, 0, 0.0)
    
    assert decision.strategy_weighting_audit is not None
    assert "DummyBreakout" in decision.strategy_weighting_audit
    assert decision.strategy_weighting_audit["DummyBreakout"]["weight_multiplier"] == 1.25
    assert decision.strategy_weighting_audit["DummyReversion"]["weight_multiplier"] == 0.75
    
    # Ensemble should pick DummyBreakout because its confidence was boosted to min(1.0, 0.8 * 1.25 = 1.0)
    # While DummyReversion was reduced to 0.8 * 0.75 = 0.6
    if decision.decision != "LONG":
        print("REASON:", decision.risk_gate_reason)
        print("DRAWDOWN REASON:", decision.main_risks)
        
    assert decision.decision == "LONG"
    
def test_all_strategies_evaluated(mock_evo_repo):
    svc = StrategyWeightingService(mock_evo_repo)
    s1 = DummyStrategy("S1", "LONG")
    s2 = DummyStrategy("S2", "SHORT")
    ensemble = StrategyEnsemble([s1, s2])
    
    limits = PortfolioRiskLimits(initial_equity=10000.0)
    risk_engine = RiskEngine(limits, risk_per_trade_pct=0.01)
    
    intel_mock = MagicMock()
    intel_mock.generate_intelligence.return_value = None
    
    orchestrator = DecisionOrchestrator(
        ensemble=ensemble,
        risk_engine=risk_engine,
        intelligence_service=intel_mock,
        forecasting_service=MagicMock(),
        weighting_service=svc
    )
    
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=1, low=1, close=100, volume=1)] * 11
    decision = orchestrator.evaluate("BTC", bars, 10000.0, 0, 0.0)
    
    # Ensure both raw signals are preserved in decision.strategy_signals
    strat_names = [s["strategy"] for s in decision.strategy_signals]
    assert "S1" in strat_names
    assert "S2" in strat_names
