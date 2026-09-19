import pytest
import sqlite3
import uuid
import json
from datetime import datetime
from app.database.schema import init_db
from app.config import config
from app.research.knowledge_models import (
    ResearchKnowledgeSnapshot, ResearchKnowledgeChange, KnowledgeChangeType,
    EvidenceGap, EvidenceGapType, EvidenceGapStatus
)
from app.research.knowledge_service import ResearchKnowledgeService
from app.research.decision_models import (
    ResearchConfidenceState, ResearchDecisionState, NextResearchAction,
    ResearchConclusion
)

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_knowledge.sqlite"
    config.DB_PATH = str(db_file)
    init_db()
    yield

def _inject_memory_record(identity_hash: str):
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("""
        INSERT INTO research_memory (identity_hash, canonical_hypothesis, affected_symbols, mapped_strategy, first_seen_at)
        VALUES (?, ?, ?, ?, ?)
    """, (identity_hash, "test hypothesis", '["BTC"]', "Trend", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def test_knowledge_snapshot_empty():
    service = ResearchKnowledgeService()
    ident = "hash_empty"
    
    # Needs a memory record first
    _inject_memory_record(ident)
    
    snap = service.get_snapshot(ident)
    assert snap is not None
    assert snap.identity_hash == ident
    assert snap.total_experiments == 0
    assert snap.current_decision_state == ResearchDecisionState.INSUFFICIENT_EVIDENCE
    assert snap.current_confidence_state == ResearchConfidenceState.LOW

def test_knowledge_change_detection():
    service = ResearchKnowledgeService()
    ident = "hash_change"
    _inject_memory_record(ident)
    
    # Simulate a new conclusion arriving
    conc = ResearchConclusion(
        conclusion_id="conc1",
        identity_hash=ident,
        decision_state=ResearchDecisionState.RESEARCH_RESULT_SUPPORTED,
        confidence_state=ResearchConfidenceState.MODERATE,
        summary="Test",
        supporting_evidence_count=1,
        conflicting_evidence_count=0,
        limitations=[],
        next_research_action=NextResearchAction.VALIDATE_WALK_FORWARD,
        provenance_experiment_ids=["exp1"]
    )
    
    # First save it to DB so it acts as "current" next time
    with service._get_conn() as conn:
        conn.execute("""
            INSERT INTO research_conclusions
            (conclusion_id, identity_hash, decision_state, confidence_state, summary,
             supporting_evidence_count, conflicting_evidence_count, limitations,
             next_research_action, ai_explanation, provenance_experiment_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            conc.conclusion_id, conc.identity_hash, conc.decision_state.value,
            conc.confidence_state.value, conc.summary, conc.supporting_evidence_count,
            conc.conflicting_evidence_count, json.dumps(conc.limitations),
            conc.next_research_action.value, conc.ai_explanation,
            json.dumps(conc.provenance_experiment_ids), conc.created_at.isoformat()
        ))
    
    # Process it through the hook
    service.on_new_conclusion_generated(conc)
    
    # Verify change was recorded
    with service._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT previous_decision, new_decision FROM research_knowledge_changes WHERE identity_hash=?", (ident,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] is None # Because there was no prior conclusion in DB before we inserted conc1
        assert row[1] == "RESEARCH_RESULT_SUPPORTED"
        
    # Verify Gap was created because action was VALIDATE_WALK_FORWARD
    with service._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT gap_type, status FROM research_evidence_gaps WHERE identity_hash=?", (ident,))
        row = cursor.fetchone()
        assert row is not None
        assert row[0] == EvidenceGapType.MISSING_WALK_FORWARD.value
        assert row[1] == EvidenceGapStatus.OPEN.value

def test_knowledge_change_ignores_duplicate():
    service = ResearchKnowledgeService()
    ident = "hash_dup"
    _inject_memory_record(ident)
    
    conc = ResearchConclusion(
        conclusion_id="conc2",
        identity_hash=ident,
        decision_state=ResearchDecisionState.RESEARCH_RESULT_SUPPORTED,
        confidence_state=ResearchConfidenceState.MODERATE,
        summary="Test",
        supporting_evidence_count=1,
        conflicting_evidence_count=0,
        limitations=[],
        next_research_action=NextResearchAction.VALIDATE_WALK_FORWARD,
        provenance_experiment_ids=["exp2"]
    )
    
    # Inject an existing conclusion with exact same state
    with service._get_conn() as conn:
        conn.execute("""
            INSERT INTO research_conclusions
            (conclusion_id, identity_hash, decision_state, confidence_state, summary,
             supporting_evidence_count, conflicting_evidence_count, limitations,
             next_research_action, ai_explanation, provenance_experiment_ids, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "conc_prev", conc.identity_hash, conc.decision_state.value,
            conc.confidence_state.value, conc.summary, conc.supporting_evidence_count,
            conc.conflicting_evidence_count, json.dumps(conc.limitations),
            conc.next_research_action.value, conc.ai_explanation,
            json.dumps(["exp1"]), datetime.utcnow().isoformat()
        ))
        
    # Run hook
    service.on_new_conclusion_generated(conc)
    
    # Should NOT have recorded a change because decision didn't change
    with service._get_conn() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM research_knowledge_changes WHERE identity_hash=?", (ident,))
        count = cursor.fetchone()[0]
        assert count == 0
