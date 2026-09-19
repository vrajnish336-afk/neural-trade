import json
import logging
from datetime import datetime
from typing import List

from app.intelligence.repository import IntelligenceRepository
from app.learning.repository import LearningRepository
from app.forecasting.repository import ForecastRepository

logger = logging.getLogger(__name__)

class ContextAssembler:
    """Assembles read-only context deterministically, bounded by an as_of timestamp."""
    
    MAX_CONTEXT_LENGTH = 16000 # Character limit to avoid overwhelming the prompt
    
    def __init__(self):
        self.intel_repo = IntelligenceRepository()
        self.learning_repo = LearningRepository()
        self.forecast_repo = ForecastRepository()
        
    def assemble(self, scope: List[str], as_of: datetime, symbol: str = None) -> str:
        """Builds a strictly bound textual representation of requested system context."""
        context_parts = []
        limitations = []
        
        try:
            if "world_intelligence" in scope:
                context_parts.append(self._get_world_intelligence(as_of))
            
            if "lessons" in scope:
                context_parts.append(self._get_lessons(as_of))
                
            if "evolution_proposals" in scope:
                context_parts.append(self._get_evolution_proposals(as_of))
                
            if "forecasts" in scope:
                context_parts.append(self._get_forecasts(as_of, symbol))
                
        except Exception as e:
            logger.error(f"Context assembly failed: {e}")
            limitations.append("Context assembly partially failed due to system error.")
            
        full_context = "\n\n".join(context_parts)
        
        if len(full_context) > self.MAX_CONTEXT_LENGTH:
            full_context = full_context[:self.MAX_CONTEXT_LENGTH] + "\n...[CONTEXT_LIMIT_REACHED]"
            
        return full_context
        
    def _get_world_intelligence(self, as_of: datetime) -> str:
        obs = self.intel_repo.get_observations(as_of=as_of, limit=10)
        if not obs:
            return "WORLD INTELLIGENCE: DATA_NOT_AVAILABLE"
            
        lines = ["WORLD INTELLIGENCE:"]
        for o in obs:
            score = f"{o.sentiment_score:.2f}" if o.sentiment_score else "N/A"
            lines.append(f"- [{o.source_type}] {o.publisher}: {o.category} | Sentiment: {score} | Quality: {o.source_quality.value}")
            
        return "\n".join(lines)
        
    def _get_lessons(self, as_of: datetime) -> str:
        lessons = [l for l in self.learning_repo.get_lessons() if l.created_at <= as_of]
        if not lessons:
            return "LESSONS BANK: DATA_NOT_AVAILABLE"
            
        lines = ["LESSONS BANK:"]
        for l in lessons:
            lines.append(f"- [{l.state.value}] {l.strategy} under {l.regime}: {l.lesson_statement} (Evidence: {l.evidence_count}, Confidence: {l.confidence_score})")
            
        return "\n".join(lines)
        
    def _get_evolution_proposals(self, as_of: datetime) -> str:
        proposals = [p for p in self.learning_repo.get_proposals() if p.created_at <= as_of]
        if not proposals:
            return "EVOLUTION PROPOSALS: DATA_NOT_AVAILABLE"
            
        lines = ["EVOLUTION PROPOSALS:"]
        for p in proposals:
            lines.append(f"- [{p.state.value}] {p.strategy}: {p.reason}")
            
        return "\n".join(lines)
        
    def _get_forecasts(self, as_of: datetime, symbol: str) -> str:
        # Forecasts have a created_at property, we must respect as_of
        records = [r for r in self.forecast_repo.get_records(symbol) if r.created_at <= as_of]
        if not records:
            return "FORECASTS: DATA_NOT_AVAILABLE"
            
        lines = ["FORECASTS:"]
        # Limit to the 3 most recent
        for r in records[:3]:
            mae = f"{r.mae:.4f}" if r.mae else "N/A"
            lines.append(f"- [{r.model_name}] {r.symbol} Horizon {r.forecast_horizon} | MAE: {mae} | Status: {r.status}")
            
        return "\n".join(lines)
