import multiprocessing
import traceback
import sys
import time
from typing import Dict, Any, List
from datetime import datetime

from app.core.models import MarketBar, TradingSignal
from app.sandbox.models import SandboxExecutionResult, ExperimentStatus

def _run_in_sandbox_process(code: str, entrypoint: str, bars: List[MarketBar], parameters: Dict[str, Any], result_queue: multiprocessing.Queue):
    """Executes the strategy inside a separate process."""
    try:
        # Create an isolated global dictionary
        # We only inject specific safe modules
        import math, statistics, numpy, pandas, datetime
        
        sandbox_globals = {
            "__builtins__": {
                "abs": abs, "all": all, "any": any, "bool": bool, "dict": dict, "float": float,
                "int": int, "len": len, "list": list, "max": max, "min": min, "pow": pow,
                "print": print, "range": range, "round": round, "set": set, "str": str,
                "sum": sum, "tuple": tuple, "zip": zip,
                "Exception": Exception, "ValueError": ValueError, "TypeError": TypeError,
                "KeyError": KeyError, "IndexError": IndexError,
                "__import__": __builtins__["__import__"]
            },
            "math": math,
            "statistics": statistics,
            "numpy": numpy,
            "np": numpy,
            "pandas": pandas,
            "pd": pandas,
            "datetime": datetime,
            "TradingSignal": TradingSignal
        }
        
        # Capture stdout
        import io
        captured_out = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured_out
        
        try:
            exec(code, sandbox_globals)
            
            if entrypoint not in sandbox_globals:
                raise ValueError(f"Entrypoint '{entrypoint}' not found in generated code.")
                
            func = sandbox_globals[entrypoint]
            
            # The contract is: func(bars, parameters) -> Optional[TradingSignal]
            start = time.perf_counter()
            # We run it just once for testing bounds
            signal = func(bars, parameters)
            elapsed = time.perf_counter() - start
            
            out = captured_out.getvalue()
            
            result_queue.put({
                "status": "SUCCESS",
                "stdout": out[:1000], # Bound output
                "runtime": elapsed,
                "is_safe": True
            })
            
        except Exception as e:
            out = captured_out.getvalue()
            err = traceback.format_exc()
            result_queue.put({
                "status": "ERROR",
                "stdout": out[:1000],
                "stderr": err[:1000],
                "is_safe": False
            })
        finally:
            sys.stdout = old_stdout
            
    except Exception as e:
        result_queue.put({
            "status": "FATAL",
            "stderr": str(e),
            "is_safe": False
        })

class SandboxExecutor:
    """Executes code with timeout in a restricted subprocess."""
    
    def __init__(self, timeout_seconds: int = 5):
        self.timeout_seconds = timeout_seconds
        
    def test_execution(self, code: str, entrypoint: str, bars: List[MarketBar], parameters: Dict[str, Any]) -> SandboxExecutionResult:
        queue = multiprocessing.Queue()
        p = multiprocessing.Process(target=_run_in_sandbox_process, args=(code, entrypoint, bars, parameters, queue))
        
        start_time = time.perf_counter()
        p.start()
        p.join(self.timeout_seconds)
        
        if p.is_alive():
            p.terminate()
            p.join()
            return SandboxExecutionResult(
                execution_id="test",
                proposal_id="",
                status=ExperimentStatus.TIMEOUT,
                stdout="",
                stderr="Execution timed out.",
                runtime_seconds=self.timeout_seconds,
                is_safe=False
            )
            
        runtime = time.perf_counter() - start_time
            
        if not queue.empty():
            res = queue.get()
            if res["status"] == "SUCCESS":
                return SandboxExecutionResult(
                    execution_id="test", proposal_id="",
                    status=ExperimentStatus.COMPLETED,
                    stdout=res.get("stdout", ""),
                    stderr="",
                    runtime_seconds=res.get("runtime", runtime),
                    is_safe=True
                )
            else:
                return SandboxExecutionResult(
                    execution_id="test", proposal_id="",
                    status=ExperimentStatus.FAILED,
                    stdout=res.get("stdout", ""),
                    stderr=res.get("stderr", ""),
                    runtime_seconds=runtime,
                    is_safe=False
                )
        else:
            return SandboxExecutionResult(
                execution_id="test", proposal_id="",
                status=ExperimentStatus.FAILED,
                stdout="",
                stderr="Process crashed without output.",
                runtime_seconds=runtime,
                is_safe=False
            )
