import pandas as pd
import numpy as np
from typing import Tuple, List

class NumpyStandardScaler:
    def __init__(self):
        self.mean_ = None
        self.scale_ = None
        
    def fit(self, X: np.ndarray):
        self.mean_ = np.mean(X, axis=0)
        self.scale_ = np.std(X, axis=0)
        self.scale_[self.scale_ == 0.0] = 1.0 # Prevent div by zero
        
    def transform(self, X: np.ndarray) -> np.ndarray:
        return (X - self.mean_) / self.scale_
        
    def fit_transform(self, X: np.ndarray) -> np.ndarray:
        self.fit(X)
        return self.transform(X)

class NumpyRidge:
    def __init__(self, alpha: float = 1.0):
        self.alpha = alpha
        self.w = None
        
    def fit(self, X: np.ndarray, y: np.ndarray):
        # Add bias term
        X_b = np.c_[np.ones((X.shape[0], 1)), X]
        n_features = X_b.shape[1]
        
        # Identity matrix for regularization
        A = np.eye(n_features)
        A[0, 0] = 0 # Do not regularize the bias term
        
        # Closed form Ridge Regression solution
        self.w = np.linalg.inv(X_b.T @ X_b + self.alpha * A) @ X_b.T @ y
        
    def predict(self, X: np.ndarray) -> np.ndarray:
        X_b = np.c_[np.ones((X.shape[0], 1)), X]
        return X_b @ self.w

class KronosContextModeler:
    """
    Implements Approach A: Contextual augmentation of Kronos.
    Trains a lightweight machine learning model (Numpy Ridge)
    that takes engineered features + Kronos baseline prediction
    to output an enhanced prediction, explicitly avoiding data leakage.
    """
    def __init__(self, alpha: float = 1.0):
        self.model = NumpyRidge(alpha=alpha)
        self.scaler = NumpyStandardScaler()
        self.is_fitted = False
        
    def prepare_data(self, df_features: pd.DataFrame, kronos_preds: pd.Series, actual_targets: pd.Series) -> pd.DataFrame:
        """Aligns features with predictions and targets."""
        df = df_features.copy()
        df['kronos_pred'] = kronos_preds
        df['target'] = actual_targets
        
        # Drop rows where target or kronos_pred is nan
        df = df.dropna(subset=['kronos_pred', 'target'])
        
        return df

    def split_chronological(self, df: pd.DataFrame, train_ratio: float = 0.6, valid_ratio: float = 0.2) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Strictly splits data chronologically."""
        n = len(df)
        train_end = int(n * train_ratio)
        valid_end = train_end + int(n * valid_ratio)
        
        train_df = df.iloc[:train_end].copy()
        valid_df = df.iloc[train_end:valid_end].copy()
        test_df = df.iloc[valid_end:].copy()
        
        return train_df, valid_df, test_df
        
    def fit(self, train_df: pd.DataFrame, feature_cols: List[str]):
        """Fits the scaler and model strictly on training data."""
        X_train = train_df[feature_cols].values
        y_train = train_df['target'].values
        
        X_train_scaled = self.scaler.fit_transform(X_train)
        self.model.fit(X_train_scaled, y_train)
        self.is_fitted = True
        
    def predict(self, test_df: pd.DataFrame, feature_cols: List[str]) -> np.ndarray:
        """Predicts on unseen data using training-fit statistics."""
        if not self.is_fitted:
            raise ValueError("Model must be fitted before prediction.")
            
        X_test = test_df[feature_cols].values
        X_test_scaled = self.scaler.transform(X_test)
        
        return self.model.predict(X_test_scaled)
