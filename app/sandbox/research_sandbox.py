import uuid
from typing import List, Dict, Any, Optional

from app.config import config
from app.sandbox.executor import SandboxExecutor
from app.sandbox.models import SandboxExecutionResult, ExperimentStatus
from app.core.models import MarketBar

class ControlledResearchSandbox:
    """Wrapper providing controlled AI research sandbox execution, safety barriers, and audit tracking."""

    PROTECTED_PATH_PATTERNS = ["app/", "app\\", "core/", "risk/", "strategies/", "config.py", "main.py"]
    FORBIDDEN_OPERATIONS = ["open(", "write(", "remove(", "unlink(", "rmdir(", "mkdir(", "os.system", "subprocess", "socket"]

    def __init__(self, executor: Optional[SandboxExecutor] = None):
        self.executor = executor or SandboxExecutor(timeout_seconds=5)
        self._human_approvals: Dict[str, bool] = {}

    def is_enabled(self) -> bool:
        return getattr(config, "AI_RESEARCH_SANDBOX_ENABLED", False)

    def validate_code_safety(self, code: str) -> tuple[bool, str]:
        """Ensures candidate code does not attempt to modify production or core trading files."""
        for pattern in self.FORBIDDEN_OPERATIONS:
            if pattern in code:
                return False, f"Forbidden operation detected: '{pattern}'"
        for path in self.PROTECTED_PATH_PATTERNS:
            if f"'{path}'" in code or f'"{path}"' in code:
                return False, f"Attempted access to protected core path: '{path}'"
        return True, ""

    def execute_candidate(
        self,
        proposal_id: str,
        code: str,
        entrypoint: str,
        bars: List[MarketBar],
        parameters: Optional[Dict[str, Any]] = None,
        timeout_seconds: Optional[int] = None
    ) -> SandboxExecutionResult:
        """Executes research code via isolated process executor with timeout and safety checks."""
        if not self.is_enabled():
            raise PermissionError("AI Research Sandbox is disabled in configuration (AI_RESEARCH_SANDBOX_ENABLED=False).")

        safe, err = self.validate_code_safety(code)
        if not safe:
            return SandboxExecutionResult(
                execution_id=str(uuid.uuid4()),
                proposal_id=proposal_id,
                status=ExperimentStatus.FAILED,
                stdout="",
                stderr=err,
                runtime_seconds=0.0,
                is_safe=False,
                provenance="CONTROLLED_RESEARCH_SANDBOX_BLOCKED_PROTECTED_FILES"
            )

        exec_instance = SandboxExecutor(timeout_seconds=timeout_seconds) if timeout_seconds else self.executor
        result = exec_instance.test_execution(code, entrypoint, bars, parameters or {})
        result.proposal_id = proposal_id
        result.provenance = "CONTROLLED_RESEARCH_SANDBOX_ISOLATED_EXECUTOR"
        return result

    def approve_candidate_for_research(self, proposal_id: str, human_approved: bool) -> bool:
        """Requires explicit human approval before a candidate is accepted outside research scope."""
        if not self.is_enabled():
            raise PermissionError("AI Research Sandbox is disabled in configuration.")

        if not human_approved:
            self._human_approvals[proposal_id] = False
            return False

        self._human_approvals[proposal_id] = True
        return True

    def is_candidate_approved(self, proposal_id: str) -> bool:
        return self._human_approvals.get(proposal_id, False)

    def execute_live(self) -> None:
        """Explicit safety barrier blocking live trade execution."""
        raise PermissionError("Research sandbox candidates are strictly forbidden from executing live trades or modifying core production files.")
