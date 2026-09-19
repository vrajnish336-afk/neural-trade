import numpy as np
import pandas as pd

def calculate_correlations(predicted: pd.Series, actual: pd.Series):
    """Calculates Pearson and Spearman correlations."""
    try:
        pearson = predicted.corr(actual, method="pearson")
        spearman = predicted.corr(actual, method="spearman")
    except Exception:
        pearson, spearman = 0.0, 0.0
    return pearson, spearman

def calculate_mae(predicted: pd.Series, actual: pd.Series) -> float:
    return np.mean(np.abs(predicted - actual))

def calculate_rmse(predicted: pd.Series, actual: pd.Series) -> float:
    return np.sqrt(np.mean((predicted - actual) ** 2))

def calculate_magnitude_buckets(df: pd.DataFrame) -> pd.DataFrame:
    """Groups predictions into magnitude buckets and calculates statistics."""
    if df.empty:
        return pd.DataFrame()
        
    df = df.copy()
    df["prediction_abs"] = df["predicted_return_percent"].abs()
    
    bins = [0.00, 0.05, 0.10, 0.20, 0.30, 0.50, np.inf]
    labels = ["0.00-0.05%", "0.05-0.10%", "0.10-0.20%", "0.20-0.30%", "0.30-0.50%", "0.50%+"]
    
    df["magnitude_bucket"] = pd.cut(
        df["prediction_abs"],
        bins=bins,
        labels=labels,
        right=False,
        include_lowest=True
    )
    
    df["direction_correct"] = np.sign(df["predicted_return_percent"]) == np.sign(df["actual_return_percent"])
    df["contrarian_correct"] = np.sign(df["predicted_return_percent"]) != np.sign(df["actual_return_percent"])
    
    bucket_results = []
    for label in labels:
        subset = df[df["magnitude_bucket"] == label]
        if len(subset) == 0:
            continue
            
        bucket_results.append({
            "bucket": label,
            "count": len(subset),
            "avg_prediction": subset["predicted_return_percent"].mean(),
            "avg_actual": subset["actual_return_percent"].mean(),
            "normal_accuracy": subset["direction_correct"].mean() * 100,
            "contrarian_accuracy": subset["contrarian_correct"].mean() * 100,
            "actual_avg_abs_return": subset["actual_return_percent"].abs().mean()
        })
        
    return pd.DataFrame(bucket_results)
