import sqlite3
import json
import logging
from typing import List, Optional
from datetime import datetime
from app.config import config
from app.research.evidence_graph.models import EvidenceNode, EvidenceEdge, NodeType, EdgeRelationship

logger = logging.getLogger(__name__)

GRAPH_SCHEMA = """
CREATE TABLE IF NOT EXISTS research_evidence_nodes (
    node_id TEXT PRIMARY KEY,
    node_type TEXT,
    source_id TEXT,
    source_type TEXT,
    identity_hash TEXT,
    created_at TEXT,
    observed_at TEXT,
    as_of TEXT,
    methodology_version TEXT,
    metadata TEXT
);
CREATE INDEX IF NOT EXISTS idx_node_source ON research_evidence_nodes(source_id, source_type);
CREATE INDEX IF NOT EXISTS idx_node_as_of ON research_evidence_nodes(as_of);

CREATE TABLE IF NOT EXISTS research_evidence_edges (
    edge_id TEXT PRIMARY KEY,
    source_node_id TEXT,
    target_node_id TEXT,
    relationship_type TEXT,
    evidence_basis TEXT,
    confidence REAL,
    methodology_version TEXT,
    created_at TEXT,
    as_of TEXT,
    deterministic_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS idx_edge_source ON research_evidence_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_edge_target ON research_evidence_edges(target_node_id);
CREATE INDEX IF NOT EXISTS idx_edge_as_of ON research_evidence_edges(as_of);
"""

class EvidenceGraphRepository:
    def __init__(self):
        if config.ENABLE_PERSISTENCE:
            self._init_db()

    def _get_conn(self):
        if not config.ENABLE_PERSISTENCE:
            raise RuntimeError("Persistence disabled")
        return sqlite3.connect(config.DB_PATH)

    def _init_db(self):
        try:
            with self._get_conn() as conn:
                conn.executescript(GRAPH_SCHEMA)
                conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Failed to init graph schema: {e}")

    def save_node(self, n: EvidenceNode):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_evidence_nodes
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    n.node_id, n.node_type.value, n.source_id, n.source_type,
                    n.identity_hash, n.created_at.isoformat(),
                    n.observed_at.isoformat() if n.observed_at else None,
                    n.as_of.isoformat(), n.methodology_version,
                    json.dumps(n.metadata)
                ))
        except Exception as e:
            logger.error(f"Failed to save node {n.node_id}: {e}")

    def save_edge(self, e: EvidenceEdge):
        if not config.ENABLE_PERSISTENCE: return
        try:
            with self._get_conn() as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO research_evidence_edges
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    e.edge_id, e.source_node_id, e.target_node_id,
                    e.relationship_type.value, e.evidence_basis,
                    e.confidence, e.methodology_version,
                    e.created_at.isoformat(), e.as_of.isoformat(),
                    e.deterministic_key
                ))
        except sqlite3.IntegrityError:
            pass # Deterministic key prevents duplicates
        except Exception as err:
            logger.error(f"Failed to save edge {e.edge_id}: {err}")

    def get_node(self, node_id: str) -> Optional[EvidenceNode]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_evidence_nodes WHERE node_id = ?", (node_id,))
                row = cursor.fetchone()
                if row:
                    return EvidenceNode(
                        node_id=row[0], node_type=NodeType(row[1]),
                        source_id=row[2], source_type=row[3], identity_hash=row[4],
                        created_at=datetime.fromisoformat(row[5]),
                        observed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        as_of=datetime.fromisoformat(row[7]),
                        methodology_version=row[8],
                        metadata=json.loads(row[9])
                    )
        except Exception as e:
            logger.error(f"Failed to get node: {e}")
        return None

    def get_node_by_source(self, source_id: str, source_type: str) -> Optional[EvidenceNode]:
        if not config.ENABLE_PERSISTENCE: return None
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM research_evidence_nodes WHERE source_id = ? AND source_type = ?", (source_id, source_type))
                row = cursor.fetchone()
                if row:
                    return EvidenceNode(
                        node_id=row[0], node_type=NodeType(row[1]),
                        source_id=row[2], source_type=row[3], identity_hash=row[4],
                        created_at=datetime.fromisoformat(row[5]),
                        observed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        as_of=datetime.fromisoformat(row[7]),
                        methodology_version=row[8],
                        metadata=json.loads(row[9])
                    )
        except Exception as e:
            logger.error(f"Failed to get node by source: {e}")
        return None
        
    def get_nodes(self, as_of: Optional[datetime] = None) -> List[EvidenceNode]:
        if not config.ENABLE_PERSISTENCE: return []
        nodes = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_evidence_nodes WHERE as_of <= ?", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_evidence_nodes")
                for row in cursor.fetchall():
                    nodes.append(EvidenceNode(
                        node_id=row[0], node_type=NodeType(row[1]),
                        source_id=row[2], source_type=row[3], identity_hash=row[4],
                        created_at=datetime.fromisoformat(row[5]),
                        observed_at=datetime.fromisoformat(row[6]) if row[6] else None,
                        as_of=datetime.fromisoformat(row[7]),
                        methodology_version=row[8],
                        metadata=json.loads(row[9])
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch nodes: {e}")
        return nodes

    def get_edges(self, as_of: Optional[datetime] = None) -> List[EvidenceEdge]:
        if not config.ENABLE_PERSISTENCE: return []
        edges = []
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if as_of:
                    cursor.execute("SELECT * FROM research_evidence_edges WHERE as_of <= ?", (as_of.isoformat(),))
                else:
                    cursor.execute("SELECT * FROM research_evidence_edges")
                for row in cursor.fetchall():
                    edges.append(EvidenceEdge(
                        edge_id=row[0], source_node_id=row[1], target_node_id=row[2],
                        relationship_type=EdgeRelationship(row[3]), evidence_basis=row[4],
                        confidence=row[5], methodology_version=row[6],
                        created_at=datetime.fromisoformat(row[7]),
                        as_of=datetime.fromisoformat(row[8]),
                        deterministic_key=row[9]
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch edges: {e}")
        return edges

    def get_edges_for_node(self, node_id: str, as_of: Optional[datetime] = None, direction: str = 'both') -> List[EvidenceEdge]:
        edges = []
        if not config.ENABLE_PERSISTENCE: return edges
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                if direction == 'both':
                    query = "SELECT * FROM research_evidence_edges WHERE (source_node_id = ? OR target_node_id = ?)"
                    params = [node_id, node_id]
                elif direction == 'out':
                    query = "SELECT * FROM research_evidence_edges WHERE source_node_id = ?"
                    params = [node_id]
                else:
                    query = "SELECT * FROM research_evidence_edges WHERE target_node_id = ?"
                    params = [node_id]
                    
                if as_of:
                    query += " AND as_of <= ?"
                    params.append(as_of.isoformat())
                    
                cursor.execute(query, tuple(params))
                for row in cursor.fetchall():
                    edges.append(EvidenceEdge(
                        edge_id=row[0], source_node_id=row[1], target_node_id=row[2],
                        relationship_type=EdgeRelationship(row[3]), evidence_basis=row[4],
                        confidence=row[5], methodology_version=row[6],
                        created_at=datetime.fromisoformat(row[7]),
                        as_of=datetime.fromisoformat(row[8]),
                        deterministic_key=row[9]
                    ))
        except Exception as e:
            logger.error(f"Failed to fetch edges for node {node_id}: {e}")
        return edges
