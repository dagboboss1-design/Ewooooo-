from __future__ import annotations
import numpy as np
import pandas as pd

def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    close = pd.to_numeric(close, errors='coerce').astype(float)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1/period, adjust=False, min_periods=period).mean()
    result = 100 - 100 / (1 + gain / loss.replace(0, np.nan))
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    return result.mask((gain == 0) & (loss > 0), 0.0)

def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = (pd.to_numeric(frame[k], errors='coerce').astype(float) for k in ('high','low','close'))
    prev = close.shift(1)
    tr = pd.concat([high-low, (high-prev).abs(), (low-prev).abs()], axis=1).max(axis=1)
    return tr.ewm(alpha=1/period, adjust=False, min_periods=period).mean()

def bollinger(close: pd.Series, period: int = 20, deviations: float = 2.0):
    close = pd.to_numeric(close, errors='coerce').astype(float)
    mid = close.rolling(period, min_periods=period).mean()
    sd = close.rolling(period, min_periods=period).std(ddof=0)
    return mid, mid + deviations*sd, mid - deviations*sd

def macd_histogram(close: pd.Series):
    close = pd.to_numeric(close, errors='coerce').astype(float)
    line = close.ewm(span=12, adjust=False, min_periods=26).mean() - close.ewm(span=26, adjust=False, min_periods=26).mean()
    signal = line.ewm(span=9, adjust=False, min_periods=9).mean()
    return line - signal

def classify_regime(frame: pd.DataFrame) -> str:
    close = pd.to_numeric(frame['close'], errors='coerce').astype(float)
    vol = atr(frame)
    if len(frame) < 60 or pd.isna(vol.iloc[-1]) or close.iloc[-1] <= 0:
        return 'unknown'
    vol_pct = vol / close
    baseline = vol_pct.rolling(50, min_periods=30).median().iloc[-1]
    if pd.isna(baseline) or baseline <= 0:
        return 'unknown'
    if vol_pct.iloc[-1] > baseline * 1.8:
        return 'high_vol'
    ema = close.ewm(span=50, adjust=False, min_periods=50).mean()
    slope = abs((ema.iloc[-1] - ema.iloc[-6]) / close.iloc[-1])
    return 'trending' if slope > (vol.iloc[-1] / close.iloc[-1]) * 0.35 else 'ranging'
