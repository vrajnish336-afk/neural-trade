from datetime import datetime, timezone
import email.utils
from typing import Optional
from app.news.models import IngestedNewsRecord
from app.news.deduplicator import compute_content_hash
from app.news.validator import validate_record_dict

def parse_rss_date(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    try:
        parsed_tuple = email.utils.parsedate_tz(date_str)
        if parsed_tuple:
            timestamp = email.utils.mktime_tz(parsed_tuple)
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except Exception:
        pass
    return None

def normalize_rss_item(item: dict, feed_url: str, source_title: str) -> IngestedNewsRecord:
    """
    Takes a raw dictionary of RSS fields and produces an IngestedNewsRecord.
    """
    title = item.get('title', '')
    summary = item.get('description', '')
    article_url = item.get('link', '')
    pub_date_str = item.get('pubDate', '')
    
    published_timestamp = parse_rss_date(pub_date_str)
    discovered_timestamp = datetime.now(timezone.utc)
    
    content_hash = compute_content_hash(source_title, title, article_url)
    record_id = content_hash
    
    raw_dict = {
        'title': title,
        'summary': summary,
        'article_url': article_url,
        'source_url': feed_url
    }
    validation_status = validate_record_dict(raw_dict)
    
    return IngestedNewsRecord(
        id=record_id,
        title=title,
        summary=summary,
        source=source_title,
        source_url=feed_url,
        article_url=article_url,
        published_timestamp=published_timestamp,
        discovered_timestamp=discovered_timestamp,
        content_hash=content_hash,
        validation_status=validation_status
    )
