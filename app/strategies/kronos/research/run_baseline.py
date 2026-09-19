import os
import logging
import pandas as pd
import numpy as np
import json

from app.core.models import MarketBar
from app.strategies.kronos.engine import KronosEngineWrapper
from app.strategies.kronos.config import kronos_config
from app.strategies.kronos.analytics import calculate_correlations, calculate_mae, calculate_rmse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def evaluate_baseline(bars, max_points: int = 400):
    """Evaluates the frozen original Kronos baseline."""
    engine = KronosEngineWrapper()
    
    start_point = kronos_config.lookback
    test_points = list(range(start_point, len(bars) - kronos_config.prediction_horizon))
    test_points = test_points[-max_points:] 
    
    # Chronological Split logic (same as ablation: Train 50%, Valid 25%, Test 25%)
    n = len(test_points)
    train_end = int(n * 0.5)
    valid_end = train_end + int(n * 0.25)
    
    oos_points = test_points[valid_end:]
    
    logger.info(f"Evaluating Baseline OOS on {len(oos_points)} points...")
    
    preds = []
    actuals = []
    
    for point in oos_points:
        x_input = bars[point - kronos_config.lookback : point]
        future = bars[point : point + kronos_config.prediction_horizon]
        
        current_close = x_input[-1].close
        actual_close = future[-1].close
        
        predicted_return = engine.predict(x_input, pred_len=kronos_config.prediction_horizon)
        actual_return = ((actual_close - current_close) / current_close) * 100.0
        
        preds.append(predicted_return)
        actuals.append(actual_return)
        
    preds = np.array(preds)
    actuals = np.array(actuals)
    
    mae = calculate_mae(preds, actuals)
    rmse = calculate_rmse(preds, actuals)
    pearson, spearman = calculate_correlations(pd.Series(preds), pd.Series(actuals))
    dir_acc = np.mean(np.sign(preds) == np.sign(actuals)) * 100.0
    
    result = {
        "Experiment": "Baseline_Frozen",
        "MAE": mae,
        "RMSE": rmse,
        "Pearson": pearson,
        "Spearman": spearman,
        "Dir_Acc": dir_acc
    }
    
    print("\n===== BASELINE RESULTS (OOS) =====")
    print(result)
    
    os.makedirs("app/strategies/kronos/research", exist_ok=True)
    
    results_path = "app/strategies/kronos/research/results.csv"
    if os.path.exists(results_path):
        df = pd.read_csv(results_path)
        df = pd.concat([df, pd.DataFrame([result])], ignore_index=True)
    else:
        df = pd.DataFrame([result])
    df.to_csv(results_path, index=False)
    
    # Save manifest
    manifest = {
        "Experiment": "Baseline_Frozen",
        "Dataset": r"D:\Kronos\finetune_csv\data\HK_ali_09988_kline_5min_all.csv",
        "OOS_Points": len(oos_points),
        "Lookback": kronos_config.lookback,
        "Horizon": kronos_config.prediction_horizon
    }
    with open("app/strategies/kronos/research/experiment_manifest.json", "w") as f:
        json.dump([manifest], f, indent=4)
        
if __name__ == "__main__":
    bars = []
    kronos_data = r"D:\Kronos\finetune_csv\data\HK_ali_09988_kline_5min_all.csv"
    df = pd.read_csv(kronos_data)
    df["timestamp"] = pd.to_datetime(df.get("timestamps", df.get("timestamp")))
    df = df.sort_values("timestamp").reset_index(drop=True)
    for _, row in df.iterrows():
        bars.append(MarketBar(
            symbol="HK_09988", timestamp=row["timestamp"], open=row["open"],
            high=row["high"], low=row["low"], close=row["close"], volume=row["volume"]
        ))
    evaluate_baseline(bars)
