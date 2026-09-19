import os
import argparse
import logging
import pandas as pd
import numpy as np

from app.core.models import MarketBar
from app.strategies.kronos.engine import KronosEngineWrapper
from app.strategies.kronos.config import kronos_config
from app.strategies.kronos.features import build_feature_set
from app.strategies.kronos.training import KronosContextModeler
from app.strategies.kronos.analytics import calculate_correlations, calculate_mae, calculate_rmse

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def generate_kronos_predictions_cache(bars, cache_path: str, max_points: int = 1500, step: int = 5):
    """Generates and caches Kronos baseline predictions to avoid redundant inference."""
    if os.path.exists(cache_path):
        logger.info(f"Loaded cached predictions from {cache_path}")
        return pd.read_csv(cache_path)
        
    engine = KronosEngineWrapper()
    predictions = []
    
    start_point = kronos_config.lookback
    test_points = list(range(start_point, len(bars) - kronos_config.prediction_horizon, step))
    test_points = test_points[-max_points:] # Cap to avoid extremely long runtimes
    
    logger.info(f"Generating Kronos predictions for {len(test_points)} points...")
    
    for count, point in enumerate(test_points, 1):
        x_input = bars[point - kronos_config.lookback : point]
        future = bars[point : point + kronos_config.prediction_horizon]
        
        current_close = x_input[-1].close
        actual_close = future[-1].close
        
        try:
            predicted_return = engine.predict(x_input, pred_len=kronos_config.prediction_horizon)
            actual_return = ((actual_close - current_close) / current_close) * 100.0
            
            predictions.append({
                "index": point, # Used to align with feature dataframe
                "kronos_pred": predicted_return,
                "target": actual_return
            })
        except Exception as e:
            logger.error(f"Error at point {point}: {e}")
            
    df = pd.DataFrame(predictions)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    df.to_csv(cache_path, index=False)
    return df

def run_ablation_study():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default=r"D:\Kronos\finetune_csv\data\HK_ali_09988_kline_5min_all.csv")
    args = parser.parse_args()
    
    # 1. Load Data
    bars = []
    if os.path.exists(args.data):
        df = pd.read_csv(args.data)
        if "timestamp" in df.columns or "timestamps" in df.columns:
            df["timestamp"] = pd.to_datetime(df.get("timestamps", df.get("timestamp")))
            df = df.sort_values("timestamp").reset_index(drop=True)
            for _, row in df.iterrows():
                bars.append(MarketBar(
                    symbol="TEST", timestamp=row["timestamp"], open=row["open"],
                    high=row["high"], low=row["low"], close=row["close"], volume=row.get("volume", 1000)
                ))
    if not bars:
        kronos_data = r"D:\Kronos\finetune_csv\data\HK_ali_09988_kline_5min_all.csv"
        df = pd.read_csv(kronos_data)
        df["timestamp"] = pd.to_datetime(df.get("timestamps", df.get("timestamp")))
        df = df.sort_values("timestamp").reset_index(drop=True)
        for _, row in df.iterrows():
            bars.append(MarketBar(
                symbol="HK_09988", timestamp=row["timestamp"], open=row["open"],
                high=row["high"], low=row["low"], close=row["close"], volume=row["volume"]
            ))
            
    # 2. Extract DataFrame for feature engineering
    df_raw = pd.DataFrame([{
        "open": b.open, "high": b.high, "low": b.low, "close": b.close, "volume": b.volume
    } for b in bars])
    
    # 3. Generate baseline predictions
    cache_path = "app/strategies/kronos/experiments/kronos_preds_cache.csv"
    pred_df = generate_kronos_predictions_cache(bars, cache_path, max_points=400, step=1)
    
    # 4. Compute Features
    logger.info("Computing engineered features...")
    features_df = build_feature_set(df_raw)
    
    # CRITICAL LEAKAGE FIX: 
    # pred_df["index"] points to the target candle index. 
    # x_input ended at index - 1. We must strictly use features up to index - 1.
    pred_df["feature_index"] = pred_df["index"] - 1
    
    # Align features with predictions using the correct historical index
    aligned = pd.merge(pred_df, features_df, left_on="feature_index", right_index=True, how="inner")
    
    # Drop the temporary column
    aligned.drop(columns=["feature_index"], inplace=True)
    
    # 5. Define Feature Groups
    feature_groups = {
        "Baseline": ["kronos_pred"],
        "Price_Return": ["kronos_pred", "ret_1", "ret_3", "ret_5", "ret_10", "ret_20", "roll_vol_20"],
        "Trend": ["kronos_pred", "dist_sma_10", "dist_sma_20", "sma_10_20_cross", "trend_slope_10"],
        "Momentum": ["kronos_pred", "rsi_14", "roc_10", "macd_hist"],
        "Volatility": ["kronos_pred", "hl_range_pct", "roll_hl_range_10"],
        "Volume": ["kronos_pred", "vol_change_1", "vol_zscore_20"],
        "Structure": ["kronos_pred", "body_range_ratio", "upper_wick_ratio", "lower_wick_ratio", "dist_roll_high", "dist_roll_low"]
    }
    
    # Also an "All" group
    all_feats = ["kronos_pred"] + [col for col in features_df.columns if col not in ["kronos_pred", "target", "index"]]
    feature_groups["All_Features"] = all_feats
    
    # 6. Chronological split
    modeler = KronosContextModeler(alpha=10.0)
    train_df, valid_df, test_df = modeler.split_chronological(aligned, train_ratio=0.5, valid_ratio=0.25)
    
    logger.info(f"Split sizes | Train: {len(train_df)}, Valid: {len(valid_df)}, Test (OOS): {len(test_df)}")
    
    # 7. Ablation Loop
    results = []
    
    for group_name, cols in feature_groups.items():
        # Train
        modeler.fit(train_df, cols)
        
        # We tune/validate on Valid, but for this ablation we just evaluate on Test directly
        # to show the impact. In a real scenario, we'd pick the best group on Valid, then test on Test.
        valid_preds = modeler.predict(valid_df, cols)
        test_preds = modeler.predict(test_df, cols)
        
        test_actuals = test_df['target'].values
        
        # Metrics on OOS
        mae = calculate_mae(test_preds, test_actuals)
        rmse = calculate_rmse(test_preds, test_actuals)
        pearson, spearman = calculate_correlations(pd.Series(test_preds), pd.Series(test_actuals))
        dir_acc = np.mean(np.sign(test_preds) == np.sign(test_actuals)) * 100.0
        
        results.append({
            "Group": group_name,
            "MAE": mae,
            "RMSE": rmse,
            "Pearson": pearson,
            "Spearman": spearman,
            "Dir_Acc": dir_acc
        })
        
    res_df = pd.DataFrame(results)
    print("\n===== ABLATION STUDY RESULTS (OOS) =====")
    print(res_df.to_string(index=False))
    
    # Save report
    os.makedirs("app/strategies/kronos/reports", exist_ok=True)
    res_df.to_csv("app/strategies/kronos/reports/ablation_results.csv", index=False)
    logger.info("Saved ablation results to app/strategies/kronos/reports/ablation_results.csv")

if __name__ == "__main__":
    run_ablation_study()
