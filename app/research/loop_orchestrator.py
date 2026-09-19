import logging
import uuid
import traceback
from datetime import datetime, timezone, timedelta
from typing import List, Optional

from app.research.loop_models import AIResearchRequest, ResearchRequestStatus
from app.research.ai_models import AIAnalysisResult, EvidenceType
from app.research.loop_mapper import HypothesisMapper
from app.research.loop_repository import ResearchLoopRepository
from app.database.schema import init_db
from app.diagnostics.telemetry import telemetry

from app.data.csv_provider import CsvHistoricalDataProvider
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits
from app.risk.portfolio import PortfolioRiskConfig
from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.research.models import ResearchExperiment
from app.research.evidence import ResearchEvidenceEvaluator, EvidenceConclusion

logger = logging.getLogger(__name__)

from app.research.opportunity_intelligence import OpportunityIntelligence
from app.research.memory_repository import ResearchMemoryRepository
from app.research.memory_models import OpportunityStatus, ResearchIdentity

class ResearchLoopOrchestrator:
    def __init__(self, data_dir: str = "data/historical"):
        self.repo = ResearchLoopRepository()
        self.memory_repo = ResearchMemoryRepository()
        self.intelligence = OpportunityIntelligence()
        self.data_dir = data_dir
        
    def process_new_hypotheses(self) -> int:
        """Finds newly generated AI hypotheses and maps them into Research Opportunities (Phase 14)."""
        try:
            with self.repo._get_conn() as conn:
                cursor = conn.cursor()
                # Find unmapped hypotheses (not in opportunities)
                cursor.execute("""
                    SELECT a.analysis_id, a.article_id, a.research_hypothesis, a.affected_symbols, a.evidence_type
                    FROM ai_research_analysis a
                    WHERE a.evidence_type = 'RESEARCH_HYPOTHESIS'
                    AND a.analysis_id NOT IN (SELECT source_analysis_id FROM research_opportunities)
                """)
                rows = cursor.fetchall()
                
                count = 0
                import json
                for row in rows:
                    class MockAnalysis:
                        analysis_id = row[0]
                        article_id = row[1]
                        research_hypothesis = row[2]
                        affected_symbols = json.loads(row[3]) if row[3] else []
                        evidence_type = EvidenceType(row[4])
                    
                    opp = self.intelligence.evaluate_analysis(MockAnalysis())
                    if opp:
                        count += 1
                return count
        except Exception as e:
            logger.error("Error creating research opportunities: %s", e)
            return 0
            
    def queue_opportunities_for_research(self, limit: int = 5) -> int:
        """Takes top READY_FOR_RESEARCH opportunities and converts them into concrete pending research requests."""
        opps = self.memory_repo.get_unresolved_opportunities(limit)
        count = 0
        for opp in opps:
            req = AIResearchRequest(
                request_id=str(uuid.uuid4()),
                analysis_id=opp.source_analysis_id,
                article_id="", # Hack since we don't strictly need it for the engine, or we could fetch it.
                hypothesis_text=opp.hypothesis_text,
                affected_symbols=opp.affected_symbols,
                mapped_strategy=opp.mapped_strategy
            )
            if self.repo.save_request(req):
                # Update opp status
                opp.status = OpportunityStatus.COMPLETED
                opp.reason = f"Queued for research as {req.request_id}"
                self.memory_repo.save_opportunity(opp)
                count += 1
        return count
        
    def execute_pending_requests(self, limit: int = 5) -> int:
        requests = self.repo.get_pending_requests(limit)
        count = 0
        
        for req in requests:
            logger.info("Executing research loop for request %s", req.request_id)
            telemetry.record_stage("RESEARCH_STARTED")
            
            try:
                self._execute_single_request(req)
                count += 1
            except Exception as e:
                telemetry.record_stage("RESEARCH_FAILED")
                logger.error("Failed to execute request %s: %s\n%s", req.request_id, e, traceback.format_exc())
                req.status = ResearchRequestStatus.EXECUTION_FAILED
                req.failure_reason = str(e)
                self.repo.save_request(req)
                
        return count
        
    def _execute_single_request(self, req: AIResearchRequest):
        # 1. Dataset Loading (Deterministic isolation)
        provider = CsvHistoricalDataProvider(self.data_dir)
        bars = []
        # We need a start_time for get_historical_bars, let's use a wide window
        start_time = datetime.utcnow() - timedelta(days=365)
        for sym in req.affected_symbols:
            try:
                sym_bars = provider.get_historical_bars(sym, "1d", start_time)
                bars.extend(sym_bars)
            except Exception:
                logger.warning("No data for symbol %s", sym)
                
        if not bars:
            req.status = ResearchRequestStatus.DATASET_UNAVAILABLE
            req.failure_reason = "No historical data found for affected symbols."
            self.repo.save_request(req)
            return
            
        bars.sort(key=lambda x: x.timestamp)
        
        # Enforce historical window logic simply (e.g. last N days of data)
        if req.historical_window_days and bars:
            end_time = bars[-1].timestamp
            start_time = end_time - timedelta(days=req.historical_window_days)
            bars = [b for b in bars if b.timestamp >= start_time]
            
        if len(bars) < 100: # Arbitrary minimum for backtest stability
            req.status = ResearchRequestStatus.INSUFFICIENT_RESEARCH_SPECIFICATION
            req.failure_reason = "Insufficient historical data depth after filtering."
            self.repo.save_request(req)
            return
            
        req.dataset_identity = {
            "source": self.data_dir,
            "start": bars[0].timestamp.isoformat(),
            "end": bars[-1].timestamp.isoformat(),
            "row_count": len(bars)
        }
        
        # 2. Engine Setup
        from app.strategies.factory import get_strategy
        strategy = get_strategy(req.mapped_strategy)
        if not strategy:
            req.status = ResearchRequestStatus.INSUFFICIENT_RESEARCH_SPECIFICATION
            req.failure_reason = f"Mapped strategy {req.mapped_strategy} is invalid."
            self.repo.save_request(req)
            return
            
        ensemble = StrategyEnsemble([strategy])
        risk_engine = RiskEngine(PortfolioRiskLimits())
        cost_config = CostConfig(commission_rate=0.001, slippage_rate=0.0005)
        
        engine = BacktestEngine(
            ensemble=ensemble,
            risk_engine=risk_engine,
            initial_capital=10000.0,
            cost_config=cost_config
        )
        
        # 3. Execution (Chronological)
        result = engine.run(bars)
        
        from app.analytics.engine import generate_analytics_report
        analytics_report = generate_analytics_report(req.request_id, result)
        
        # 5. Experiment / Evidence Wrapping
        experiment = ResearchExperiment(
            experiment_id=str(uuid.uuid4()),
            experiment_name=f"AI Request: {req.request_id}",
            dataset_id="local_csv",
            dataset_identity=req.dataset_identity,
            symbols=req.affected_symbols,
            timeframe="1d",
            strategy=req.mapped_strategy,
            configuration="default",
            starting_capital=10000.0,
            random_seed=req.random_seed,
            created_at=datetime.utcnow(),
            status="COMPLETED",
            validation_results=[],
            out_of_sample_report=analytics_report
        )
        
        # 6. Evaluate Evidence
        telemetry.record_stage("EVIDENCE_EVALUATED")
        summary = ResearchEvidenceEvaluator.evaluate(experiment)
        
        req.experiment_id = experiment.experiment_id
        req.evidence_conclusion = summary.conclusion
        req.status = ResearchRequestStatus.COMPLETED
        telemetry.record_stage("RESEARCH_COMPLETED")
        self.repo.save_request(req)
        
        # 7. Update Memory
        identity = ResearchIdentity.generate(req.mapped_strategy, req.affected_symbols, req.hypothesis_text)
        mem = self.memory_repo.get_memory(identity.identity_hash)
        if mem:
            mem.last_researched_at = datetime.utcnow()
            mem.latest_experiment_id = req.experiment_id
            mem.latest_conclusion = summary.conclusion.value
            self.memory_repo.save_memory(mem)
            telemetry.record_stage("MEMORY_UPDATED")
