import pytest
import os
import sqlite3
from datetime import datetime, timezone

from app.config import config
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.learning.paper_evolution_models import LessonState, ProposalStatus, PaperResearchLesson
from app.learning.paper_evolution_engine import EvolutionProposalEngine
from app.strategies.ensemble import StrategyEnsemble
from app.core.models import TradingSignal, MarketRegimeResult, MarketBar
from app.strategies.base import Strategy

class Phase62MockStrategy(Strategy):
    def __init__(self, name, direction, confidence):
        self._name = name
        self.direction = direction
        self._confidence = confidence
        
    @property
    def name(self): return self._name
    
    def generate_signal(self, bars):
        if self.direction is None:
            return None
        return TradingSignal(
            symbol="BTC", timestamp=datetime.now(timezone.utc), direction=self.direction, strategy=self.name,
            confidence=self._confidence, entry_price=100, reason="test", stop_loss=90, take_profit=110
        )

@pytest.fixture
def evo_db():
    db_path = "test_phase62_evo.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    old_persist = config.ENABLE_PERSISTENCE
    config.ENABLE_PERSISTENCE = True
    
    repo = PaperEvolutionRepository(db_path)
    yield repo
    
    config.ENABLE_PERSISTENCE = old_persist
    if os.path.exists(db_path):
        os.remove(db_path)

def test_config_strategy_fallback():
    # Base is 50.0
    assert config.get_strategy_min_score("UnknownStrat") == config.MIN_SIGNAL_SCORE
    
    # Override
    config.Phase62MockStrategy_MIN_SCORE = 85.0
    assert config.get_strategy_min_score("Phase62MockStrategy") == 85.0
    
    # Cleanup
    del config.Phase62MockStrategy_MIN_SCORE

def test_evolution_engine_strategy_proposal(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    
    # A lesson with negative PnL and a known strategy
    lesson = PaperResearchLesson(
        lesson_id="lesson_strat_1",
        source_trade_ids=[],
        strategy="BreakoutStrategy",
        regime="RANGE_BOUND",
        observation="Test",
        sample_count=10,
        wins=2,
        losses=8,
        observed_pnl=-150,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime.now(timezone.utc),
        data_window_start=datetime.now(timezone.utc),
        data_window_end=datetime.now(timezone.utc)
    )
    
    proposals = engine.generate_proposals([lesson])
    assert len(proposals) == 1
    p = proposals[0]
    
    assert p.affected_parameter == "BreakoutStrategy_MIN_SCORE"
    assert p.current_value == config.MIN_SIGNAL_SCORE
    assert p.proposed_value == config.MIN_SIGNAL_SCORE + 10.0
    assert "Observed negative PnL for BreakoutStrategy" in p.reason

def test_evolution_engine_apply_rollback_strategy(evo_db):
    engine = EvolutionProposalEngine(evo_db)
    
    lesson = PaperResearchLesson(
        lesson_id="lesson_strat_2",
        source_trade_ids=[],
        strategy="TestStrat",
        regime="UNKNOWN",
        observation="Test",
        sample_count=5,
        wins=0,
        losses=5,
        observed_pnl=-50,
        confidence_status=LessonState.VALIDATED,
        created_at=datetime.now(timezone.utc),
        data_window_start=datetime.now(timezone.utc),
        data_window_end=datetime.now(timezone.utc)
    )
    
    proposals = engine.generate_proposals([lesson])
    p = proposals[0]
    p.status = ProposalStatus.APPROVED
    evo_db.save_proposal(p)
    
    # Apply
    res = engine.apply_proposal(p.proposal_id)
    assert res is True
    assert getattr(config, "TestStrat_MIN_SCORE") == 60.0
    
    # Rollback
    res = engine.rollback_proposal(p.proposal_id)
    assert res is True
    assert getattr(config, "TestStrat_MIN_SCORE") == 50.0
    
    # Cleanup
    if hasattr(config, "TestStrat_MIN_SCORE"):
        delattr(config, "TestStrat_MIN_SCORE")

def test_ensemble_enforces_strategy_specific_threshold():
    s1 = Phase62MockStrategy("TestStratX", "LONG", 0.9)
    ensemble = StrategyEnsemble([s1])
    
    regime = MarketRegimeResult(regime="TRENDING_UP", confidence=1.0)
    bars = [MarketBar(symbol="BTC", timestamp=datetime.now(timezone.utc), open=1, high=2, low=1, close=1, volume=1)]
    
    # Base score = 50 + 40 (regime alignment) = 90
    
    # 1. No override, threshold is 50. Score 90 > 50 -> PASS
    signal = ensemble.evaluate(bars, regime)
    assert signal is not None
    assert signal.direction == "LONG"
    
    # 2. Add override threshold > 90
    config.TestStratX_MIN_SCORE = 95.0
    
    signal = ensemble.evaluate(bars, regime)
    # Score 90 < 95 -> FAIL (Returns None)
    assert signal is None
    
    # Cleanup
    del config.TestStratX_MIN_SCORE
