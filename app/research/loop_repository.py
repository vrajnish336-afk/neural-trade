import sqlite3
import logging
import json
from typing import List, Optional
from app.config import config
from app.research.loop_models import AIResearchRequest, ResearchRequestStatus
from app.research.evidence import EvidenceConclusion

logger = logging.getLogger(__name__)

class ResearchLoopRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_request(self, req: AIResearchRequest) -> bool:
        if not config.ENABLE_PERSISTENCE:
            return False
            
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT OR REPLACE INTO ai_research_requests 
                       (request_id, analysis_id, article_id, hypothesis_text, affected_symbols, mapped_strategy,
                        historical_window_days, dataset_identity, random_seed, created_at, status,
                        experiment_id, evidence_conclusion, failure_reason) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        req.request_id,
                        req.analysis_id,
                        req.article_id,
                        req.hypothesis_text,
                        json.dumps(req.affected_symbols),
                        req.mapped_strategy,
                        req.historical_window_days,
                        json.dumps(req.dataset_identity) if req.dataset_identity else None,
                        req.random_seed,
                        req.created_at.isoformat(),
                        req.status.value,
                        req.experiment_id,
                        req.evidence_conclusion.value if req.evidence_conclusion else None,
                        req.failure_reason
                    )
                )
            return True
        except Exception as e:
            logger.error("Failed to save AI research request: %s", e)
            return False

    def get_pending_requests(self, limit: int = 10) -> List[AIResearchRequest]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ai_research_requests WHERE status = 'PENDING' ORDER BY created_at ASC LIMIT ?", (limit,))
                rows = cursor.fetchall()
                results = []
                for row in rows:
                    results.append(self._row_to_request(row))
                return results
        except Exception as e:
            logger.error("Failed to fetch pending requests: %s", e)
            return []
            
    def _row_to_request(self, row) -> AIResearchRequest:
        from datetime import datetime
        return AIResearchRequest(
            request_id=row[0],
            analysis_id=row[1],
            article_id=row[2],
            hypothesis_text=row[3],
            affected_symbols=json.loads(row[4]) if row[4] else [],
            mapped_strategy=row[5],
            historical_window_days=row[6],
            dataset_identity=json.loads(row[7]) if row[7] else None,
            random_seed=row[8],
            created_at=datetime.fromisoformat(row[9]),
            status=ResearchRequestStatus(row[10]),
            experiment_id=row[11],
            evidence_conclusion=EvidenceConclusion(row[12]) if row[12] else None,
            failure_reason=row[13]
        )
