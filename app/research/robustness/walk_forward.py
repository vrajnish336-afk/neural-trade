import uuid
import logging
from typing import Callable, List, Optional, Dict, Any
from app.backtesting.engine import BacktestEngine
from app.core.models import MarketBar
from app.research.models import ResearchExperiment
from app.research.robustness.models import WalkForwardWindowResult
from app.research.robustness.artifact import (
    FoldBoundary, FoldEvidenceMetrics, AggregateEvidenceMetrics,
    WalkForwardEvidenceArtifact, build_evidence_artifact,
    save_evidence_artifact, compute_dataset_fingerprint,
    get_current_code_revision
)

logger = logging.getLogger(__name__)

class WalkForwardResultSet(list):
    """
    List of WalkForwardWindowResult items that also holds evidence artifact metadata.
    Subclasses list so all existing list consumers, indexers, and iterators work unchanged.
    """
    def __init__(
        self,
        items: Optional[List[WalkForwardWindowResult]] = None,
        artifact: Optional[WalkForwardEvidenceArtifact] = None,
        persistence_success: bool = False,
        persistence_failed: bool = False,
        persistence_error: Optional[str] = None
    ):
        super().__init__(items or [])
        self.artifact = artifact
        self.persistence_success = persistence_success
        self.persistence_failed = persistence_failed
        self.persistence_error = persistence_error

def run_walk_forward_robustness(
    bars: List[MarketBar],
    engine_factory: Callable[[], BacktestEngine],
    window_size: int = 500,
    step_size: int = 250,
    candidate_id: Optional[str] = None,
    strategy_name: Optional[str] = None,
    parameters: Optional[Dict[str, Any]] = None,
    config_snapshot: Optional[Dict[str, Any]] = None,
    auto_persist: bool = True,
    db_path: Optional[str] = None,
    json_path: Optional[str] = None
) -> WalkForwardResultSet:
    results = []
    folds_evidence: List[FoldEvidenceMetrics] = []
    total_bars = len(bars)
    start_idx = 0
    window_id = 1
    
    while start_idx + window_size <= total_bars:
        window_bars = bars[start_idx : start_idx + window_size]
        
        train_end_idx = int(window_size * 0.5)
        val_end_idx = int(window_size * 0.75)
        
        train_bars = window_bars[:train_end_idx]
        val_bars = window_bars[train_end_idx:val_end_idx]
        test_bars = window_bars[val_end_idx:]
        
        test_start = str(test_bars[0].timestamp)
        test_end = str(test_bars[-1].timestamp)
        
        # Enforce strict isolation: no state leakage between train/val/test
        engine_train = engine_factory()
        engine_train.run(train_bars)
        
        engine_val = engine_factory()
        engine_val.run(val_bars)
        
        engine_test = engine_factory()
        res = engine_test.run(test_bars)
        
        oos_trades = res.trades
        trades_count = res.number_of_trades
        wins_count = res.winning_trades
        losses_count = res.losing_trades
        entry_costs = sum(getattr(t, "entry_cost", 0.0) for t in oos_trades)
        exit_costs = sum(getattr(t, "exit_cost", 0.0) for t in oos_trades)
        slippage_costs = sum(getattr(t, "slippage_cost", 0.0) for t in oos_trades)
        total_costs = entry_costs + exit_costs + slippage_costs
        expectancy = (res.net_profit / trades_count) if trades_count > 0 else 0.0
        
        boundaries = FoldBoundary(
            train_start=str(train_bars[0].timestamp),
            train_end=str(train_bars[-1].timestamp),
            validation_start=str(val_bars[0].timestamp),
            validation_end=str(val_bars[-1].timestamp),
            test_start=test_start,
            test_end=test_end
        )
        fold_evidence = FoldEvidenceMetrics(
            window_id=window_id,
            boundaries=boundaries,
            trades=trades_count,
            wins=wins_count,
            losses=losses_count,
            profit_factor=res.profit_factor,
            expectancy=expectancy,
            max_drawdown_pct=res.max_drawdown_pct,
            gross_profit=res.gross_profit,
            gross_loss=res.gross_loss,
            net_pnl=res.net_profit,
            entry_costs=entry_costs,
            exit_costs=exit_costs,
            slippage_costs=slippage_costs,
            total_costs=total_costs
        )
        folds_evidence.append(fold_evidence)
        
        results.append(WalkForwardWindowResult(
            window_id=window_id,
            train_start=str(train_bars[0].timestamp),
            train_end=str(train_bars[-1].timestamp),
            validation_start=str(val_bars[0].timestamp),
            validation_end=test_start,
            test_start=test_start,
            test_end=test_end,
            strategy=strategy_name or 'Adaptive',
            adaptive_state='Varies',
            strategy_weights={},
            trades=len(oos_trades),
            return_pct=res.total_return_pct,
            win_rate=res.win_rate / 100.0 if res.number_of_trades > 0 else 0.0,
            profit_factor=res.profit_factor,
            gross_profit=res.gross_profit,
            gross_loss=res.gross_loss,
            max_drawdown_pct=res.max_drawdown_pct
        ))
        start_idx += step_size
        window_id += 1

    if not folds_evidence:
        return WalkForwardResultSet(
            items=[],
            artifact=None,
            persistence_success=False,
            persistence_failed=False,
            persistence_error="Missing data: No completed folds formed."
        )

    # Compute aggregate metrics with exact reconciliation
    agg_trades = sum(f.trades for f in folds_evidence)
    agg_wins = sum(f.wins for f in folds_evidence)
    agg_losses = sum(f.losses for f in folds_evidence)
    agg_gross_profit = sum(f.gross_profit for f in folds_evidence)
    agg_gross_loss = sum(f.gross_loss for f in folds_evidence)
    agg_net_pnl = sum(f.net_pnl for f in folds_evidence)
    agg_total_costs = sum(f.total_costs for f in folds_evidence)
    
    if agg_gross_loss > 0:
        agg_pf = agg_gross_profit / agg_gross_loss
    elif agg_gross_profit > 0:
        agg_pf = float('inf')
    else:
        agg_pf = 0.0
        
    agg_exp = (agg_net_pnl / agg_trades) if agg_trades > 0 else 0.0
    agg_dd = max((f.max_drawdown_pct for f in folds_evidence), default=0.0)

    aggregate = AggregateEvidenceMetrics(
        total_trades=agg_trades,
        wins=agg_wins,
        losses=agg_losses,
        profit_factor=agg_pf,
        expectancy=agg_exp,
        max_drawdown_pct=agg_dd,
        gross_profit=agg_gross_profit,
        gross_loss=agg_gross_loss,
        net_pnl=agg_net_pnl,
        total_costs=agg_total_costs
    )

    dataset_fp = compute_dataset_fingerprint(bars)
    code_rev = get_current_code_revision()
    
    cand_id = candidate_id or f"cand_wf_{uuid.uuid4().hex[:8]}"
    strat_name = strategy_name or "Adaptive"
    params = parameters or {}
    cfg_snap = config_snapshot or {}

    artifact = build_evidence_artifact(
        candidate_id=cand_id,
        strategy_name=strat_name,
        parameters=params,
        config_snapshot=cfg_snap,
        dataset_fingerprint=dataset_fp,
        folds=folds_evidence,
        aggregate=aggregate,
        code_revision=code_rev
    )

    p_success = False
    p_failed = False
    p_error = None

    if auto_persist:
        try:
            save_evidence_artifact(artifact, db_path=db_path, json_path=json_path)
            p_success = True
        except Exception as e:
            p_success = False
            p_failed = True
            p_error = str(e)
            logger.error("Failed to persist walk-forward evidence artifact: %s", e)

    return WalkForwardResultSet(
        items=results,
        artifact=artifact,
        persistence_success=p_success,
        persistence_failed=p_failed,
        persistence_error=p_error
    )

def attach_evidence_to_experiment(
    experiment: ResearchExperiment,
    result_set: WalkForwardResultSet
) -> ResearchExperiment:
    """
    Attaches walk-forward evidence artifact and persistence status to a ResearchExperiment.
    """
    experiment.walk_forward_artifact = result_set.artifact
    if result_set.artifact:
        experiment.artifact_id = result_set.artifact.artifact_id
    experiment.persistence_failed = result_set.persistence_failed
    return experiment
