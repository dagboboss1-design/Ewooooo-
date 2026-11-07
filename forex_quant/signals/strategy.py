from __future__ import annotations
from dataclasses import asdict, dataclass
from math import floor
import pandas as pd
from .indicators import atr, bollinger, classify_regime, macd_histogram, rsi

@dataclass(frozen=True)
class Signal:
    instrument: str
    timestamp: str
    side: str
    entry: float
    stop_loss: float
    take_profit: float
    units: int
    risk_fraction: float
    confidence_score: float
    regime: str
    invalidation: str
    strategy: str = 'bb_rsi_macd_mean_reversion_v1'
    def to_dict(self) -> dict:
        return asdict(self)

def generate_signal(frame: pd.DataFrame, instrument: str, equity: float, quote_to_account_rate: float = 1.0, risk_fraction: float = 0.005, reward_risk: float = 2.0) -> Signal | None:
    """Closed-bar candidate only. Confidence is confluence, not win probability."""
    required = {'time','open','high','low','close'}
    if not required.issubset(frame.columns):
        raise ValueError(f'Missing columns: {sorted(required - set(frame.columns))}')
    if not 0 < risk_fraction <= 0.01:
        raise ValueError('risk_fraction must be > 0 and <= 1%')
    if equity <= 0 or quote_to_account_rate <= 0 or reward_risk <= 0:
        raise ValueError('equity, conversion rate and reward_risk must be positive')
    if len(frame) < 60:
        return None
    data = frame.copy()
    data['time'] = pd.to_datetime(data['time'], utc=True, errors='raise')
    data = data.sort_values('time', kind='stable').reset_index(drop=True)
    if data['time'].duplicated().any():
        raise ValueError('Duplicate candle timestamps are not allowed')
    for col in ('open','high','low','close'):
        data[col] = pd.to_numeric(data[col], errors='coerce')
    if data[['open','high','low','close']].isna().any().any():
        raise ValueError('OHLC values must be numeric and non-null')
    if not (data['high'] >= data[['open','close','low']].max(axis=1)).all():
        raise ValueError('Invalid OHLC high values')
    if not (data['low'] <= data[['open','close','high']].min(axis=1)).all():
        raise ValueError('Invalid OHLC low values')
    regime = classify_regime(data)
    if regime != 'ranging':
        return None
    close = data['close']
    mid, upper, lower = bollinger(close)
    hist, strength, volatility = macd_histogram(close), rsi(close), atr(data)
    vals = [upper.iloc[-1], lower.iloc[-1], hist.iloc[-1], hist.iloc[-2], strength.iloc[-1], volatility.iloc[-1]]
    if any(pd.isna(v) for v in vals):
        return None
    price, av = float(close.iloc[-1]), float(volatility.iloc[-1])
    if price <= 0 or av <= 0:
        return None
    long_checks = (price <= float(lower.iloc[-1])*1.001, float(strength.iloc[-1]) < 30, float(hist.iloc[-1]) > float(hist.iloc[-2]))
    short_checks = (price >= float(upper.iloc[-1])*0.999, float(strength.iloc[-1]) > 70, float(hist.iloc[-1]) < float(hist.iloc[-2]))
    if all(long_checks): side, checks = 'buy', long_checks
    elif all(short_checks): side, checks = 'sell', short_checks
    else: return None
    distance = 1.5 * av
    stop = price - distance if side == 'buy' else price + distance
    target = price + reward_risk*distance if side == 'buy' else price - reward_risk*distance
    units = floor((equity*risk_fraction) / (distance*quote_to_account_rate))
    if units < 1: return None
    return Signal(instrument, data['time'].iloc[-1].isoformat(), side, price, stop, target, units, risk_fraction, round(sum(checks)/3,4), regime, 'Close beyond stop_loss or regime changes from ranging')
