import uuid
from typing import List, Callable, Any, Dict
from datetime import datetime, timezone
from app.research.models import ResearchExperiment, WalkForwardResult
from app.research.dataset import generate_synthetic_data
from app.research.validation import validate_dataset
from app.research.splits import split_research_windows
from app.research.stress import run_stress_test
from app.analytics.engine import generate_analytics_report
from app.backtesting.models import CostConfig
from app.research.registry import ExperimentRegistry, generate_dataset_identity

def run_governed_experiment(
    experiment_name: str,
    symbols: List[str],
    seed: int,
    engine_factory: Callable[[CostConfig], Any],
    base_cost: CostConfig,
    strategy_name: str,
    config_snapshot: Dict[str, Any] = None,
    lineage: Any = None
) -> ResearchExperiment:
    registry = ExperimentRegistry()
    experiment_id = str(uuid.uuid4())
    
    # Generate Dataset
    datasets = generate_synthetic_data(symbols=symbols, num_bars=2000, seed=seed)
    
    # Dataset Identity
    primary_sym = symbols[0]
    primary_bars = datasets[primary_sym]
    dataset_id = generate_dataset_identity(primary_bars, primary_sym, "1h")
    
    # Validate
    validations = []
    for sym, bars in datasets.items():
        validations.append(validate_dataset(bars, sym))
        
    exp = ResearchExperiment(
        experiment_id=experiment_id,
        experiment_name=experiment_name,
        experiment_type="BACKTEST",
        dataset_id=dataset_id.get("hash", f"synth_{seed}"),
        dataset_identity=dataset_id,
        symbols=symbols,
        timeframe="1h",
        strategy=strategy_name,
        configuration="snapshot",
        configuration_snapshot=config_snapshot or {},
        starting_capital=10000.0,
        random_seed=seed,
        seeds={"synthetic_data_seed": seed, "system_seed": seed},
        lineage=lineage,
        created_at=datetime.now(timezone.utc),
        status="RUNNING",
        validation_results=validations
    )
    registry.save_experiment(exp)
    
    if not all(v.is_valid for v in validations):
        exp.status = "FAILED_VALIDATION"
        exp.classification = "INVALID"
        registry.save_experiment(exp)
        return exp
        
    try:
        # Out-Of-Sample Validation
        train_bars, val_bars, test_bars, train_s, val_s, test_s = split_research_windows(primary_bars)
        
        engine = engine_factory(base_cost)
        oos_result = engine.run(test_bars)
        exp.out_of_sample_report = generate_analytics_report(experiment_id + "_oos", oos_result)
        
        # Stress Testing
        stress_res = run_stress_test(
            engine_factory, test_bars, base_cost, "High Transaction Costs", stress_multiplier=3.0
        )
        exp.stress_test_results.append(stress_res)
        
        # Walk-Forward
        engine_train = engine_factory(base_cost)
        train_result = engine_train.run(train_bars)
        
        engine_val = engine_factory(base_cost)
        val_result = engine_val.run(val_bars)
        
        wf = WalkForwardResult(
            window_id="wf_1",
            train_split=train_s, validation_split=val_s, test_split=test_s,
            train_report=generate_analytics_report(experiment_id + "_wf_train", train_result),
            validation_report=generate_analytics_report(experiment_id + "_wf_val", val_result),
            test_report=exp.out_of_sample_report
        )
        exp.walk_forward_results.append(wf)
        
        exp.status = "COMPLETED"
        registry.save_experiment(exp)
        return exp
    except Exception as e:
        exp.status = "FAILED"
        exp.notes = f"Exception: {str(e)}"
        registry.save_experiment(exp)
        raise

def run_reproducibility_check(
    symbols: List[str],
    seed: int,
    engine_factory: Callable[[CostConfig], Any],
    base_cost: CostConfig,
    strategy_name: str,
    config_snapshot: Dict[str, Any]
) -> Dict[str, Any]:
    """Runs the experiment twice and ensures outputs match deterministically."""
    exp1 = run_governed_experiment(
        "Repro Run 1", symbols, seed, engine_factory, base_cost, strategy_name, config_snapshot
    )
    exp2 = run_governed_experiment(
        "Repro Run 2", symbols, seed, engine_factory, base_cost, strategy_name, config_snapshot
    )
    
    # Compare
    from app.research.registry import compare_experiments
    diff = compare_experiments(exp1, exp2)
    
    is_reproducible = True
    mismatches = []
    
    if diff["metrics_exp1"] != diff["metrics_exp2"]:
        is_reproducible = False
        mismatches.append("metrics_mismatch")
        
    return {
        "exp1_id": exp1.experiment_id,
        "exp2_id": exp2.experiment_id,
        "is_reproducible": is_reproducible,
        "mismatches": mismatches,
        "comparison": diff
    }

