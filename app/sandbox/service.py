import uuid
import json
import logging
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any

from app.sandbox.models import ResearchCodeProposal, ResearchSandboxExperiment, ProposalStatus, ExperimentStatus
from app.sandbox.repository import SandboxRepository
from app.sandbox.analyzer import ASTSecurityValidator
from app.sandbox.executor import SandboxExecutor
from app.core.models import MarketBar, TradingSignal
from app.strategies.base import Strategy
from app.backtesting.engine import BacktestEngine
from app.strategies.ensemble import StrategyEnsemble
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

logger = logging.getLogger(__name__)

class AISandboxStrategyWrapper(Strategy):
    """Wraps dynamically evaluated AI code into the Strategy protocol for the BacktestEngine."""
    def __init__(self, name: str, code: str, entrypoint: str, parameters: Dict[str, Any]):
        self._name = name
        self.code = code
        self.entrypoint = entrypoint
        self.parameters = parameters
        
        self.sandbox_globals = {
            "math": __import__("math"),
            "statistics": __import__("statistics"),
            "numpy": __import__("numpy"),
            "pandas": __import__("pandas"),
            "TradingSignal": TradingSignal
        }
        # Inject standard builtins safely
        self.sandbox_globals["__builtins__"] = {k: __builtins__[k] for k in ["abs", "all", "any", "bool", "dict", "float", "int", "len", "list", "max", "min", "pow", "range", "round", "set", "str", "sum", "tuple", "zip", "__import__", "Exception", "ValueError"]}
        
        # Pre-compile
        exec(self.code, self.sandbox_globals)
        self.func = self.sandbox_globals[self.entrypoint]
        
    @property
    def name(self) -> str:
        return self._name
        
    def generate_signal(self, historical_bars: List[MarketBar]) -> Optional[TradingSignal]:
        try:
            return self.func(historical_bars, self.parameters)
        except Exception as e:
            logger.error(f"Sandbox strategy exception during backtest: {e}")
            return None
            
    def get_parameters(self) -> dict:
        return self.parameters

class SandboxService:
    def __init__(self):
        self.repo = SandboxRepository()
        self.validator = ASTSecurityValidator()
        self.executor = SandboxExecutor()
        
    def propose_code(self, identity: str, title: str, description: str, code: str, entrypoint: str = "research_strategy", model: str = "Copilot") -> ResearchCodeProposal:
        proposal = ResearchCodeProposal(
            proposal_id=str(uuid.uuid4()),
            research_identity=identity,
            title=title,
            description=description,
            code=code,
            entrypoint=entrypoint,
            model=model,
            status=ProposalStatus.VALIDATING
        )
        self.repo.save_proposal(proposal)
        return proposal
        
    def validate_proposal(self, proposal: ResearchCodeProposal, test_bars: List[MarketBar]) -> bool:
        # Step 1: AST
        is_safe, errors = self.validator.validate(proposal.code)
        if not is_safe:
            logger.warning(f"Proposal {proposal.proposal_id} failed AST: {errors}")
            proposal.status = ProposalStatus.AST_REJECTED
            proposal.assumptions = errors
            self.repo.save_proposal(proposal)
            return False
            
        # Step 2: Sandbox Exec Test
        res = self.executor.test_execution(proposal.code, proposal.entrypoint, test_bars, {})
        if res.status == ExperimentStatus.COMPLETED:
            proposal.status = ProposalStatus.SANDBOX_READY
            self.repo.save_proposal(proposal)
            return True
        else:
            proposal.status = ProposalStatus.REJECTED
            proposal.assumptions = [f"Execution Failed: {res.stderr}"]
            self.repo.save_proposal(proposal)
            return False

    def run_backtest(self, proposal: ResearchCodeProposal, dataset_identity: str, bars: List[MarketBar], parameters: Dict[str, Any]) -> ResearchSandboxExperiment:
        exp = ResearchSandboxExperiment(
            experiment_id=str(uuid.uuid4()),
            proposal_id=proposal.proposal_id,
            code_hash=proposal.get_code_hash(),
            dataset_identity=dataset_identity,
            parameters=parameters,
            seed=42,
            status=ExperimentStatus.RUNNING,
            started_at=datetime.utcnow()
        )
        self.repo.save_experiment(exp)
        
        if proposal.status not in {ProposalStatus.SANDBOX_READY, ProposalStatus.TESTED, ProposalStatus.BACKTESTED, ProposalStatus.APPROVED_FOR_RESEARCH}:
            exp.status = ExperimentStatus.FAILED
            exp.limitations = ["Proposal not ready for backtest."]
            exp.completed_at = datetime.utcnow()
            self.repo.save_experiment(exp)
            return exp
            
        try:
            strategy = AISandboxStrategyWrapper(f"Sandbox_{proposal.proposal_id}", proposal.code, proposal.entrypoint, parameters)
            ensemble = StrategyEnsemble([strategy])
            engine = BacktestEngine(ensemble, RiskEngine(PortfolioRiskLimits(initial_equity=10000.0)))
            
            result = engine.run(bars)
            
            exp.status = ExperimentStatus.COMPLETED
            exp.backtest_result_json = result.model_dump_json()
            exp.evidence = f"Historically observed total return: {result.total_return_pct:.2%}. Max drawdown: {result.max_drawdown_pct:.2%}"
            
            proposal.status = ProposalStatus.BACKTESTED
            self.repo.save_proposal(proposal)
            
        except Exception as e:
            exp.status = ExperimentStatus.FAILED
            exp.limitations = [str(e)]
            
        exp.completed_at = datetime.utcnow()
        self.repo.save_experiment(exp)
        return exp
        
    def approve_for_research(self, proposal_id: str):
        # NOTE: Approval means "APPROVED_FOR_RESEARCH". 
        # It DOES NOT mean deployment to live trading.
        proposals = self.repo.get_proposals()
        for p in proposals:
            if p.proposal_id == proposal_id:
                if p.status == ProposalStatus.BACKTESTED:
                    p.status = ProposalStatus.APPROVED_FOR_RESEARCH
                    self.repo.save_proposal(p)
                return
