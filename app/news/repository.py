import sqlite3
import logging
from typing import List, Tuple
from app.config import config
from app.news.models import IngestedNewsRecord

logger = logging.getLogger(__name__)

class NewsRepository:
    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.DB_PATH
        
    def _get_conn(self):
        return sqlite3.connect(self.db_path)
        
    def save_records(self, records: List[IngestedNewsRecord]) -> Tuple[int, int]:
        """
        Saves records. Returns (inserted_count, duplicate_count).
        """
        if not config.ENABLE_PERSISTENCE or not records:
            return 0, 0
            
        inserted = 0
        duplicates = 0
        
        try:
            conn = self._get_conn()
            try:
                with conn:
                    cursor = conn.cursor()
                    for rec in records:
                        try:
                            cursor.execute(
                                '''INSERT INTO news_articles 
                                   (id, title, summary, source, source_url, article_url, published_timestamp, discovered_timestamp, content_hash, validation_status) 
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                                (
                                    rec.id, rec.title, rec.summary, rec.source, rec.source_url, rec.article_url,
                                    rec.published_timestamp.isoformat() if rec.published_timestamp else None,
                                    rec.discovered_timestamp.isoformat(),
                                    rec.content_hash, rec.validation_status
                                )
                            )
                            inserted += 1
                        except sqlite3.IntegrityError:
                            duplicates += 1
                return inserted, duplicates
            finally:
                conn.close()
        except Exception as e:
            logger.error("Failed to save news records: %s", e)
            return inserted, duplicates
