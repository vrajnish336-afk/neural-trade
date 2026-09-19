import logging
import json
from typing import List, Optional, Dict
from datetime import datetime

from app.research.portfolio_models import (
    ResearchCandidateSnapshot, ResearchPriority, 
    ResearchEvidenceScore, CandidateComparisonMatrix
)
from app.research.track_record_models import StrategyHealthState
from app.research.decision_models import ResearchDecisionState
from app.research.forward_validation_models import ForwardDriftState
from app.research.comparator import ComparabilityStatus

from app.research.track_record_service import PaperTrackRecordService
from app.research.decision_engine import ResearchDecisionEngine
from app.research.memory_repository import ResearchMemoryRepository
from app.research.knowledge_service import ResearchKnowledgeService
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

class ResearchPortfolioService:
    """Builds read-only candidate snapshots and comparisons over research data."""
    
    def __init__(self):
        self.track_service = PaperTrackRecordService()
        self.decision_engine = ResearchDecisionEngine()
        self.memory_repo = ResearchMemoryRepository()
        self.knowledge_service = ResearchKnowledgeService()

    def _calculate_score_and_priority(self, 
                                      decision: ResearchDecisionState, 
                                      health: StrategyHealthState, 
                                      obs_count: int, 
                                      drift: ForwardDriftState,
                                      conflicts: int,
                                      missing_lineage: bool) -> tuple[ResearchEvidenceScore, ResearchPriority, List[str]]:
        
        hist_score = 0
        fwd_score = 0
        health_score = 0
        penalty = 0
        reasons = []
        
        # 1. Historical Evidence
        if decision == ResearchDecisionState.RESEARCH_RESULT_SUPPORTED:
            hist_score = 3
            reasons.append("Strong historical evidence.")
        elif decision == ResearchDecisionState.SUPPORTED_FOR_FURTHER_RESEARCH:
            hist_score = 2
            reasons.append("Historical evidence requires forward validation.")
        elif decision == ResearchDecisionState.CONTRADICTORY_EVIDENCE:
            hist_score = 1
            penalty += 2
            reasons.append("Historical evidence contains contradictions.")
        elif decision == ResearchDecisionState.INSUFFICIENT_EVIDENCE:
            reasons.append("Insufficient historical evidence.")
            
        # 2. Forward Evidence
        if obs_count >= 5:
            fwd_score = 3
            reasons.append("Robust forward sample size.")
        elif obs_count >= 2:
            fwd_score = 2
            reasons.append("Growing forward sample size.")
        elif obs_count == 1:
            fwd_score = 1
            reasons.append("Minimal forward evidence.")
        else:
            reasons.append("No forward evidence.")
            
        # 3. Health
        if health == StrategyHealthState.HEALTHY:
            health_score = 3
            reasons.append("Strategy health is completely stable.")
        elif health == StrategyHealthState.WATCH:
            health_score = 1
            reasons.append("Strategy health on watch (recent degradation).")
        elif health == StrategyHealthState.DEGRADED:
            health_score = -1
            reasons.append("Strategy health is degraded.")
        elif health == StrategyHealthState.CRITICAL:
            health_score = -3
            reasons.append("Strategy health is CRITICAL.")
        elif health == StrategyHealthState.INSUFFICIENT_HISTORY:
            reasons.append("Insufficient health history.")
            
        # 4. Drift & Quality Penalties
        if drift == ForwardDriftState.SIGNIFICANTLY_DEGRADED:
            penalty += 2
            reasons.append("Significant performance drift detected.")
        if conflicts > 0:
            penalty += conflicts
            reasons.append(f"{conflicts} unresolved research conflict(s).")
        if missing_lineage:
            penalty += 5
            reasons.append("Missing critical research lineage (BLOCKED).")
            
        total = hist_score + fwd_score + health_score - penalty
        score = ResearchEvidenceScore(
            total_score=total,
            historical_evidence_score=hist_score,
            forward_evidence_score=fwd_score,
            health_score=health_score,
            penalty_score=penalty
        )
        
        # Priority mapping (Research Priority, NOT Trading Priority)
        # High priority means it urgently needs research attention (either it's very promising, or breaking down)
        if missing_lineage or decision in [ResearchDecisionState.SOFTWARE_OR_ACCOUNTING_ISSUE, ResearchDecisionState.BLOCKED]:
            priority = ResearchPriority.BLOCKED
        elif conflicts > 0 or health in [StrategyHealthState.DEGRADED, StrategyHealthState.CRITICAL]:
            priority = ResearchPriority.VERY_HIGH
            reasons.append("PRIORITY: Urgent investigation required due to conflicts or critical degradation.")
        elif hist_score >= 2 and fwd_score < 2:
            priority = ResearchPriority.HIGH
            reasons.append("PRIORITY: Strong historical candidate urgently needs forward validation.")
        elif total >= 6:
            priority = ResearchPriority.MEDIUM
            reasons.append("PRIORITY: Solid evidence base, continue standard monitoring.")
        else:
            priority = ResearchPriority.LOW
            
        return score, priority, reasons

    def build_snapshot(self, identity_hash: str, as_of: Optional[datetime] = None) -> Optional[ResearchCandidateSnapshot]:
        # Helper to append time filters
        def _tf(col: str) -> str:
            return f" AND {col} <= ?" if as_of else ""
            
        def _tp(base_params: tuple) -> tuple:
            return base_params + (as_of.isoformat(),) if as_of else base_params

        mem = self.memory_repo.get_memory(identity_hash)
        if not mem: return None
        # We assume ResearchMemory itself is a singular record, but we could filter it out if first_seen_at > as_of
        if as_of and mem.first_seen_at:
            mem_dt = mem.first_seen_at if isinstance(mem.first_seen_at, datetime) else datetime.fromisoformat(mem.first_seen_at)
            mem_dt_comp = mem_dt.replace(tzinfo=None) if mem_dt.tzinfo else mem_dt
            as_of_comp = as_of.replace(tzinfo=None) if as_of.tzinfo else as_of
            if mem_dt_comp > as_of_comp:
                return None
        
        # Get Latest Conclusion
        dec_state = ResearchDecisionState.INSUFFICIENT_EVIDENCE
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT decision_state FROM research_conclusions 
                    WHERE identity_hash = ? {_tf('created_at')} ORDER BY created_at DESC LIMIT 1
                """, _tp((identity_hash,)))
                row = cursor.fetchone()
                if row:
                    dec_state = ResearchDecisionState(row[0])
        except Exception as e:
            logger.error(f"Failed to fetch conclusion for {identity_hash}: {e}")
        
        # Get Track Record
        obs_count = 0
        health = StrategyHealthState.INSUFFICIENT_HISTORY
        cum_pnl = 0.0
        max_dd = 0.0
        drift = ForwardDriftState.UNRESOLVED
        missing_lineage = False
        
        try:
            with self.track_service._get_conn() as conn:
                cursor = conn.cursor()
                
                # We need to construct the track record AS OF the timestamp.
                # If we just fetch paper_track_records, we might get future health.
                # The prompt asks for chronological reconstruction.
                # So we must compute obs_count, cum_pnl, max_dd FROM paper_observations directly!
                cursor.execute(f"""
                    SELECT track_record_id FROM paper_track_records 
                    WHERE identity_hash = ? {_tf('created_at')} ORDER BY created_at ASC LIMIT 1
                """, _tp((identity_hash,)))
                tr_row = cursor.fetchone()
                
                if tr_row:
                    tr_id = tr_row[0]
                    
                    if not as_of:
                        # Fast path: fetch latest from track record directly
                        cursor.execute("""
                            SELECT observation_count, cumulative_pnl, max_drawdown_pct, current_health_state 
                            FROM paper_track_records WHERE track_record_id = ?
                        """, (tr_id,))
                        tr_latest = cursor.fetchone()
                        if tr_latest:
                            obs_count, cum_pnl, max_dd = tr_latest[0], tr_latest[1], tr_latest[2]
                            health = StrategyHealthState(tr_latest[3])
                    else:
                        # 1. Observations aggregate AS OF time
                        cursor.execute(f"""
                            SELECT COUNT(*), SUM(net_pnl), MIN(drawdown_pct)
                            FROM paper_observations WHERE track_record_id = ? {_tf('observation_end')}
                        """, _tp((tr_id,)))
                        obs_aggr = cursor.fetchone()
                        if obs_aggr and obs_aggr[0] > 0:
                            obs_count = obs_aggr[0]
                            cum_pnl = obs_aggr[1] if obs_aggr[1] else 0.0
                            max_dd = obs_aggr[2] if obs_aggr[2] else 0.0
                        
                    # 2. Latest drift
                    cursor.execute(f"""
                        SELECT drift_state FROM paper_observations WHERE track_record_id = ? {_tf('observation_end')}
                        ORDER BY observation_end DESC LIMIT 1
                    """, _tp((tr_id,)))
                    drift_row = cursor.fetchone()
                    if drift_row and drift_row[0]:
                        drift = ForwardDriftState(drift_row[0])
                        
                    # 3. Latest Health
                    cursor.execute(f"""
                        SELECT new_state FROM paper_health_history WHERE track_record_id = ? {_tf('created_at')}
                        ORDER BY created_at DESC LIMIT 1
                    """, _tp((tr_id,)))
                    health_row = cursor.fetchone()
                    if health_row:
                        health = StrategyHealthState(health_row[0])
                    elif obs_count > 0 and as_of:
                        # Fallback: If observations exist but no health history transitions exist before as_of,
                        # it means the candidate is in its initial state, which is HEALTHY.
                        health = StrategyHealthState.HEALTHY
        except Exception as e:
            logger.error(f"Failed to fetch track record for {identity_hash}: {e}")
            missing_lineage = True
            
        # Get Conflicts & Opportunities
        conflicts = 0
        opps = 0
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                    SELECT COUNT(*) FROM research_conflicts 
                    WHERE identity_hash = ? AND resolution_status = 'UNRESOLVED' {_tf('created_at')}
                """, _tp((identity_hash,)))
                conflicts = cursor.fetchone()[0]
                
                cursor.execute(f"""
                    SELECT COUNT(*) FROM research_opportunities 
                    WHERE identity_hash = ? AND status != 'COMPLETED' {_tf('created_at')}
                """, _tp((identity_hash,)))
                opps = cursor.fetchone()[0]
        except Exception as e:
            logger.error(f"Failed to fetch conflicts/opps for {identity_hash}: {e}")
        
        score, priority, reasons = self._calculate_score_and_priority(
            dec_state, health, obs_count, drift, conflicts, missing_lineage
        )
        
        return ResearchCandidateSnapshot(
            identity_hash=identity_hash,
            canonical_hypothesis=mem.canonical_hypothesis,
            strategy=mem.mapped_strategy,
            symbols=mem.affected_symbols if mem.affected_symbols else [],
            timeframe="1d", # Approximated for view
            forward_observation_count=obs_count,
            current_health=health,
            latest_drift=drift,
            decision_state=dec_state,
            cumulative_forward_pnl=cum_pnl,
            max_forward_drawdown_pct=max_dd,
            unresolved_conflicts=conflicts,
            open_opportunities=opps,
            missing_lineage=missing_lineage,
            priority=priority,
            priority_reasons=reasons,
            evidence_score=score
        )

    def get_portfolio(self, limit: int = 50) -> List[ResearchCandidateSnapshot]:
        telemetry.record_stage("PAPER_CANDIDATE_PORTFOLIO_LOADED")
        portfolio = []
        try:
            with self.memory_repo._get_conn() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT identity_hash FROM research_memory ORDER BY last_researched_at DESC LIMIT ?", (limit,))
                hashes = [row[0] for row in cursor.fetchall()]
                
            for h in hashes:
                snap = self.build_snapshot(h)
                if snap: portfolio.append(snap)
        except Exception as e:
            logger.error(f"Failed to load portfolio: {e}")
            
        # We explicitly DO NOT sort solely by PnL. We sort by Priority (which prioritizes investigation), then Evidence Score
        priority_map = {
            ResearchPriority.BLOCKED: 0,
            ResearchPriority.LOW: 1,
            ResearchPriority.MEDIUM: 2,
            ResearchPriority.HIGH: 3,
            ResearchPriority.VERY_HIGH: 4
        }
        portfolio.sort(key=lambda x: (priority_map[x.priority], x.evidence_score.total_score), reverse=True)
        return portfolio

    def compare_candidates(self, identities: List[str]) -> CandidateComparisonMatrix:
        telemetry.record_stage("PAPER_CANDIDATE_COMPARISON_STARTED")
        candidates = []
        for identity in identities:
            snap = self.build_snapshot(identity)
            if snap: candidates.append(snap)
            
        if len(candidates) < 2:
            return CandidateComparisonMatrix(
                comparability=ComparabilityStatus.NOT_COMPARABLE,
                candidates=candidates,
                differences=["Insufficient valid candidates provided."],
                conclusion="Comparison failed."
            )
            
        differences = []
        
        # Check comparability (e.g. strategy mismatch)
        strategies = set(c.strategy for c in candidates)
        if len(strategies) > 1:
            differences.append(f"Strategy mismatch: {strategies}")
            
        if len(differences) > 0:
            status = ComparabilityStatus.LIMITED_COMPARABILITY
            conclusion = "Candidates differ in core strategic approach. Direct PnL comparison is invalid. Compare via Evidence Score."
        else:
            status = ComparabilityStatus.COMPARABLE
            conclusion = "Candidates share core strategic approach. Evidence profiles can be directly weighed."
            
        telemetry.record_stage("PAPER_CANDIDATE_COMPARISON_COMPLETED")
        return CandidateComparisonMatrix(
            comparability=status,
            candidates=sorted(candidates, key=lambda x: x.evidence_score.total_score, reverse=True),
            differences=differences,
            conclusion=conclusion
        )
