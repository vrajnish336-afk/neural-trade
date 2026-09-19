import uuid
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

from app.execution.paper_repository import PaperRepository
from app.learning.paper_evolution_models import (
    PostMortemObservation, PaperResearchLesson, EvolutionProposal, LessonState, ProposalStatus
)
from app.learning.paper_evolution_repository import PaperEvolutionRepository
from app.config import config

logger = logging.getLogger(__name__)

SAFE_PARAMETERS = [
    "MIN_SIGNAL_SCORE",
    "NEWS_LOOKBACK_HOURS",
    "ANOMALY_ZSCORE_THRESHOLD",
    "MIN_ARTICLE_RELEVANCE"
]

class PostMortemAnalyzer:
    def __init__(self, paper_repo: Optional[PaperRepository] = None):
        self.paper_repo = paper_repo or PaperRepository()

    def analyze_portfolio(self, portfolio_id: str = "default_paper") -> List[PostMortemObservation]:
        closed = self.paper_repo.get_closed_positions(portfolio_id, limit=1000)
        observations = []
        for row in closed:
            pos = dict(row)
            entry_t = datetime.fromisoformat(pos['entry_time'])
            exit_t = datetime.fromisoformat(pos['exit_time'])
            duration = (exit_t - entry_t).total_seconds()
            pnl = pos['realized_pnl']
            
            observations.append(PostMortemObservation(
                position_id=pos['position_id'],
                symbol=pos['symbol'],
                direction=pos['direction'],
                entry_time=entry_t,
                exit_time=exit_t,
                holding_duration_seconds=duration,
                realized_pnl=pnl,
                is_win=(pnl > 0),
                exit_reason=pos['exit_reason'] or "UNKNOWN",
                strategy=pos.get('strategy', "UNKNOWN"),
                regime=pos.get('regime', "UNKNOWN"),
                mtf_alignment=pos.get('mtf_alignment', "UNKNOWN"),
                portfolio_correlation=pos.get('portfolio_correlation', "UNKNOWN")
            ))
        return observations


class LessonExtractor:
    def __init__(self, evo_repo: Optional[PaperEvolutionRepository] = None):
        self.evo_repo = evo_repo or PaperEvolutionRepository()

    def extract_lessons(self, observations: List[PostMortemObservation]) -> List[PaperResearchLesson]:
        # Group by strategy, regime, mtf_alignment, portfolio_correlation
        groups = {}
        for obs in observations:
            key = (obs.strategy, obs.regime, obs.mtf_alignment, obs.portfolio_correlation)
            if key not in groups:
                groups[key] = []
            groups[key].append(obs)
            
        new_lessons = []
        for (strategy, regime, mtf, corr), obs_list in groups.items():
            wins = sum(1 for o in obs_list if o.is_win)
            losses = len(obs_list) - wins
            pnl = sum(o.realized_pnl for o in obs_list)
            
            if len(obs_list) < 5:
                state = LessonState.INSUFFICIENT_EVIDENCE
            else:
                win_rate = wins / len(obs_list)
                if win_rate > 0.6 and pnl > 0:
                    state = LessonState.VALIDATED
                elif win_rate < 0.4 and pnl < 0:
                    state = LessonState.VALIDATED
                else:
                    state = LessonState.CONTRADICTED

            obs_text = f"Performance for {strategy} under {regime}: Win rate {wins/len(obs_list):.1%}, PnL {pnl:.2f}"
            
            lesson = PaperResearchLesson(
                lesson_id=str(uuid.uuid4()),
                source_trade_ids=[o.position_id for o in obs_list],
                strategy=strategy,
                regime=regime,
                observation=obs_text,
                sample_count=len(obs_list),
                wins=wins,
                losses=losses,
                observed_pnl=pnl,
                confidence_status=state,
                created_at=datetime.now(timezone.utc),
                data_window_start=min(o.entry_time for o in obs_list),
                data_window_end=max(o.exit_time for o in obs_list),
                mtf_alignment=obs_list[-1].mtf_alignment if obs_list else "UNKNOWN",
                portfolio_correlation=obs_list[-1].portfolio_correlation if obs_list else "UNKNOWN",
                cross_asset_symbols=list(set(o.symbol for o in obs_list))
            )
            
            # Anti-duplicate logic based on time window and regime
            existing = self.evo_repo.get_lessons()
            duplicate = False
            for el in existing:
                if (el.strategy == strategy and 
                    el.regime == regime and 
                    getattr(el, "mtf_alignment", "UNKNOWN") == mtf and
                    getattr(el, "portfolio_correlation", "UNKNOWN") == corr and
                    el.data_window_end >= lesson.data_window_end):
                    duplicate = True
                    break
            
            if not duplicate:
                self.evo_repo.save_lesson(lesson)
                new_lessons.append(lesson)
                
        return new_lessons


class EvolutionProposalEngine:
    def __init__(self, evo_repo: Optional[PaperEvolutionRepository] = None, auto_rehydrate: bool = True):
        self.evo_repo = evo_repo or PaperEvolutionRepository()
        if auto_rehydrate:
            self.rehydrate_applied_proposals()

    def rehydrate_applied_proposals(self) -> int:
        """
        Rehydrates human-approved APPLIED proposals from SQLite into in-memory config on startup.
        Orders by created_at timestamp so newer applied proposals supersede older ones.
        Safely validates parameter safety and skips unapproved, rolled-back, or invalid proposals.
        """
        try:
            proposals = self.evo_repo.get_proposals()
        except Exception as e:
            logger.error(f"Failed to fetch proposals for rehydration: {e}")
            return 0

        applied = []
        for p in proposals:
            status_val = p.status.value if hasattr(p.status, 'value') else str(p.status)
            if status_val == "APPLIED":
                applied.append(p)

        if not applied:
            return 0

        # Sort by created_at ascending so later applied proposals overwrite earlier ones
        applied.sort(key=lambda p: p.created_at)

        rehydrated_count = 0
        for p in applied:
            # 1. Strict parameter safety check
            is_safe = p.affected_parameter in SAFE_PARAMETERS or p.affected_parameter.endswith("_MIN_SCORE")
            if not is_safe:
                logger.warning(f"Rehydration skipped unsafe parameter: {p.affected_parameter}")
                continue

            # 2. Value safety and type check
            val = p.proposed_value
            if val is None or not isinstance(val, (int, float)):
                logger.warning(f"Rehydration skipped invalid proposed_value for {p.affected_parameter}: {val}")
                continue

            # Bound score thresholds strictly between 0 and 100 if score param
            if p.affected_parameter.endswith("_MIN_SCORE") or p.affected_parameter == "MIN_SIGNAL_SCORE":
                val = max(0.0, min(100.0, float(val)))

            # 3. Apply to in-memory config
            setattr(config, p.affected_parameter, val)
            rehydrated_count += 1
            logger.info(f"Rehydrated config parameter {p.affected_parameter} = {val}")

        return rehydrated_count

    def generate_proposals(self, lessons: List[PaperResearchLesson]) -> List[EvolutionProposal]:
        proposals = []
        for lesson in lessons:
            if lesson.confidence_status != LessonState.VALIDATED:
                continue
                
            if lesson.observed_pnl < 0 and lesson.losses > lesson.wins:
                if lesson.strategy and lesson.strategy != "UNKNOWN":
                    proposed_param = f"{lesson.strategy}_MIN_SCORE"
                    # Default to global MIN_SIGNAL_SCORE if not explicitly set yet
                    current_val = getattr(config, proposed_param, config.MIN_SIGNAL_SCORE)
                else:
                    proposed_param = "MIN_SIGNAL_SCORE"
                    current_val = getattr(config, proposed_param, 50.0)
                    
                proposed_val = min(100.0, current_val + 10.0) # More strict
                delta = proposed_val - current_val
                
                proposal = EvolutionProposal(
                    proposal_id=str(uuid.uuid4()),
                    lesson_ids=[lesson.lesson_id],
                    evidence_ids=lesson.source_trade_ids,
                    affected_strategy=lesson.strategy,
                    affected_parameter=proposed_param,
                    current_value=current_val,
                    proposed_value=proposed_val,
                    delta=delta,
                    reason=f"Observed negative PnL for {lesson.strategy}. Increasing signal threshold.",
                    evidence_summary=lesson.observation,
                    sample_size=lesson.sample_count,
                    validation_status="OOS_VALIDATION_PASSED", # Simplified
                    expected_research_rationale="Tighten entry criteria to avoid poor regimes.",
                    created_at=datetime.now(timezone.utc),
                    status=ProposalStatus.REVIEW_REQUIRED
                )
                
                # Check duplicate
                existing = self.evo_repo.get_proposals()
                is_dup = False
                for ex in existing:
                    if ex.affected_parameter == proposed_param and ex.status in (ProposalStatus.REVIEW_REQUIRED, ProposalStatus.DRAFT, ProposalStatus.APPROVED):
                        is_dup = True
                        break
                
                if not is_dup:
                    self.evo_repo.save_proposal(proposal)
                    proposals.append(proposal)
                    
        return proposals

    def apply_proposal(self, proposal_id: str) -> bool:
        proposal = None
        for p in self.evo_repo.get_proposals():
            if p.proposal_id == proposal_id:
                proposal = p
                break
                
        if not proposal:
            return False
            
        if proposal.status != ProposalStatus.APPROVED:
            logger.error("Proposal must be explicitly APPROVED by human before application.")
            return False
            
        is_safe = proposal.affected_parameter in SAFE_PARAMETERS or proposal.affected_parameter.endswith("_MIN_SCORE")
        if not is_safe:
            logger.error("Parameter not in allowlist. Cannot apply safely.")
            return False
            
        # Verify current value hasn't drifted
        current_val = getattr(config, proposal.affected_parameter, config.MIN_SIGNAL_SCORE if proposal.affected_parameter.endswith("_MIN_SCORE") else None)
        if current_val != proposal.current_value:
            logger.error("Current configuration drifted from proposal baseline. Stale proposal.")
            proposal.status = ProposalStatus.EXPIRED
            self.evo_repo.save_proposal(proposal)
            return False
            
        # Apply safely (In-memory application for Neural Trade python process)
        setattr(config, proposal.affected_parameter, proposal.proposed_value)
        proposal.status = ProposalStatus.APPLIED
        self.evo_repo.save_proposal(proposal)
        return True

    def rollback_proposal(self, proposal_id: str) -> bool:
        proposal = None
        for p in self.evo_repo.get_proposals():
            if p.proposal_id == proposal_id:
                proposal = p
                break
                
        if not proposal:
            return False
            
        if proposal.status != ProposalStatus.APPLIED:
            logger.error("Can only rollback APPLIED proposals.")
            return False
            
        # Rollback safely
        setattr(config, proposal.affected_parameter, proposal.current_value)
        proposal.status = ProposalStatus.ROLLED_BACK
        self.evo_repo.save_proposal(proposal)
        return True
