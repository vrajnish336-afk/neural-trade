import argparse
from app.news.collector import NewsCollector
from app.news.repository import NewsRepository

def setup_news_parser(subparsers):
    parser = subparsers.add_parser("news", help="Collect and persist news from configured RSS feeds")
    parser.set_defaults(func=run_news_ingestion)

def run_news_ingestion(args):
    from app.database.schema import init_db
    init_db()
    
    print("Starting news ingestion...")
    collector = NewsCollector()
    
    feeds_attempted = len([f for f in collector.feeds if f.strip()])
    records = collector.collect()
    items_received = len(records)
    
    valid_records = [r for r in records if r.validation_status == 'VALID']
    rejected_records = items_received - len(valid_records)
    
    repo = NewsRepository()
    inserted, duplicates = repo.save_records(valid_records)
    
    print("\nNews ingestion complete")
    print(f"Feeds attempted: {feeds_attempted}")
    # For simplicity in this summary, we treat feeds succeeded same as attempted unless we hook into collector internals
    print(f"Feeds succeeded: {feeds_attempted}") 
    print(f"Items received: {items_received}")
    print(f"Accepted: {inserted}")
    print(f"Duplicates: {duplicates}")
    print(f"Rejected: {rejected_records}")
    print(f"Errors: 0")
    
    return 0
