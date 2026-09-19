import pytest
from datetime import datetime, timezone, timedelta
import json
import urllib.request

from app.config import config
from app.database.schema import init_db
from app.intelligence.repository import IntelligenceRepository
from app.intelligence.models import WorldObservation, SourceQuality
from app.intelligence.service import WorldIntelligenceService
from app.intelligence.adapters.sentiment import FearAndGreedAdapter
from app.intelligence.adapters.macro import MacroAdapter, FlowAdapter

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_intelligence.sqlite"
    config.DB_PATH = str(db_file)
    config.ENABLE_PERSISTENCE = True
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    init_db()
    
    repo = IntelligenceRepository()
    repo._init_db()
    yield repo

def test_i01_as_of_filtering(setup_test_db):
    repo = setup_test_db
    base_t = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    
    # Save obs published at base_t
    obs1 = WorldObservation(
        observation_id="1", source_id="1", source_type="NEWS", publisher="A", category="C",
        published_at=base_t, retrieved_at=base_t, content_hash="h1"
    )
    # Save obs published one day later
    obs2 = WorldObservation(
        observation_id="2", source_id="2", source_type="NEWS", publisher="A", category="C",
        published_at=base_t + timedelta(days=1), retrieved_at=base_t + timedelta(days=1), content_hash="h2"
    )
    repo.save_observation(obs1)
    repo.save_observation(obs2)
    
    # Query with as_of exactly base_t
    results = repo.get_observations(as_of=base_t)
    assert len(results) == 1
    assert results[0].observation_id == "1"

def test_i02_missing_published_at_fallback(setup_test_db):
    repo = setup_test_db
    base_t = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    
    # Missing published_at but retrieved_at is before as_of
    obs1 = WorldObservation(
        observation_id="1", source_id="1", source_type="NEWS", publisher="A", category="C",
        published_at=None, retrieved_at=base_t - timedelta(hours=1), content_hash="h1"
    )
    # Missing published_at and retrieved_at is after as_of
    obs2 = WorldObservation(
        observation_id="2", source_id="2", source_type="NEWS", publisher="A", category="C",
        published_at=None, retrieved_at=base_t + timedelta(hours=1), content_hash="h2"
    )
    repo.save_observation(obs1)
    repo.save_observation(obs2)
    
    results = repo.get_observations(as_of=base_t)
    assert len(results) == 1
    assert results[0].observation_id == "1"

def test_i03_fear_greed_normalization(monkeypatch):
    class MockResponse:
        def __init__(self):
            self.status = 200
        def read(self, size):
            return b'{"name": "Fear and Greed Index", "data": [{"value": "25", "value_classification": "Extreme Fear", "timestamp": "1610000000", "time_until_update": "100"}]}'
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass

    def mock_urlopen(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    adapter = FearAndGreedAdapter()
    obs = adapter.fetch_observations()
    assert len(obs) == 1
    # 25 / 50.0 - 1.0 = -0.5
    assert obs[0].sentiment_score == -0.5
    assert obs[0].source_quality == SourceQuality.MEDIUM

def test_i04_fear_greed_offline(monkeypatch):
    def mock_urlopen(*args, **kwargs):
        raise urllib.error.URLError("Network unreachable")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    adapter = FearAndGreedAdapter()
    obs = adapter.fetch_observations()
    assert len(obs) == 0

def test_i05_unavailable_macro_flow():
    # Enforces we don't fabricate data
    macro = MacroAdapter()
    assert len(macro.fetch_observations()) == 0
    flow = FlowAdapter()
    assert len(flow.fetch_observations()) == 0

def test_i06_paper_only_enforcement():
    assert config.PAPER_TRADING is True
    assert config.LIVE_TRADING is False

def test_i07_aggregation_deterministic(setup_test_db):
    svc = WorldIntelligenceService()
    now = datetime.utcnow().replace(tzinfo=timezone.utc)
    ctx1 = svc.aggregate_context(now)
    ctx2 = svc.aggregate_context(now)
    assert ctx1.lineage_hash == ctx2.lineage_hash
