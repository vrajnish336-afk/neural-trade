from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum
import hashlib

class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    VALIDATING = "VALIDATING"
    AST_REJECTED = "AST_REJECTED"
    SANDBOX_READY = "SANDBOX_READY"
    TESTED = "TESTED"
    BACKTESTED = "BACKTESTED"
    REJECTED = "REJECTED"
    APPROVED_FOR_RESEARCH = "APPROVED_FOR_RESEARCH"

class ExperimentStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"

class ResearchCodeProposal(BaseModel):
    proposal_id: str
    research_identity: str
    title: str
    description: str
    code: str
    entrypoint: str = "research_strategy"
    language: str = "python"
    requested_inputs: List[str] = Field(default_factory=lambda: ["historical_bars", "parameters"])
    expected_outputs: str = "TradingSignal"
    dependencies: List[str] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    model: str
    status: ProposalStatus = ProposalStatus.DRAFT
    
    def get_code_hash(self) -> str:
        return hashlib.sha256(self.code.encode('utf-8')).hexdigest()

class SandboxExecutionResult(BaseModel):
    execution_id: str
    proposal_id: str
    status: ExperimentStatus
    stdout: str
    stderr: str
    runtime_seconds: float
    is_safe: bool
    metrics: Dict[str, Any] = Field(default_factory=dict)
    provenance: str = "LIMITED_RESEARCH_EXECUTION_ENVIRONMENT"

class ResearchSandboxExperiment(BaseModel):
    experiment_id: str
    proposal_id: str
    code_hash: str
    dataset_identity: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    seed: int = 42
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    status: ExperimentStatus = ExperimentStatus.PENDING
    backtest_result_json: Optional[str] = None
    evidence: str = ""
    limitations: List[str] = Field(default_factory=list)
