import pytest
from datetime import datetime, timezone
from app.news.deduplicator import compute_content_hash
from app.news.validator import is_valid_url, validate_record_dict
from app.news.normalizer import parse_rss_date, normalize_rss_item
from app.news.models import IngestedNewsRecord
from app.news.collector import NewsCollector
from app.news.repository import NewsRepository

def test_deduplicator_hash_stability():
    hash1 = compute_content_hash("Source", "Title", "http://url")
    hash2 = compute_content_hash("source", "title ", " HTTP://URL ")
    assert hash1 == hash2

def test_validator_url():
    assert is_valid_url("https://example.com") is True
    assert is_valid_url("http://news.google.com") is True
    assert is_valid_url("not_a_url") is False
    assert is_valid_url("") is False

def test_validator_record_dict():
    valid_dict = {
        'title': 'Good Title',
        'article_url': 'https://example.com'
    }
    assert validate_record_dict(valid_dict) == 'VALID'
    
    no_title = {'article_url': 'https://example.com'}
    assert validate_record_dict(no_title) == 'REJECTED'
    
    bad_url = {'title': 'Good Title', 'article_url': 'ftp://example.com'}
    assert validate_record_dict(bad_url) == 'REJECTED'
    
    script_injection = {'title': 'Breaking <script>alert(1)</script>', 'article_url': 'https://example.com'}
    assert validate_record_dict(script_injection) == 'REJECTED'

def test_normalizer_date_parsing():
    dt = parse_rss_date("Tue, 01 Nov 2022 14:00:00 GMT")
    assert dt is not None
    assert dt.year == 2022
    assert dt.month == 11
    
    dt_invalid = parse_rss_date("Invalid Date")
    assert dt_invalid is None

def test_normalize_rss_item():
    raw_item = {
        'title': 'Test Article',
        'description': 'Test Summary',
        'link': 'https://example.com/test',
        'pubDate': 'Tue, 01 Nov 2022 14:00:00 GMT'
    }
    record = normalize_rss_item(raw_item, 'https://feed.com', 'Test Source')
    assert isinstance(record, IngestedNewsRecord)
    assert record.title == 'Test Article'
    assert record.validation_status == 'VALID'
    assert record.published_timestamp is not None
    assert record.content_hash == compute_content_hash('Test Source', 'Test Article', 'https://example.com/test')

def test_collector_offline_mode():
    # Use an invalid unresolvable domain to simulate network failure
    collector = NewsCollector(feeds=["https://this.is.an.invalid.domain.that.will.fail.com/rss"], timeout=1)
    records = collector.collect()
    assert len(records) == 0

def test_repository_idempotent_insert():
    import tempfile
    import sqlite3
    import os
    
    fd, temp_path = tempfile.mkstemp()
    os.close(fd)
    
    try:
        repo = NewsRepository(db_path=temp_path)
        
        conn = repo._get_conn()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute('''CREATE TABLE news_articles (
                    id TEXT PRIMARY KEY, title TEXT, summary TEXT, source TEXT, source_url TEXT, article_url TEXT,
                    published_timestamp TEXT, discovered_timestamp TEXT, content_hash TEXT, validation_status TEXT)''')
        finally:
            conn.close()
        
        raw_item = {'title': 'Test DB', 'link': 'https://example.com', 'pubDate': 'Tue, 01 Nov 2022 14:00:00 GMT'}
        record = normalize_rss_item(raw_item, 'https://feed.com', 'Source')
        
        # First insert
        inserted, dupes = repo.save_records([record])
        assert inserted == 1
        assert dupes == 0
        
        # Second insert (duplicate)
        inserted2, dupes2 = repo.save_records([record])
        assert inserted2 == 0
        assert dupes2 == 1
    finally:
        os.unlink(temp_path)
