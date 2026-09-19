import uuid
from datetime import datetime
from typing import List, Optional

from app.research.ai_models import AIAnalysisResult
from app.research.loop_mapper import HypothesisMapper
from app.research.memory_models import ResearchIdentity, ResearchMemoryRecord, ResearchOpportunity, OpportunityStatus
from app.research.memory_repository import ResearchMemoryRepository
from app.diagnostics.telemetry import telemetry

class OpportunityIntelligence:
    """
    Evaluates AI hypotheses to determine their research value (Opportunity Score).
    This strictly evaluates research usefulness, NOT expected profitability.
    """
    
    def __init__(self):
        self.repo = ResearchMemoryRepository()
        
    def evaluate_analysis(self, analysis: AIAnalysisResult) -> Optional[ResearchOpportunity]:
        # 1. Base mapping to get structured fields
        temp_req = HypothesisMapper.map_to_request(analysis)
        if temp_req.status.value == "INSUFFICIENT_RESEARCH_SPECIFICATION":
            telemetry.record_stage("OPPORTUNITY_SKIPPED")
            return None
            
        # 2. Determine canonical identity
        identity = ResearchIdentity.generate(
            strategy=temp_req.mapped_strategy,
            symbols=temp_req.affected_symbols,
            text=analysis.research_hypothesis
        )
        
        telemetry.record_stage("MEMORY_LOOKUP")
        existing_memory = self.repo.get_memory(identity.identity_hash)
        
        # 3. Opportunity Scoring
        novelty_score = 1.0 if not existing_memory else 0.0
        
        # Evidence gap: If previously researched, how strong was the conclusion?
        evidence_gap_score = 1.0
        duplicate_penalty = 0.0
        status = OpportunityStatus.NEW
        reason = "Novel hypothesis identified."
        
        if existing_memory:
            telemetry.record_stage("DUPLICATE_DETECTED")
            telemetry.record_stage("HISTORY_FOUND")
            conclusion = existing_memory.latest_conclusion
            
            if conclusion == "VERIFIED_ROBUST":
                evidence_gap_score = 0.0
                duplicate_penalty = 1.0
                status = OpportunityStatus.ALREADY_RESEARCHED
                reason = "Already verified."
            elif conclusion in ["INSUFFICIENT_DATA", "WEAK_EVIDENCE"]:
                evidence_gap_score = 0.8
                duplicate_penalty = 0.2
                status = OpportunityStatus.NEEDS_VALIDATION
                reason = "Previous evidence was weak or insufficient; warrants re-test if new data exists."
            elif conclusion == "FAILED_ROBUSTNESS":
                evidence_gap_score = 0.2 # We know it failed, less value in re-testing immediately
                duplicate_penalty = 0.8
                status = OpportunityStatus.ALREADY_RESEARCHED
                reason = "Previously failed robustness."
            else:
                # E.g. never actually ran
                evidence_gap_score = 1.0
                duplicate_penalty = 0.1
                status = OpportunityStatus.NEEDS_VALIDATION
                reason = "Hypothesis seen before but no conclusive research run found."
                
        # Data availability is a simple heuristic: do we have the symbols? (Mapper already filtered them)
        data_availability_score = 1.0 if temp_req.affected_symbols else 0.0
        
        # 4. Calculate Priority
        # Priority = (Novelty + EvidenceGap + DataAvail) / 3 - Penalty
        priority = ((novelty_score + evidence_gap_score + data_availability_score) / 3.0) - duplicate_penalty
        priority = max(0.0, min(1.0, priority)) # clamp 0-1
        
        if priority > 0.6 and status not in [OpportunityStatus.ALREADY_RESEARCHED, OpportunityStatus.DUPLICATE]:
            status = OpportunityStatus.READY_FOR_RESEARCH
            
        opp = ResearchOpportunity(
            opportunity_id=str(uuid.uuid4()),
            source_analysis_id=analysis.analysis_id,
            identity_hash=identity.identity_hash,
            hypothesis_text=analysis.research_hypothesis,
            affected_symbols=temp_req.affected_symbols,
            mapped_strategy=temp_req.mapped_strategy,
            novelty_score=novelty_score,
            evidence_gap_score=evidence_gap_score,
            data_availability_score=data_availability_score,
            duplicate_penalty=duplicate_penalty,
            research_priority=priority,
            status=status,
            reason=reason
        )
        
        # 5. Persist
        self.repo.save_opportunity(opp)
        telemetry.record_stage("OPPORTUNITY_CREATED")
        
        # 6. Update Memory (First seen)
        if not existing_memory:
            mem = ResearchMemoryRecord(
                identity_hash=identity.identity_hash,
                canonical_hypothesis=analysis.research_hypothesis,
                affected_symbols=temp_req.affected_symbols,
                mapped_strategy=temp_req.mapped_strategy,
                first_seen_at=datetime.utcnow()
            )
            self.repo.save_memory(mem)
            telemetry.record_stage("MEMORY_UPDATED")
            
        return opp
