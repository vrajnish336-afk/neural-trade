import hashlib

def compute_content_hash(source: str, title: str, article_url: str) -> str:
    """
    Computes a deterministic hash for deduplication based on canonicalized fields.
    """
    safe_source = (source or "").strip().lower()
    safe_title = (title or "").strip().lower()
    safe_url = (article_url or "").strip().lower()
    
    hash_input = f"{safe_source}|{safe_title}|{safe_url}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()
