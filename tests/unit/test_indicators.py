import pytest
import pandas as pd
import numpy as np
from app.analysis.indicators import (
    calculate_sma, calculate_ema, calculate_rsi, 
    calculate_atr, calculate_volatility, calculate_roc
)

def test_sma_correctness():
    series = pd.Series([10, 20, 30, 40, 50])
    sma = calculate_sma(series, 3)
    # NaN, NaN, 20, 30, 40
    assert pd.isna(sma.iloc[0])
    assert pd.isna(sma.iloc[1])
    assert sma.iloc[2] == 20
    assert sma.iloc[3] == 30
    
def test_ema_correctness():
    series = pd.Series([10, 10, 10, 10])
    ema = calculate_ema(series, 2)
    assert pd.isna(ema.iloc[0])
    assert ema.iloc[-1] == 10

def test_rsi_bounds():
    # Upward trend
    series_up = pd.Series([10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 34, 36, 38])
    rsi = calculate_rsi(series_up, 14)
    assert rsi.iloc[-1] > 50
    assert rsi.iloc[-1] <= 100
    
def test_atr_behavior():
    high = pd.Series([10, 15, 12])
    low = pd.Series([8, 9, 10])
    close = pd.Series([9, 14, 11])
    atr = calculate_atr(high, low, close, 2)
    assert pd.isna(atr.iloc[0])
    assert atr.iloc[1] > 0
    assert atr.iloc[2] > 0

def test_insufficient_data():
    series = pd.Series([10])
    sma = calculate_sma(series, 5)
    assert pd.isna(sma.iloc[0])
    
    roc = calculate_roc(series, 5)
    assert pd.isna(roc.iloc[0])
