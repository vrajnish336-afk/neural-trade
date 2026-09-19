from datetime import datetime, timezone
from typing import List, Tuple
from app.core.models import SentimentResult, NewsArticle

POSITIVE_WORDS = {"growth", "profit", "surge", "beat", "up", "bullish", "record", "jump", "rally", "dividend"}
NEGATIVE_WORDS = {"loss", "lawsuit", "crash", "missed", "down", "bearish", "decline", "plunge", "bankrupt", "hack"}

def analyze_sentiment(text: str, timestamp: datetime) -> SentimentResult:
    """
    Deterministic rule-based baseline sentiment analyzer.
    DO NOT claim this represents probability of stock movement.
    """
    if not text:
        return SentimentResult(score=0.0, label="NEUTRAL", confidence=0.0, source_count=1, timestamp=timestamp)
        
    words = set(text.lower().replace(".", "").replace(",", "").split())
    
    pos_count = len(words.intersection(POSITIVE_WORDS))
    neg_count = len(words.intersection(NEGATIVE_WORDS))
    
    total_sentiment_words = pos_count + neg_count
    if total_sentiment_words == 0:
        return SentimentResult(score=0.0, label="NEUTRAL", confidence=0.5, source_count=1, timestamp=timestamp)
        
    score = (pos_count - neg_count) / total_sentiment_words
    
    if score > 0.3:
        label = "POSITIVE"
    elif score < -0.3:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"
        
    # Confidence based on number of sentiment words found
    confidence = min(1.0, total_sentiment_words * 0.2)
    
    return SentimentResult(score=score, label=label, confidence=confidence, source_count=1, timestamp=timestamp)

def is_article_relevant(article: NewsArticle, symbol: str, aliases: List[str] = None) -> bool:
    """
    Determines whether an article is relevant to a symbol.
    """
    aliases = aliases or []
    search_terms = {symbol.lower()} | {a.lower() for a in aliases}
    
    title_words = set(article.title.lower().split())
    summary_words = set(article.summary.lower().split())
    
    all_words = title_words | summary_words
    
    for term in search_terms:
        if term in all_words:
            return True
            
    # Check exact substring for multi-word aliases
    full_text = f"{article.title} {article.summary}".lower()
    for term in search_terms:
        if " " in term and term in full_text:
            return True
            
    return False
