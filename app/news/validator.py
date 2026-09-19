import urllib.parse

def is_valid_url(url: str) -> bool:
    if not url:
        return False
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme in ("http", "https"), result.netloc])
    except Exception:
        return False

def validate_record_dict(record_dict: dict) -> str:
    """
    Validates the raw dictionary before it becomes an IngestedNewsRecord.
    Returns 'VALID' or 'REJECTED'.
    """
    title = record_dict.get('title', '')
    if not title or len(title) > 1000:
        return 'REJECTED'
        
    article_url = record_dict.get('article_url', '')
    if not is_valid_url(article_url):
        return 'REJECTED'
        
    # Extra safety: Ensure no scripts in title or summary
    summary = record_dict.get('summary', '')
    if '<script' in title.lower() or '<script' in summary.lower():
        return 'REJECTED'
        
    return 'VALID'
