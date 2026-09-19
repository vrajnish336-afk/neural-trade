import uuid
import logging
from typing import List, Optional
from app.research.ai_models import AIAnalysisResult, EvidenceType
from app.research.loop_models import AIResearchRequest, ResearchRequestStatus
from app.diagnostics.telemetry import telemetry

logger = logging.getLogger(__name__)

# Allowed strategies to ensure AI cannot execute arbitrary code
ALLOWED_STRATEGIES = ["TrendFollowing", "MeanReversion", "VolatilityBreakout"]
ALLOWED_SYMBOLS = ["BTC/USD", "ETH/USD", "SOL/USD", "AAPL", "MSFT"]

class HypothesisMapper:
    """
    Safely translates an AI research hypothesis into deterministic execution parameters.
    Prevents arbitrary code execution and bounds inputs to known valid sets.
    """
    
    @staticmethod
    def map_to_request(analysis: AIAnalysisResult) -> AIResearchRequest:
        telemetry.record_stage("RESEARCH_REQUEST_CREATED")
        
        request = AIResearchRequest(
            request_id=str(uuid.uuid4()),
            analysis_id=analysis.analysis_id,
            article_id=analysis.article_id,
            hypothesis_text=analysis.research_hypothesis or "",
            affected_symbols=[]
        )
        
        # 1. Validate basic preconditions
        if not analysis.research_hypothesis or analysis.evidence_type != EvidenceType.RESEARCH_HYPOTHESIS:
            telemetry.record_stage("RESEARCH_REJECTED_NOT_HYPOTHESIS")
            request.status = ResearchRequestStatus.INSUFFICIENT_RESEARCH_SPECIFICATION
            request.failure_reason = "No valid hypothesis provided by AI."
            return request
            
        # 2. Validate symbols
        valid_symbols = [s for s in analysis.affected_symbols if s in ALLOWED_SYMBOLS]
        if not valid_symbols:
            telemetry.record_stage("RESEARCH_REJECTED_UNSUPPORTED_SYMBOL")
            request.status = ResearchRequestStatus.INSUFFICIENT_RESEARCH_SPECIFICATION
            request.failure_reason = f"No supported symbols found. AI provided: {analysis.affected_symbols}"
            return request
            
        request.affected_symbols = valid_symbols
        
        # 3. Deterministic Strategy Mapping
        # We perform keyword-based heuristic mapping on the AI's hypothesis text to pick a safe, pre-approved strategy.
        # This isolates the AI text completely from Python/executable evaluation.
        hyp_lower = request.hypothesis_text.lower()
        
        if "volatility" in hyp_lower or "breakout" in hyp_lower:
            request.mapped_strategy = "VolatilityBreakout"
        elif "revert" in hyp_lower or "mean" in hyp_lower or "overbought" in hyp_lower or "oversold" in hyp_lower:
            request.mapped_strategy = "MeanReversion"
        else:
            # Default fallback for general directional sentiment or unknown hypotheses
            request.mapped_strategy = "TrendFollowing"
            
        telemetry.record_stage("HYPOTHESIS_VALIDATED")
        return request
