from typing import List, Optional
from datetime import datetime
from app.core.models import SentimentResult

def aggregate_sentiment(sentiments: List[SentimentResult], timestamp: datetime) -> Optional[SentimentResult]:
    """
    Aggregates multiple sentiment results into a single composite result.
    Returns None if insufficient news (state: INSUFFICIENT_NEWS).
    """
    if not sentiments:
        return None
        
    total_score = 0.0
    total_confidence = 0.0
    pos_count = 0
    neg_count = 0
    neutral_count = 0
    
    for s in sentiments:
        total_score += s.score * s.confidence
        total_confidence += s.confidence
        if s.label == "POSITIVE":
            pos_count += 1
        elif s.label == "NEGATIVE":
            neg_count += 1
        else:
            neutral_count += 1
            
    if total_confidence == 0:
        agg_score = 0.0
    else:
        agg_score = total_score / total_confidence
        
    # Cap final confidence
    final_confidence = min(1.0, sum(s.confidence for s in sentiments) / max(1, len(sentiments)) + 0.1 * len(sentiments))
    
    if agg_score > 0.2:
        label = "POSITIVE"
    elif agg_score < -0.2:
        label = "NEGATIVE"
    else:
        label = "NEUTRAL"
        
    return SentimentResult(
        score=agg_score,
        label=label,
        confidence=final_confidence,
        source_count=len(sentiments),
        timestamp=timestamp
    )
