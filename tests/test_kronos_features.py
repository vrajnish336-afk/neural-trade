import pytest
import pandas as pd
import numpy as np

from app.strategies.kronos.features import build_feature_set, calculate_returns, calculate_trend

def create_dummy_df():
    # Simple linear price
    prices = np.linspace(100, 200, 100)
    return pd.DataFrame({
        'open': prices - 1,
        'high': prices + 2,
        'low': prices - 2,
        'close': prices,
        'volume': np.random.randint(1000, 5000, 100)
    })

def test_no_future_leakage():
    df = create_dummy_df()
    features = build_feature_set(df)
    
    # If we alter the last row of df, only the last row of features should change
    # because features at t should not depend on t+1
    
    df_altered = df.copy()
    df_altered.loc[99, 'close'] = 999.0
    
    features_altered = build_feature_set(df_altered)
    
    # Compare all rows except the last one
    pd.testing.assert_frame_equal(features.iloc[:-1], features_altered.iloc[:-1])
    
    # The last row should be different for some features (like ret_1)
    assert features.iloc[99]['ret_1'] != features_altered.iloc[99]['ret_1']

def test_missing_values_handled():
    df = create_dummy_df()
    # Introduce some nasty data
    df.loc[10, 'close'] = np.nan
    df.loc[20, 'volume'] = 0.0
    df.loc[30, 'high'] = df.loc[30, 'low'] # Force zero range for division by zero check
    
    # Forward fill the intentionally broken close just to make it processable
    df['close'] = df['close'].ffill()
    
    features = build_feature_set(df)
    
    # Check that there are no NaNs or Infs remaining
    assert not features.isnull().values.any()
    assert not np.isinf(features.values).any()

def test_chronological_splits():
    from app.strategies.kronos.training import KronosContextModeler
    
    modeler = KronosContextModeler()
    df = pd.DataFrame({'kronos_pred': range(100), 'target': range(100)})
    
    train, valid, test = modeler.split_chronological(df, train_ratio=0.6, valid_ratio=0.2)
    
    assert len(train) == 60
    assert len(valid) == 20
    assert len(test) == 20
    
    # Ensure no overlap
    assert train.iloc[-1]['kronos_pred'] == 59
    assert valid.iloc[0]['kronos_pred'] == 60
    assert valid.iloc[-1]['kronos_pred'] == 79
    assert test.iloc[0]['kronos_pred'] == 80
