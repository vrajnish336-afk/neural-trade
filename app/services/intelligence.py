from typing import List, Optional
from datetime import datetime, timedelta
from app.core.models import MarketBar, MarketRegimeResult, TradingSignal, MarketIntelligence, SentimentResult
from app.news.provider import NewsProvider
from app.news.sentiment import analyze_sentiment, is_article_relevant
from app.news.aggregator import aggregate_sentiment
from app.analysis.anomaly import detect_anomalies
from app.analysis.fakeout import assess_breakout_quality

class IntelligenceService:
    def __init__(self, news_provider: NewsProvider, config):
        self.news_provider = news_provider
        self.config = config
        
    def generate_intelligence(
        self, 
        symbol: str, 
        timestamp: datetime, 
        bars: List[MarketBar], 
        signal: Optional[TradingSignal] = None
    ) -> MarketIntelligence:
        
        # 1. Fetch News & Aggregate Sentiment
        start_time = timestamp - timedelta(hours=self.config.NEWS_LOOKBACK_HOURS)
        articles = self.news_provider.get_articles(symbol, start_time, timestamp)
        
        relevant_sentiments = []
        for article in articles:
            if is_article_relevant(article, symbol):
                # Only analyze if it hasn't been pre-analyzed
                if not article.sentiment:
                    article.sentiment = analyze_sentiment(article.title + " " + article.summary, article.timestamp)
                relevant_sentiments.append(article.sentiment)
                
        sentiment_result = aggregate_sentiment(relevant_sentiments, timestamp)
        if not sentiment_result:
            sentiment_result = SentimentResult(
                score=0.0, label="INSUFFICIENT_NEWS", confidence=0.0, source_count=0, timestamp=timestamp
            )
            
        # 2. Detect Anomalies
        anomaly_flags = detect_anomalies(bars, zscore_threshold=self.config.ANOMALY_ZSCORE_THRESHOLD)
        
        # 3. Assess Fakeout Risk (Only if there is a signal)
        fakeout_risk = "UNKNOWN"
        if signal and signal.entry_price:
            fakeout_risk = assess_breakout_quality(bars, signal.direction, signal.entry_price)
            
        # 4. Construct Result
        return MarketIntelligence(
            symbol=symbol,
            timestamp=timestamp,
            sentiment=sentiment_result,
            relevant_articles=len(relevant_sentiments),
            anomaly_status=anomaly_flags,
            risk_flags=anomaly_flags.copy(),
            fakeout_risk=fakeout_risk
        )
