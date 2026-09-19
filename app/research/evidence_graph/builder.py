import uuid
import json
from datetime import datetime
from app.config import config
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship
from app.research.evidence_graph.repository import EvidenceGraphRepository
import sqlite3

class GraphBuilder:
    def __init__(self):
        self.repo = EvidenceGraphRepository()

    def _get_conn(self):
        if not config.ENABLE_PERSISTENCE:
            raise RuntimeError("Persistence disabled")
        return sqlite3.connect(config.DB_PATH)

    def _deterministic_uuid(self, source: str) -> str:
        import hashlib
        h = hashlib.sha256(source.encode('utf-8')).hexdigest()
        return str(uuid.UUID(h[:32]))

    def build_graph(self):
        """Idempotent build of the evidence graph from known tables."""
        if not config.ENABLE_PERSISTENCE: return
        self._build_sandbox_experiments()
        self._build_evolution_proposals()
        self._build_lessons()
        self._build_experiment_comparisons()
        self._build_evidence_gaps()

    def _build_evidence_gaps(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT gap_id, identity_hash, gap_type, severity, status, created_at FROM research_evidence_gaps")
                for row in cursor.fetchall():
                    gap_id = row[0]
                    identity = row[1]
                    gap_type = row[2]
                    severity = row[3]
                    status = row[4]
                    created_dt = datetime.fromisoformat(row[5])
                    
                    node = EvidenceNode(
                        node_id=self._deterministic_uuid(f"gap_{gap_id}"),
                        node_type=NodeType.EVIDENCE_GAP,
                        source_id=gap_id,
                        source_type="research_evidence_gaps",
                        identity_hash=identity,
                        created_at=created_dt,
                        as_of=created_dt,
                        metadata={"gap_type": gap_type, "severity": severity, "status": status}
                    )
                    self.repo.save_node(node)
            except sqlite3.OperationalError:
                pass

    def _build_sandbox_experiments(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT experiment_id, proposal_id, dataset_identity, created_at, completed_at, status FROM research_sandbox_experiments")
                for row in cursor.fetchall():
                    exp_id = row[0]
                    prop_id = row[1]
                    ds_identity = row[2]
                    created_at_str = row[3]
                    completed_at_str = row[4]
                    created_dt = datetime.fromisoformat(created_at_str)
                    
                    # Node
                    node = EvidenceNode(
                        node_id=self._deterministic_uuid(f"exp_{exp_id}"),
                        node_type=NodeType.EXPERIMENT,
                        source_id=exp_id,
                        source_type="research_sandbox_experiments",
                        created_at=created_dt,
                        observed_at=datetime.fromisoformat(completed_at_str) if completed_at_str else None,
                        as_of=created_dt,
                        metadata={"dataset_identity": ds_identity, "status": row[5]}
                    )
                    self.repo.save_node(node)
                    
                    # Edge to proposal if exists
                    if prop_id:
                        prop_node_id = self._deterministic_uuid(f"prop_{prop_id}")
                        edge = EvidenceEdge(
                            edge_id=self._deterministic_uuid(f"edge_exp_prop_{exp_id}"),
                            source_node_id=node.node_id,
                            target_node_id=prop_node_id,
                            relationship_type=EdgeRelationship.DERIVED_FROM,
                            evidence_basis="Sandbox experiment execution links to proposal",
                            created_at=created_dt,
                            as_of=created_dt,
                            deterministic_key=f"exp_{exp_id}_prop_{prop_id}"
                        )
                        self.repo.save_edge(edge)
            except sqlite3.OperationalError:
                pass

    def _build_evolution_proposals(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT proposal_id, baseline_experiment_id, proposed_parameters, created_at FROM research_evolution_proposals")
                for row in cursor.fetchall():
                    prop_id = row[0]
                    baseline_id = row[1]
                    params = row[2]
                    created_dt = datetime.fromisoformat(row[3])
                    
                    node = EvidenceNode(
                        node_id=self._deterministic_uuid(f"prop_{prop_id}"),
                        node_type=NodeType.EVOLUTION_PROPOSAL,
                        source_id=prop_id,
                        source_type="research_evolution_proposals",
                        created_at=created_dt,
                        as_of=created_dt,
                        metadata={"proposed_parameters": params}
                    )
                    self.repo.save_node(node)
                    
                    if baseline_id:
                        base_node_id = self._deterministic_uuid(f"exp_{baseline_id}")
                        edge = EvidenceEdge(
                            edge_id=self._deterministic_uuid(f"edge_prop_base_{prop_id}"),
                            source_node_id=node.node_id,
                            target_node_id=base_node_id,
                            relationship_type=EdgeRelationship.DERIVED_FROM,
                            evidence_basis="Evolution proposal builds on baseline experiment",
                            created_at=created_dt,
                            as_of=created_dt,
                            deterministic_key=f"prop_{prop_id}_base_{baseline_id}"
                        )
                        self.repo.save_edge(edge)
            except sqlite3.OperationalError:
                pass

    def _build_lessons(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT lesson_id, category, description, created_at FROM research_lessons")
                for row in cursor.fetchall():
                    lesson_id = row[0]
                    created_dt = datetime.fromisoformat(row[3])
                    
                    node = EvidenceNode(
                        node_id=self._deterministic_uuid(f"lesson_{lesson_id}"),
                        node_type=NodeType.LESSON,
                        source_id=lesson_id,
                        source_type="research_lessons",
                        created_at=created_dt,
                        as_of=created_dt,
                        metadata={"category": row[1], "description": row[2]}
                    )
                    self.repo.save_node(node)
            except sqlite3.OperationalError:
                pass

    def _build_experiment_comparisons(self):
        with self._get_conn() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("SELECT comparison_id, baseline_experiment_id, target_experiment_id, generated_at, status FROM experiment_comparisons")
                for row in cursor.fetchall():
                    comp_id = row[0]
                    base_id = row[1]
                    target_id = row[2]
                    generated_dt = datetime.fromisoformat(row[3])
                    status = row[4]
                    
                    node = EvidenceNode(
                        node_id=self._deterministic_uuid(f"comp_{comp_id}"),
                        node_type=NodeType.EXPERIMENT_COMPARISON,
                        source_id=comp_id,
                        source_type="experiment_comparisons",
                        created_at=generated_dt,
                        as_of=generated_dt,
                        metadata={"status": status}
                    )
                    self.repo.save_node(node)
                    
                    target_node_id = self._deterministic_uuid(f"exp_{target_id}")
                    rel = EdgeRelationship.SUPPORTS if status == "SUPPORTED" else (EdgeRelationship.CONTRADICTS if status == "NOT_SUPPORTED" else EdgeRelationship.RELATED_TO)
                    
                    edge = EvidenceEdge(
                        edge_id=self._deterministic_uuid(f"edge_comp_{comp_id}_{target_id}"),
                        source_node_id=target_node_id,
                        target_node_id=self._deterministic_uuid(f"exp_{base_id}"),
                        relationship_type=rel,
                        evidence_basis=f"Experiment Comparison resulting in {status}",
                        created_at=generated_dt,
                        as_of=generated_dt,
                        deterministic_key=f"comp_{comp_id}_rel"
                    )
                    self.repo.save_edge(edge)
            except sqlite3.OperationalError:
                pass
