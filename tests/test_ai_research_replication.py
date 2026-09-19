import pytest
from datetime import datetime, timezone, timedelta
from app.research.evidence_graph.models import EvidenceNode, NodeType
from app.research.hypothesis_validation.models import HypothesisValidationResult, ValidationState, FalsificationState, EvidenceClassification
from app.research.replication.service import ReplicationService
from app.research.replication.models import GeneralizationState, EvidenceStrengthLevel, ReplicationCategory

@pytest.fixture
def rep_service():
    s = ReplicationService()
    s.repo._init_db()
    s.graph_repo._init_db()
    with s.repo._get_conn() as conn:
        conn.execute("DELETE FROM research_replication_results")
    with s.graph_repo._get_conn() as conn:
        conn.execute("DELETE FROM research_evidence_nodes")
    return s

def test_identical_dataset_is_not_independent(rep_service):
    t = datetime.now(timezone.utc)
    
    # Save 3 experiments with EXACT same dataset and seed
    nodes = []
    for i in range(3):
        nid = f"exp_{i}"
        node = EvidenceNode(
            node_id=nid, node_type=NodeType.EXPERIMENT, source_id=str(i), source_type="t", created_at=t, as_of=t,
            metadata={"dataset_id": "ds_1", "start_time": "2020-01-01T00:00:00Z", "end_time": "2021-01-01T00:00:00Z", "seed": 42}
        )
        rep_service.graph_repo.save_node(node)
        nodes.append(nid)
        
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        validation_state=ValidationState.SUPPORTED, evidence_state=EvidenceClassification.SUPPORTING,
        supporting_evidence_ids=nodes, evidence_count=3, as_of=t, created_at=t
    )
    
    res = rep_service.evaluate(val, as_of=t)
    # The first is INDEPENDENT, the next two are SAME_DATASET_REPLAY
    assert res.replication.total_independent_units == 1
    assert res.replication.same_dataset_units == 2
    assert res.evidence_strength == EvidenceStrengthLevel.FRAGILE
    assert res.generalization_state == GeneralizationState.LIMITED_SCOPE

def test_different_seed_on_same_dataset(rep_service):
    t = datetime.now(timezone.utc)
    nodes = []
    # Same dataset, but different seeds
    for i in range(2):
        nid = f"exp_{i}"
        node = EvidenceNode(
            node_id=nid, node_type=NodeType.EXPERIMENT, source_id=str(i), source_type="t", created_at=t, as_of=t,
            metadata={"dataset_id": "ds_1", "start_time": "2020-01-01T00:00:00Z", "end_time": "2021-01-01T00:00:00Z", "seed": i}
        )
        rep_service.graph_repo.save_node(node)
        nodes.append(nid)
        
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        validation_state=ValidationState.SUPPORTED, evidence_state=EvidenceClassification.SUPPORTING,
        supporting_evidence_ids=nodes, evidence_count=2, as_of=t, created_at=t
    )
    
    res = rep_service.evaluate(val, as_of=t)
    assert res.replication.total_independent_units == 1
    assert res.replication.same_dataset_units == 1 # 1 different seed only
    assert res.replication.category_counts[ReplicationCategory.DIFFERENT_SEED_ONLY.value] == 1

def test_overlapping_periods_detected(rep_service):
    t = datetime.now(timezone.utc)
    n1 = EvidenceNode(
        node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t,
        metadata={"dataset_id": "ds_1", "start_time": "2020-01-01T00:00:00Z", "end_time": "2021-01-01T00:00:00Z", "seed": 1}
    )
    n2 = EvidenceNode(
        node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t,
        metadata={"dataset_id": "ds_1", "start_time": "2020-06-01T00:00:00Z", "end_time": "2022-01-01T00:00:00Z", "seed": 1}
    )
    rep_service.graph_repo.save_node(n1)
    rep_service.graph_repo.save_node(n2)
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        validation_state=ValidationState.SUPPORTED, evidence_state=EvidenceClassification.SUPPORTING,
        supporting_evidence_ids=["exp_1", "exp_2"], evidence_count=2, as_of=t, created_at=t
    )
    
    res = rep_service.evaluate(val, as_of=t)
    assert res.replication.overlapping_units == 1
    assert res.replication.category_counts[ReplicationCategory.OVERLAPPING_DATA.value] == 1

def test_unseen_period_recognized_generalization(rep_service):
    t = datetime.now(timezone.utc)
    n1 = EvidenceNode(
        node_id="exp_1", node_type=NodeType.EXPERIMENT, source_id="1", source_type="t", created_at=t, as_of=t,
        metadata={"dataset_id": "ds_1", "start_time": "2020-01-01T00:00:00Z", "end_time": "2021-01-01T00:00:00Z", "seed": 1, "regime": "A"}
    )
    n2 = EvidenceNode(
        node_id="exp_2", node_type=NodeType.EXPERIMENT, source_id="2", source_type="t", created_at=t, as_of=t,
        metadata={"dataset_id": "ds_2", "start_time": "2022-01-01T00:00:00Z", "end_time": "2023-01-01T00:00:00Z", "seed": 1, "regime": "B"}
    )
    rep_service.graph_repo.save_node(n1)
    rep_service.graph_repo.save_node(n2)
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        validation_state=ValidationState.SUPPORTED, evidence_state=EvidenceClassification.SUPPORTING,
        supporting_evidence_ids=["exp_1", "exp_2"], evidence_count=2, as_of=t, created_at=t
    )
    
    res = rep_service.evaluate(val, as_of=t)
    assert res.replication.total_independent_units == 2
    assert res.generalization_state == GeneralizationState.GENERALIZES
    assert res.evidence_strength == EvidenceStrengthLevel.STRONG

def test_falsification_overrides_strength(rep_service):
    t = datetime.now(timezone.utc)
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.REJECTED,
        validation_state=ValidationState.REJECTED, evidence_state=EvidenceClassification.CONTRADICTING,
        supporting_evidence_ids=[], evidence_count=5, falsification_triggered=FalsificationState.TRIGGERED,
        as_of=t, created_at=t
    )
    res = rep_service.evaluate(val, as_of=t)
    assert res.evidence_strength == EvidenceStrengthLevel.CONFLICTED

def test_as_of_excludes_future_evidence(rep_service):
    t_past = datetime.now(timezone.utc) - timedelta(days=10)
    t_future = datetime.now(timezone.utc)
    
    n_future = EvidenceNode(
        node_id="exp_future", node_type=NodeType.EXPERIMENT, source_id="f1", source_type="t", created_at=t_future, as_of=t_future,
        metadata={"dataset_id": "ds_1"}
    )
    rep_service.graph_repo.save_node(n_future)
    
    val = HypothesisValidationResult(
        validation_id="val_1", hypothesis_id="hyp_1", research_identity="id1", status=ValidationState.SUPPORTED,
        validation_state=ValidationState.SUPPORTED, evidence_state=EvidenceClassification.SUPPORTING,
        supporting_evidence_ids=["exp_future"], evidence_count=1, as_of=t_past, created_at=t_past
    )
    
    res = rep_service.evaluate(val, as_of=t_past)
    assert res.replication.evidence_nodes_assessed == 0 # Excluded cleanly
    assert res.evidence_strength == EvidenceStrengthLevel.INSUFFICIENT
