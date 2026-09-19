import pytest
import sqlite3
import uuid
import json
from datetime import datetime, timezone
from app.research.memory_models import ResearchIdentity, ResearchMemoryRecord, ResearchOpportunity, OpportunityStatus
from app.research.memory_repository import ResearchMemoryRepository
from app.research.opportunity_intelligence import OpportunityIntelligence
from app.research.ai_models import AIAnalysisResult, EvidenceType
from app.database.schema import init_db
from app.config import config
from app.research.loop_orchestrator import ResearchLoopOrchestrator

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_memory.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    yield

def test_deterministic_identity_hashing():
    id1 = ResearchIdentity.generate("TrendFollowing", ["BTC/USD"], "Prices will go up")
    id2 = ResearchIdentity.generate(" trendfollowing ", ["btc/usd"], " prices  will go up ")
    id3 = ResearchIdentity.generate("TrendFollowing", ["ETH/USD"], "Prices will go up")
    
    assert id1.identity_hash == id2.identity_hash
    assert id1.identity_hash != id3.identity_hash
    # Timestamp is strictly excluded
    
def test_memory_repository_save_and_load():
    repo = ResearchMemoryRepository()
    ident = ResearchIdentity.generate("Trend", ["BTC"], "test")
    
    mem = ResearchMemoryRecord(
        identity_hash=ident.identity_hash,
        canonical_hypothesis="test",
        affected_symbols=["BTC"],
        mapped_strategy="Trend",
        first_seen_at=datetime.utcnow()
    )
    
    assert repo.save_memory(mem) is True
    loaded = repo.get_memory(ident.identity_hash)
    assert loaded is not None
    assert loaded.canonical_hypothesis == "test"
    assert loaded.affected_symbols == ["BTC"]
    
def test_opportunity_intelligence_novel_hypothesis():
    intel = OpportunityIntelligence()
    
    analysis = AIAnalysisResult(
        analysis_id=str(uuid.uuid4()),
        article_id=str(uuid.uuid4()),
        provider="Ollama",
        model="llama3",
        relevance_score=0.9,
        confidence=0.8,
        evidence_type=EvidenceType.RESEARCH_HYPOTHESIS,
        summary="Test",
        market_relevance="High",
        affected_symbols=["BTC/USD"],
        research_hypothesis="Volatility breakout expected due to news."
    )
    
    opp = intel.evaluate_analysis(analysis)
    assert opp is not None
    assert opp.novelty_score == 1.0
    assert opp.status == OpportunityStatus.READY_FOR_RESEARCH
    assert opp.research_priority > 0.6
    
def test_opportunity_intelligence_duplicate_detection():
    intel = OpportunityIntelligence()
    
    analysis = AIAnalysisResult(
        analysis_id=str(uuid.uuid4()),
        article_id=str(uuid.uuid4()),
        provider="Ollama",
        model="llama3",
        relevance_score=0.9,
        confidence=0.8,
        evidence_type=EvidenceType.RESEARCH_HYPOTHESIS,
        summary="Test",
        market_relevance="High",
        affected_symbols=["BTC/USD"],
        research_hypothesis="Volatility breakout expected due to news."
    )
    
    # First time
    opp1 = intel.evaluate_analysis(analysis)
    assert opp1.novelty_score == 1.0
    
    # Simulate that we researched it and found it robust
    repo = ResearchMemoryRepository()
    mem = repo.get_memory(opp1.identity_hash)
    mem.latest_conclusion = "VERIFIED_ROBUST"
    repo.save_memory(mem)
    
    # Second time with identical logical analysis
    opp2 = intel.evaluate_analysis(analysis)
    assert opp2.novelty_score == 0.0
    assert opp2.status == OpportunityStatus.ALREADY_RESEARCHED
    assert opp2.research_priority < 0.6

def test_opportunity_intelligence_needs_validation():
    intel = OpportunityIntelligence()
    
    analysis = AIAnalysisResult(
        analysis_id=str(uuid.uuid4()),
        article_id=str(uuid.uuid4()),
        provider="Ollama",
        model="llama3",
        relevance_score=0.9,
        confidence=0.8,
        evidence_type=EvidenceType.RESEARCH_HYPOTHESIS,
        summary="Test",
        market_relevance="High",
        affected_symbols=["BTC/USD"],
        research_hypothesis="Mean reversion test"
    )
    
    opp1 = intel.evaluate_analysis(analysis)
    
    repo = ResearchMemoryRepository()
    mem = repo.get_memory(opp1.identity_hash)
    mem.latest_conclusion = "INSUFFICIENT_DATA"
    repo.save_memory(mem)
    
    # Second time
    opp2 = intel.evaluate_analysis(analysis)
    assert opp2.novelty_score == 0.0
    assert opp2.status == OpportunityStatus.NEEDS_VALIDATION
    # Priority should be higher than ALREADY_RESEARCHED but maybe not READY immediately without manual push
    assert opp2.evidence_gap_score == 0.8
    assert opp2.duplicate_penalty == 0.2

def test_orchestrator_queue_opportunities(tmp_path):
    orchestrator = ResearchLoopOrchestrator(data_dir=str(tmp_path))
    repo = orchestrator.memory_repo
    
    # Inject a ready opportunity
    opp = ResearchOpportunity(
        opportunity_id=str(uuid.uuid4()),
        source_analysis_id=str(uuid.uuid4()),
        identity_hash="testhash",
        hypothesis_text="test",
        affected_symbols=["BTC/USD"],
        mapped_strategy="TrendFollowing",
        novelty_score=1.0,
        evidence_gap_score=1.0,
        data_availability_score=1.0,
        duplicate_penalty=0.0,
        research_priority=1.0,
        status=OpportunityStatus.READY_FOR_RESEARCH,
        reason="test"
    )
    repo.save_opportunity(opp)
    
    queued = orchestrator.queue_opportunities_for_research()
    assert queued == 1
    
    # Check status changed
    opp_after = repo.get_unresolved_opportunities()
    assert len(opp_after) == 0
