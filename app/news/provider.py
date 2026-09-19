import uuid
from typing import Protocol, List
from datetime import datetime, timezone
from app.core.models import NewsArticle

class NewsProvider(Protocol):
    def get_articles(self, symbol: str, start_time: datetime, end_time: datetime) -> List[NewsArticle]:
        ...

class FixtureNewsProvider(NewsProvider):
    """
    Deterministic local fixture provider for testing and backtesting without external APIs.
    """
    def __init__(self, fixtures: List[NewsArticle] = None):
        self.fixtures = fixtures or []
        
    def get_articles(self, symbol: str, start_time: datetime, end_time: datetime) -> List[NewsArticle]:
        results = []
        for article in self.fixtures:
            if start_time <= article.timestamp <= end_time:
                # Basic exact match for testing (relevance engine does deeper checks)
                if symbol in article.symbols:
                    results.append(article)
                    
        # Remove exact duplicates (same ID)
        unique_results = {}
        for r in results:
            if r.id not in unique_results:
                unique_results[r.id] = r
                
        return list(unique_results.values())
