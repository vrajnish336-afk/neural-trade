import argparse
import logging
from app.database.schema import init_db
from app.news.repository import NewsRepository
from app.news.models import IngestedNewsRecord
from app.research.ai_provider import get_ai_provider
from app.research.ai_repository import AIResearchRepository

logger = logging.getLogger(__name__)

def setup_research_news_parser(subparsers):
    parser = subparsers.add_parser("research-news", help="Run AI Research Analysis on unprocessed news")
    parser.set_defaults(func=run_research_news)

def run_research_news(args):
    init_db()
    print("Starting AI Research Analysis on News...")
    
    news_repo = NewsRepository()
    ai_repo = AIResearchRepository()
    provider = get_ai_provider()
    
    # Fetch news articles (mocking a get_unprocessed query for now by fetching all and checking)
    try:
        conn = news_repo._get_conn()
        cursor = conn.cursor()
        # Find articles that haven't been analyzed yet
        cursor.execute("""
            SELECT id, title, summary, source, source_url, article_url, published_timestamp, discovered_timestamp, content_hash, validation_status 
            FROM news_articles 
            WHERE id NOT IN (SELECT article_id FROM ai_research_analysis)
            AND validation_status = 'VALID'
        """)
        rows = cursor.fetchall()
        
        from datetime import datetime
        unprocessed_articles = []
        for row in rows:
            unprocessed_articles.append(IngestedNewsRecord(
                id=row[0],
                title=row[1],
                summary=row[2],
                source=row[3],
                source_url=row[4],
                article_url=row[5],
                published_timestamp=datetime.fromisoformat(row[6]) if row[6] else None,
                discovered_timestamp=datetime.fromisoformat(row[7]),
                content_hash=row[8],
                validation_status=row[9]
            ))
            
    except Exception as e:
        logger.error("Failed to fetch unprocessed news: %s", e)
        return 1
    finally:
        conn.close()
        
    print(f"Found {len(unprocessed_articles)} unprocessed articles.")
    
    analyzed_count = 0
    fallback_count = 0
    
    for article in unprocessed_articles:
        print(f"Analyzing: {article.title[:50]}...")
        analysis = provider.analyze_article(article)
        
        if analysis.is_fallback:
            fallback_count += 1
            
        success = ai_repo.save_analysis(analysis)
        if success:
            analyzed_count += 1
            
    print("\nAI Research Analysis Complete")
    print(f"Items processed: {len(unprocessed_articles)}")
    print(f"Analyses saved: {analyzed_count}")
    print(f"Fallbacks/Errors: {fallback_count}")
    
    return 0
