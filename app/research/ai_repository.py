import sqlite3
import logging
import json
from typing import List, Optional
from app.config import config
from app.research.ai_models import AIAnalysisResult, EvidenceType

logger = logging.getLogger(__name__)

class AIResearchRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_analysis(self, analysis: AIAnalysisResult) -> bool:
        if not config.ENABLE_PERSISTENCE:
            return False
            
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    '''INSERT INTO ai_research_analysis 
                       (analysis_id, article_id, analysis_timestamp, provider, model, schema_version,
                        relevance_score, confidence, evidence_type, summary, market_relevance,
                        affected_symbols, research_hypothesis, limitations, is_fallback, error_message) 
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                    (
                        analysis.analysis_id,
                        analysis.article_id,
                        analysis.analysis_timestamp.isoformat(),
                        analysis.provider,
                        analysis.model,
                        analysis.schema_version,
                        analysis.relevance_score,
                        analysis.confidence,
                        analysis.evidence_type.value,
                        analysis.summary,
                        analysis.market_relevance,
                        json.dumps(analysis.affected_symbols),
                        analysis.research_hypothesis,
                        json.dumps(analysis.limitations),
                        analysis.is_fallback,
                        analysis.error_message
                    )
                )
            return True
        except sqlite3.IntegrityError:
            # Idempotent: Ignore if duplicate analysis_id
            return False
        except Exception as e:
            logger.error("Failed to save AI analysis: %s", e)
            return False

    def get_analysis_by_article(self, article_id: str) -> Optional[AIAnalysisResult]:
        try:
            with self._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM ai_research_analysis WHERE article_id = ?", (article_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                    
                return AIAnalysisResult(
                    analysis_id=row[0],
                    article_id=row[1],
                    analysis_timestamp=row[2], # pydantic parses ISO strings
                    provider=row[3],
                    model=row[4],
                    schema_version=row[5],
                    relevance_score=row[6],
                    confidence=row[7],
                    evidence_type=EvidenceType(row[8]),
                    summary=row[9],
                    market_relevance=row[10],
                    affected_symbols=json.loads(row[11]),
                    research_hypothesis=row[12],
                    limitations=json.loads(row[13]),
                    is_fallback=bool(row[14]),
                    error_message=row[15]
                )
        except Exception as e:
            logger.error("Failed to fetch AI analysis: %s", e)
            return None
