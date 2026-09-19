import pandas as pd
import numpy as np

def calculate_returns(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    features['ret_1'] = df['close'].pct_change(1)
    features['ret_3'] = df['close'].pct_change(3)
    features['ret_5'] = df['close'].pct_change(5)
    features['ret_10'] = df['close'].pct_change(10)
    features['ret_20'] = df['close'].pct_change(20)
    features['roll_vol_20'] = features['ret_1'].rolling(20).std()
    return features

def calculate_trend(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    sma_10 = df['close'].rolling(10).mean()
    sma_20 = df['close'].rolling(20).mean()
    sma_50 = df['close'].rolling(50).mean()
    
    features['dist_sma_10'] = (df['close'] - sma_10) / sma_10
    features['dist_sma_20'] = (df['close'] - sma_20) / sma_20
    features['sma_10_20_cross'] = (sma_10 - sma_20) / sma_20
    features['trend_slope_10'] = sma_10.diff(3) / sma_10
    return features

def calculate_momentum(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    
    # RSI 14
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    features['rsi_14'] = 100 - (100 / (1 + rs))
    
    # ROC
    features['roc_10'] = df['close'].pct_change(10) * 100
    
    # MACD-style
    ema_12 = df['close'].ewm(span=12, adjust=False).mean()
    ema_26 = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()
    features['macd_hist'] = (macd - macd_signal) / df['close']
    
    return features

def calculate_volatility(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    
    # High-Low Range
    features['hl_range_pct'] = (df['high'] - df['low']) / df['close']
    features['roll_hl_range_10'] = features['hl_range_pct'].rolling(10).mean()
    
    return features

def calculate_volume(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    vol = df.get('volume', pd.Series(1000, index=df.index))
    
    features['vol_change_1'] = vol.pct_change(1)
    
    vol_mean = vol.rolling(20).mean()
    vol_std = vol.rolling(20).std()
    # Replace 0 std with inf to avoid div by zero, which then becomes 0 in fillna
    vol_std = vol_std.replace(0, np.nan)
    features['vol_zscore_20'] = (vol - vol_mean) / vol_std
    
    return features

def calculate_market_structure(df: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame(index=df.index)
    
    body = (df['close'] - df['open']).abs()
    hl_range = df['high'] - df['low']
    # Avoid div by zero
    hl_range = hl_range.replace(0, np.nan)
    
    features['body_range_ratio'] = body / hl_range
    
    upper_wick = df['high'] - df[['open', 'close']].max(axis=1)
    lower_wick = df[['open', 'close']].min(axis=1) - df['low']
    
    features['upper_wick_ratio'] = upper_wick / hl_range
    features['lower_wick_ratio'] = lower_wick / hl_range
    
    roll_high = df['high'].rolling(20).max()
    roll_low = df['low'].rolling(20).min()
    
    features['dist_roll_high'] = (roll_high - df['close']) / df['close']
    features['dist_roll_low'] = (df['close'] - roll_low) / df['close']
    
    return features

def build_feature_set(df: pd.DataFrame) -> pd.DataFrame:
    """Combines all feature groups into a single DataFrame."""
    f_ret = calculate_returns(df)
    f_trend = calculate_trend(df)
    f_mom = calculate_momentum(df)
    f_volat = calculate_volatility(df)
    f_vol = calculate_volume(df)
    f_struct = calculate_market_structure(df)
    
    combined = pd.concat([f_ret, f_trend, f_mom, f_volat, f_vol, f_struct], axis=1)
    
    # We strictly shift ALL features by 1 if they are to be used for predicting the NEXT candle.
    # Actually, if we compute them up to row t, they are safe to use for predicting t+1.
    # The target will be computed as row t+1 return.
    
    # Let's clean up infinite and nan values produced by divisions and early rolling windows
    combined.replace([np.inf, -np.inf], np.nan, inplace=True)
    combined.ffill(inplace=True)
    combined.fillna(0, inplace=True)
    
    return combined

