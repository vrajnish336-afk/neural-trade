import pytest
import sqlite3
import uuid
import json
from datetime import datetime
from app.database.schema import init_db
from app.config import config
from app.research.decision_models import (
    ResearchConfidenceState, ResearchDecisionState, NextResearchAction,
    ResearchConflict, ResearchRelationship, RelationshipType
)
from app.research.decision_engine import ResearchDecisionEngine
from app.research.models import ResearchExperiment
from app.analytics.models import FullAnalyticsReport, TradeMetrics
from app.research.orchestrator_models import ResearchJob, JobState

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_decisions.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    yield

def _mock_experiment(pnl: float, pf: float, trades: int, strategy: str = "Trend", symbols=["BTC"]) -> ResearchExperiment:
    return ResearchExperiment(
        experiment_id=str(uuid.uuid4()),
        experiment_name="test",
        dataset_id="local",
        dataset_identity={"hash": "local"},
        symbols=symbols,
        timeframe="1d",
        strategy=strategy,
        configuration="default",
        starting_capital=10000,
        random_seed=42,
        created_at=datetime.utcnow(),
        status="COMPLETED",
        validation_results=[],
        out_of_sample_report=FullAnalyticsReport(
            backtest_id="fake",
            trade_metrics=TradeMetrics(
                total_trades=trades,
                winning_trades=trades//2,
                losing_trades=trades//2,
                gross_pnl=pnl,
                gross_loss=0,
                net_pnl=pnl,
                profit_factor=pf,
                win_rate=0.5,
                total_commission=0,
                average_trade_net=0,
                max_drawdown=0,
                average_pnl=0,
                average_win=0,
                average_loss=0,
                largest_win=0,
                largest_loss=0,
                max_consecutive_wins=0,
                max_consecutive_losses=0,
                average_holding_hours=0
            ),
            equity_metrics={
                "initial_capital": 10000,
                "final_equity": 10000 + pnl,
                "absolute_pnl": pnl,
                "total_return_pct": 0,
                "max_drawdown_pct": 0,
                "max_drawdown_amount": 0,
                "average_drawdown_pct": 0,
                "time_in_drawdown_pct": 0,
                "recovery_periods": 0
            },
            strategy_attribution=[],
            regime_attribution=[],
            signal_bucket_attribution=[],
            intelligence_attribution=[],
            failure_findings=[],
            strategy_comparisons=[]
        )
    )

def _inject_job_and_experiment(engine: ResearchDecisionEngine, exp: ResearchExperiment, identity_hash: str):
    with engine._get_conn() as conn:
        conn.execute("INSERT INTO research_experiments (id, timestamp, experiment_json) VALUES (?, ?, ?)",
                     (exp.experiment_id, datetime.utcnow().isoformat(), exp.json()))
        
        job_id = str(uuid.uuid4())
        conn.execute("""
            INSERT INTO research_jobs (job_id, opportunity_id, identity_hash, priority, state, result_experiment_id)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (job_id, "opp1", identity_hash, 1.0, "SUCCEEDED", exp.experiment_id))

def test_decision_engine_single_strong():
    engine = ResearchDecisionEngine()
    ident = "hash1"
    
    # Strong experiment: PnL > 0, PF > 1, Trades >= 30
    exp = _mock_experiment(pnl=100.0, pf=1.5, trades=50)
    _inject_job_and_experiment(engine, exp, ident)
    
    conc = engine.evaluate_identity(ident)
    assert conc is not None
    assert conc.decision_state == ResearchDecisionState.SUPPORTED_FOR_FURTHER_RESEARCH
    assert conc.confidence_state == ResearchConfidenceState.MODERATE # Not High yet because only 1 exp
    assert conc.next_research_action == NextResearchAction.VALIDATE_WALK_FORWARD

def test_decision_engine_insufficient():
    engine = ResearchDecisionEngine()
    ident = "hash2"
    
    # Insufficient: Trades < 30
    exp = _mock_experiment(pnl=100.0, pf=1.5, trades=10)
    _inject_job_and_experiment(engine, exp, ident)
    
    conc = engine.evaluate_identity(ident)
    assert conc.decision_state == ResearchDecisionState.INSUFFICIENT_EVIDENCE
    assert conc.confidence_state == ResearchConfidenceState.LOW
    assert conc.next_research_action == NextResearchAction.COLLECT_MORE_DATA

def test_decision_engine_contradiction():
    engine = ResearchDecisionEngine()
    ident = "hash3"
    
    # Exp 1: Strong
    exp1 = _mock_experiment(pnl=100.0, pf=1.5, trades=50)
    _inject_job_and_experiment(engine, exp1, ident)
    
    # Exp 2: Weak (Comparable setup, different seed/config causing negative PnL)
    exp2 = _mock_experiment(pnl=-50.0, pf=0.8, trades=50)
    # Ensure they are perfectly comparable by hacking seed
    exp2.random_seed = 99 
    _inject_job_and_experiment(engine, exp2, ident)
    
    conc = engine.evaluate_identity(ident)
    
    assert conc.decision_state == ResearchDecisionState.CONTRADICTORY_EVIDENCE
    assert conc.confidence_state == ResearchConfidenceState.UNRESOLVED
    assert conc.next_research_action == NextResearchAction.INSPECT_CONFLICTING_EXPERIMENTS
    assert conc.conflicting_evidence_count == 1

def test_relationships():
    engine = ResearchDecisionEngine()
    rel = ResearchRelationship(
        source_id="A",
        target_id="B",
        relationship_type=RelationshipType.SUPPORTS,
        description="test"
    )
    engine.add_relationship(rel)
    
    with engine._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT relationship_type FROM research_relationships")
        assert cursor.fetchone()[0] == "SUPPORTS"
