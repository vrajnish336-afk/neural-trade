import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone

from app.intelligence.adapters.news import NewsAdapter
from app.news.models import IngestedNewsRecord
from app.intelligence.models import SourceQuality

@pytest.fixture
def sample_record_high_quality():
    return IngestedNewsRecord(
        id="123",
        title="SEC Approves Bitcoin ETF",
        summary="The SEC has officially approved...",
        source="Reuters",
        source_url="https://reuters.com/news/123",
        article_url="https://reuters.com/news/123",
        published_timestamp=datetime.now(timezone.utc),
        discovered_timestamp=datetime.now(timezone.utc),
        content_hash="hash123",
        validation_status="VALID"
    )

@pytest.fixture
def sample_record_low_quality():
    return IngestedNewsRecord(
        id="456",
        title="Bitcoin might hit 100k",
        summary="Some guy on Twitter said...",
        source="CryptoGossip",
        source_url="https://cryptogossip.com/news/456",
        article_url="https://cryptogossip.com/news/456",
        published_timestamp=datetime.now(timezone.utc),
        discovered_timestamp=datetime.now(timezone.utc),
        content_hash="hash456",
        validation_status="VALID"
    )

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_verified_accepted(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "{\\"credibility\\": \\"VERIFIED\\"}"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 1
    assert obs[0].source_id == "123"

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_unverified_dropped(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "{\\"credibility\\": \\"UNVERIFIED\\"}"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_rumor_dropped(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "{\\"credibility\\": \\"RUMOR\\"}"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_conflicting_dropped(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "{\\"credibility\\": \\"CONFLICTING\\"}"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_missing_corroboration_dropped(mock_urlopen, mock_config, sample_record_low_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    # LLM says VERIFIED, but source is low quality
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "{\\"credibility\\": \\"VERIFIED\\"}"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_low_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0  # Dropped due to lack of trusted source corroboration

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_network_failure_dropped(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_urlopen.side_effect = Exception("Network timeout")
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0  # Fails closed

@patch("app.intelligence.adapters.news.config")
@patch("app.intelligence.adapters.news.urllib.request.urlopen")
def test_credibility_filter_malformed_response_dropped(mock_urlopen, mock_config, sample_record_high_quality):
    mock_config.NEWS_CREDIBILITY_FILTER_ENABLED = True
    
    mock_response = MagicMock()
    mock_response.read.return_value = b'{"response": "this is not json"}'
    mock_urlopen.return_value.__enter__.return_value = mock_response
    
    adapter = NewsAdapter()
    adapter.collector.collect = MagicMock(return_value=[sample_record_high_quality])
    
    obs = adapter.fetch_observations()
    assert len(obs) == 0  # Fails closed

@patch("app.intelligence.adapters.news.config")
def test_no_trading_capability_from_news(mock_config, sample_record_high_quality):
    # LLM output cannot create/approve/reject a trade directly because it only produces a WorldObservation
    # We verify the adapter has no references to execution or brokers.
    adapter = NewsAdapter()
    assert not hasattr(adapter, 'execute_decision')
    assert not hasattr(adapter, 'submit_order')
    assert not hasattr(adapter, 'place_order')
