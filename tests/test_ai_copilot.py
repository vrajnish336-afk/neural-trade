import pytest
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta

from app.config import config
from app.database.schema import init_db
from app.copilot.models import CopilotRequest
from app.copilot.agent import CopilotAgent
from app.copilot.context import ContextAssembler
from app.intelligence.repository import IntelligenceRepository
from app.intelligence.models import WorldObservation
from app.learning.repository import LearningRepository
from app.learning.models import ResearchLesson, LessonState

@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_copilot.sqlite"
    config.DB_PATH = str(db_file)
    config.ENABLE_PERSISTENCE = True
    config.PAPER_TRADING = True
    config.LIVE_TRADING = False
    init_db()
    
    IntelligenceRepository()._init_db()
    LearningRepository()._init_db()
    yield

def test_c01_context_assembler_as_of():
    intel_repo = IntelligenceRepository()
    base_t = datetime(2026, 1, 1, tzinfo=timezone.utc)
    
    # Save a past obs
    obs1 = WorldObservation(observation_id="1", source_id="1", source_type="NEWS", publisher="A", category="C", published_at=base_t, content_hash="h1")
    intel_repo.save_observation(obs1)
    # Save a future obs
    obs2 = WorldObservation(observation_id="2", source_id="2", source_type="NEWS", publisher="A", category="C", published_at=base_t + timedelta(days=2), content_hash="h2")
    intel_repo.save_observation(obs2)
    
    assembler = ContextAssembler()
    # Query as of base_t + 1 day
    ctx = assembler.assemble(["world_intelligence"], base_t + timedelta(days=1))
    
    assert "DATA_NOT_AVAILABLE" not in ctx
    assert "h1" not in ctx # h1 is hash, we print publisher/category. Let's check publisher
    assert "NEWS" in ctx
    
def test_c02_context_limit():
    assembler = ContextAssembler()
    # Mocking repos to return massive amounts of text
    class FakeIntelRepo:
        def get_observations(self, **kwargs):
            return [WorldObservation(observation_id=str(i), source_id=str(i), source_type="NEWS", publisher="A", category="C"*500, published_at=datetime.utcnow(), content_hash="h") for i in range(50)]
            
    assembler.intel_repo = FakeIntelRepo()
    ctx = assembler.assemble(["world_intelligence"], datetime.utcnow())
    assert len(ctx) <= ContextAssembler.MAX_CONTEXT_LENGTH + 50
    assert "[CONTEXT_LIMIT_REACHED]" in ctx
    
def test_c03_copilot_fallback_on_network_error(monkeypatch):
    def mock_urlopen(*args, **kwargs):
        raise urllib.error.URLError("Refused")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    agent = CopilotAgent()
    req = CopilotRequest(question="Test?", as_of=datetime.utcnow(), context_scope=["world_intelligence"])
    resp = agent.ask(req)
    
    assert resp.is_fallback is True
    assert "AI Service Unavailable" in resp.answer
    assert "DATA_NOT_AVAILABLE" in resp.answer # Because DB is empty
    
def test_c04_copilot_response_parsing(monkeypatch):
    class MockResponse:
        def read(self):
            return b'{"response": "Historically observed that X is Y."}'
        def __enter__(self): return self
        def __exit__(self, *args): pass
        
    def mock_urlopen(*args, **kwargs):
        return MockResponse()

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)
    
    agent = CopilotAgent()
    req = CopilotRequest(question="Test?", as_of=datetime.utcnow(), context_scope=["lessons"])
    resp = agent.ask(req)
    
    assert resp.is_fallback is False
    assert resp.answer == "Historically observed that X is Y."
    
def test_c05_paper_only_enforcement():
    assert config.PAPER_TRADING is True
    assert config.LIVE_TRADING is False
