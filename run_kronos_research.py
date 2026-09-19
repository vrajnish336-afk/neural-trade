import logging
from datetime import datetime, timezone
import pandas as pd
import numpy as np
import argparse
from app.core.models import MarketBar

from app.config import config
from app.data.csv_provider import CsvHistoricalDataProvider
from app.strategies.kronos.config import kronos_config
from app.strategies.kronos.strategy import KronosStrategy
from app.strategies.kronos.analytics import calculate_correlations, calculate_mae, calculate_rmse, calculate_magnitude_buckets
from app.strategies.kronos.engine import KronosEngineWrapper

from app.strategies.ensemble import StrategyEnsemble
from app.backtesting.engine import BacktestEngine
from app.backtesting.models import CostConfig
from app.risk.engine import RiskEngine
from app.risk.limits import PortfolioRiskLimits

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
logger = logging.getLogger(__name__)

def evaluate_raw_predictions(bars):
    """Generates raw predictions and calculates Pearson/Spearman, MAE, RMSE."""
    engine = KronosEngineWrapper()
    
    predictions = []
    
    logger.info("Evaluating raw predictions...")
    
    # We will step through the data and predict
    # To save time in tests, we just predict for a subset of the bars.
    # In a real scenario you would predict across all sliding windows.
    # We step every 400 bars similar to D:\Kronos experiments.
    
    start_point = kronos_config.lookback
    step = 400
    
    test_points = list(range(start_point, len(bars) - kronos_config.prediction_horizon, step))
    # Cap to a reasonable number to avoid waiting an hour
    test_points = test_points[-200:]
    
    for count, point in enumerate(test_points, 1):
        x_input = bars[point - kronos_config.lookback : point]
        future = bars[point : point + kronos_config.prediction_horizon]
        
        current_close = x_input[-1].close
        actual_close = future[-1].close
        
        try:
            predicted_return = engine.predict(x_input, pred_len=kronos_config.prediction_horizon)
            actual_return = ((actual_close - current_close) / current_close) * 100.0
            
            predictions.append({
                "test_number": count,
                "current_close": current_close,
                "predicted_return_percent": predicted_return,
                "actual_return_percent": actual_return
            })
        except Exception as e:
            logger.error(f"Error at point {point}: {e}")
            
    if not predictions:
        logger.warning("No predictions generated.")
        return
        
    df = pd.DataFrame(predictions)
    
    pred = df["predicted_return_percent"]
    actual = df["actual_return_percent"]
    
    pearson, spearman = calculate_correlations(pred, actual)
    mae = calculate_mae(pred, actual) # wait, MAE of returns
    rmse = calculate_rmse(pred, actual)
    
    print("\n===== KRONOS RAW PREDICTION METRICS =====")
    print(f"Total evaluated points: {len(df)}")
    print(f"Predicted Return Mean: {pred.mean():.4f}%")
    print(f"Actual Return Mean: {actual.mean():.4f}%")
    print(f"Pearson Correlation: {pearson:.4f}")
    print(f"Spearman Correlation: {spearman:.4f}")
    print(f"MAE (Returns): {mae:.4f}%")
    print(f"RMSE (Returns): {rmse:.4f}%")
    
    print("\n===== MAGNITUDE CALIBRATION =====")
    bucket_df = calculate_magnitude_buckets(df)
    print(bucket_df.to_string(index=False))


def run_walk_forward(bars):
    """Walk forward validation using Neural Trade's BacktestEngine."""
    logger.info("Running Walk-Forward validation...")
    
    # We will use small step sizes
    train_size = kronos_config.wf_train_size
    test_size = kronos_config.wf_test_size
    step_size = kronos_config.wf_step_size
    
    windows = []
    start = 0
    # A 'bar' here is just one data point. Since Kronos needs 512 context, 
    # the actual train window size in 'bars' must be 512 + train_size.
    # To keep the logic aligned with original walk-forward which operated on predictions:
    # Original walk forward: Train on N predictions, test on M predictions.
    # Let's adjust to step over predictions.
    # 
    # But since we use Neural Trade's BacktestEngine, we must pass the actual `MarketBar`s.
    # So we'll slice bars.
    total_bars_needed_train = kronos_config.lookback + train_size
    
    while start + total_bars_needed_train + test_size <= len(bars):
        windows.append({
            "train": bars[start : start + total_bars_needed_train],
            "test": bars[start + train_size : start + total_bars_needed_train + test_size]
        })
        start += step_size
        
        # We will only test 5 windows to prevent timeouts
        if len(windows) >= 5:
            break
            
    oos_results = []
    
    for i, window in enumerate(windows, 1):
        train = window["train"]
        test = window["test"]
        
        best_return = -float('inf')
        best_mode, best_threshold = None, None
        
        for t in kronos_config.thresholds:
            for mode in ["normal", "contrarian"]:
                strategy = KronosStrategy(threshold=t, mode=mode)
                ensemble = StrategyEnsemble([strategy], min_score=0.0)
                limits = PortfolioRiskLimits(initial_equity=10000.0)
                risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
                
                engine = BacktestEngine(
                    ensemble=ensemble,
                    risk_engine=risk_engine,
                    initial_capital=10000.0,
                    cost_config=CostConfig(commission_rate=0.0001, slippage_rate=0.0)
                )
                
                result = engine.run(train)
                
                if result.number_of_trades >= 5 and result.total_return_pct > best_return:
                    best_return = result.total_return_pct
                    best_mode = mode
                    best_threshold = t
                    
        if best_mode is None:
            logger.info(f"Window {i}: No valid training candidate.")
            continue
            
        # Run on TEST
        strategy = KronosStrategy(threshold=best_threshold, mode=best_mode)
        ensemble = StrategyEnsemble([strategy], min_score=0.0)
        limits = PortfolioRiskLimits(initial_equity=10000.0)
        risk_engine = RiskEngine(limits, risk_per_trade_pct=0.05)
        
        test_engine = BacktestEngine(
            ensemble=ensemble,
            risk_engine=risk_engine,
            initial_capital=10000.0,
            cost_config=CostConfig(commission_rate=0.0001, slippage_rate=0.0)
        )
        
        test_result = test_engine.run(test)
        
        logger.info(f"Window {i} | Train Return: {best_return:.2f}% ({best_mode} @ {best_threshold}) | OOS Return: {test_result.total_return_pct:.2f}%")
        
        oos_results.append({
            "window": i,
            "mode": best_mode,
            "threshold": best_threshold,
            "test_trades": test_result.number_of_trades,
            "test_return_percent": test_result.total_return_pct
        })
        
    if not oos_results:
        print("\nNo valid walk-forward results generated.")
        return
        
    oos_df = pd.DataFrame(oos_results)
    
    print("\n===== WALK-FORWARD RESULTS =====")
    print(oos_df.to_string(index=False))
    print(f"\nTotal OOS Return (Sum of Windows): {oos_df['test_return_percent'].sum():.2f}%")
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data", default="data/sample/synthetic_test_data_1D.csv")
    parser.add_argument("--eval-raw", action="store_true")
    parser.add_argument("--eval-wf", action="store_true")
    args = parser.parse_args()
    
    import os
    bars = []
    
    if os.path.exists(args.data):
        logger.info(f"Loading data from {args.data}")
        # Simple CSV loading matching Neural Trade structure
        df = pd.read_csv(args.data)
        if "timestamp" in df.columns or "timestamps" in df.columns:
            df["timestamp"] = pd.to_datetime(df.get("timestamps", df.get("timestamp")))
            df = df.sort_values("timestamp").reset_index(drop=True)
            
            for _, row in df.iterrows():
                bars.append(MarketBar(
                    symbol="TEST",
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row.get("volume", 1000)
                ))
    
    if not bars:
        # Fallback to Kronos data
        kronos_data = r"D:\Kronos\finetune_csv\data\HK_ali_09988_kline_5min_all.csv"
        if os.path.exists(kronos_data):
            logger.info(f"Using Kronos data from {kronos_data}")
            df = pd.read_csv(kronos_data)
            df["timestamp"] = pd.to_datetime(df.get("timestamps", df.get("timestamp")))
            df = df.sort_values("timestamp").reset_index(drop=True)
            
            for _, row in df.iterrows():
                bars.append(MarketBar(
                    symbol="HK_09988",
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"]
                ))
        else:
            logger.error("No data found.")
            exit(1)
        
    if args.eval_raw:
        evaluate_raw_predictions(bars)
        
    if args.eval_wf:
        run_walk_forward(bars)
