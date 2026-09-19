import uuid
import logging
from typing import List
from datetime import datetime
from app.learning.models import ResearchLesson, LessonState
from app.learning.trade_analyzer import RegimePerformance, TradeAnalyzer
from app.learning.repository import LearningRepository

logger = logging.getLogger(__name__)

class LessonEngine:
    """Extracts and ranks lessons deterministically."""
    
    def __init__(self):
        self.analyzer = TradeAnalyzer()
        self.repo = LearningRepository()
        
    def extract_lessons(self, identity_hash: str) -> List[ResearchLesson]:
        """Extracts lessons based on statistical patterns in paper observations."""
        performances = self.analyzer.analyze_candidate(identity_hash)
        new_lessons = []
        
        for perf in performances:
            total_obs = perf.win_count + perf.loss_count
            if total_obs == 0: continue
            
            win_rate = perf.win_count / total_obs
            
            # Deterministic Lesson Creation
            statement = f"Performance under {perf.regime} regime: Win rate {win_rate:.1%}, Avg PnL {perf.avg_pnl:.2f}"
            
            if total_obs < 3:
                state = LessonState.INSUFFICIENT_EVIDENCE
                confidence = 0.1
            elif win_rate >= 0.6 and perf.avg_pnl > 0:
                state = LessonState.SUPPORTED
                confidence = min(0.9, 0.4 + (total_obs * 0.05))
            elif win_rate <= 0.4 and perf.avg_pnl < 0:
                state = LessonState.SUPPORTED
                confidence = min(0.9, 0.4 + (total_obs * 0.05))
            else:
                state = LessonState.MIXED_EVIDENCE
                confidence = 0.5
                
            lesson = ResearchLesson(
                lesson_id=str(uuid.uuid4()),
                identity_hash=perf.identity_hash,
                strategy=perf.strategy,
                regime=perf.regime,
                lesson_statement=statement,
                evidence_count=total_obs,
                supporting_observation_ids=perf.observation_ids if state == LessonState.SUPPORTED else [],
                conflicting_observation_ids=perf.observation_ids if state == LessonState.MIXED_EVIDENCE else [],
                confidence_score=confidence,
                state=state,
                created_at=datetime.utcnow(),
                last_observed_at=datetime.utcnow()
            )
            
            # Check for exact duplicate via hash
            existing = self.repo.get_lessons(identity_hash)
            is_dup = any(l.get_hash() == lesson.get_hash() for l in existing)
            
            if not is_dup:
                self.repo.save_lesson(lesson)
                new_lessons.append(lesson)
                
        return new_lessons

    def rank_lessons(self, lessons: List[ResearchLesson]) -> List[ResearchLesson]:
        """
        Rank lessons deterministically.
        Score = Evidence Count * Confidence - (Conflicts * 0.5)
        NOT solely based on PnL.
        """
        def _score(l: ResearchLesson) -> float:
            base = l.evidence_count * l.confidence_score
            penalty = len(l.conflicting_observation_ids) * 0.5
            return base - penalty
            
        return sorted(lessons, key=_score, reverse=True)
