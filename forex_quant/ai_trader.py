"""Technical confluence engine for Ewoooooo.

Consumes candles from the dashboard's existing market-data adapters; it does
not create a second feed or invent prices.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / period, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / period, adjust=False).mean()
    relative = gain.div(loss.replace(0, np.nan))
    result = 100 - (100 / (1 + relative))
    result = result.mask((loss == 0) & (gain > 0), 100.0)
    return result.mask((loss == 0) & (gain == 0), 50.0)


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    fast_ema = close.ewm(span=fast, adjust=False).mean()
    slow_ema = close.ewm(span=slow, adjust=False).mean()
    line = fast_ema - slow_ema
    signal_line = line.ewm(span=signal, adjust=False).mean()
    return line, signal_line, line - signal_line


def bollinger(close: pd.Series, period: int = 20, deviations: float = 2.0):
    middle = close.rolling(period).mean()
    spread = close.rolling(period).std()
    upper, lower = middle + deviations * spread, middle - deviations * spread
    percent_b = (close - lower).div((upper - lower).replace(0, np.nan))
    return upper, middle, lower, percent_b


def atr(frame: pd.DataFrame, period: int = 14) -> pd.Series:
    high, low, close = frame["high"], frame["low"], frame["close"]
    true_range = pd.concat(
        [high - low, (high - close.shift()).abs(), (low - close.shift()).abs()],
        axis=1,
    ).max(axis=1)
    return true_range.ewm(alpha=1 / period, adjust=False).mean()


def enrich(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        raise ValueError("No candles were supplied.")
    result = frame.copy()
    result.columns = [str(column).lower() for column in result.columns]
    required = {"open", "high", "low", "close"}
    missing = required.difference(result.columns)
    if missing:
        raise ValueError("Candles are missing required fields: " + ", ".join(sorted(missing)))
    for column in required:
        result[column] = pd.to_numeric(result[column], errors="coerce")
    # Tick volume is often absent for OTC FX; missing volume must not vote.
    if "volume" not in result:
        result["volume"] = 0.0
    result["volume"] = pd.to_numeric(result["volume"], errors="coerce").fillna(0.0)
    result = result.dropna(subset=list(required)).sort_index()
    result["ema20"] = result["close"].ewm(span=20, adjust=False).mean()
    result["ema50"] = result["close"].ewm(span=50, adjust=False).mean()
    result["rsi"] = rsi(result["close"])
    result["macd"], result["macd_sig"], result["macd_hist"] = macd(result["close"])
    result["bb_upper"], result["bb_mid"], result["bb_lower"], result["pctb"] = bollinger(result["close"])
    result["atr"] = atr(result)
    return result.replace([np.inf, -np.inf], np.nan).dropna(
        subset=["ema20", "ema50", "rsi", "macd", "macd_sig", "pctb", "atr"]
    )


def analyze(frame: pd.DataFrame, symbol: str, timeframe: str) -> dict[str, Any]:
    if len(frame) < 60:
        raise ValueError(f"Not enough candles ({len(frame)}); at least 60 are required.")
    enriched = enrich(frame)
    if len(enriched) < 60:
        raise ValueError(f"Not enough valid indicator candles ({len(enriched)}); at least 60 are required.")
    last, previous = enriched.iloc[-1], enriched.iloc[-2]
    price, atr_value = float(last["close"]), float(last["atr"])
    if not np.isfinite(price) or not np.isfinite(atr_value) or atr_value <= 0:
        raise ValueError("Price or ATR is invalid; no trade analysis can be produced.")

    bullish = bearish = 0
    notes: list[str] = []
    if last["ema20"] > last["ema50"]:
        bullish += 1
        notes.append("EMA20 above EMA50: uptrend")
    elif last["ema20"] < last["ema50"]:
        bearish += 1
        notes.append("EMA20 below EMA50: downtrend")
    else:
        notes.append("EMA trend is flat")

    rsi_value = float(last["rsi"])
    if 50 < rsi_value < 70:
        bullish += 1
        notes.append(f"RSI {rsi_value:.1f}: bullish momentum")
    elif 30 < rsi_value < 50:
        bearish += 1
        notes.append(f"RSI {rsi_value:.1f}: bearish momentum")
    else:
        notes.append(f"RSI {rsi_value:.1f}: neutral or extreme; no vote")

    if last["macd"] > last["macd_sig"]:
        bullish += 1
        notes.append("MACD above signal")
    elif last["macd"] < last["macd_sig"]:
        bearish += 1
        notes.append("MACD below signal")
    else:
        notes.append("MACD is flat")

    percent_b = float(last["pctb"])
    if 0.5 < percent_b < 0.95:
        bullish += 1
        notes.append(f"Bollinger %B {percent_b:.2f}: upper-half momentum")
    elif 0.05 < percent_b < 0.5:
        bearish += 1
        notes.append(f"Bollinger %B {percent_b:.2f}: lower-half momentum")
    else:
        notes.append(f"Bollinger %B {percent_b:.2f}: extreme; no vote")

    volume_average = float(enriched["volume"].tail(20).mean())
    volume_recent = float(enriched["volume"].tail(3).mean())
    change = float(last["close"] - previous["close"])
    volume_ratio = volume_recent / volume_average if volume_average > 0 else None
    if volume_average > 0 and volume_recent > volume_average and change > 0:
        bullish += 1
        notes.append("Volume above average with rising price")
    elif volume_average > 0 and volume_recent > volume_average and change < 0:
        bearish += 1
        notes.append("Volume above average with falling price")
    else:
        notes.append("Volume inconclusive or unavailable; no vote")

    if bullish >= 3 and bullish > bearish:
        signal = "STRONG BUY" if bullish >= 4 else "BUY"
    elif bearish >= 3 and bearish > bullish:
        signal = "STRONG SELL" if bearish >= 4 else "SELL"
    else:
        signal = "HOLD / NO TRADE"

    plan = None
    if signal.endswith("BUY"):
        plan = {"entry": price, "stop": round(price - 1.5 * atr_value, 8),
                "target": round(price + 3.0 * atr_value, 8), "rr": 2.0}
    elif signal.endswith("SELL"):
        plan = {"entry": price, "stop": round(price + 1.5 * atr_value, 8),
                "target": round(price - 3.0 * atr_value, 8), "rr": 2.0}

    return {
        "symbol": symbol, "timeframe": timeframe, "price": round(price, 8),
        "bias": "Bullish" if bullish > bearish else "Bearish" if bearish > bullish else "Neutral",
        "signal": signal, "votes": f"{bullish}B / {bearish}S",
        "bullish_votes": bullish, "bearish_votes": bearish, "notes": notes, "plan": plan,
        "indicators": {
            "rsi": round(rsi_value, 2), "macd": round(float(last["macd"]), 8),
            "macd_signal": round(float(last["macd_sig"]), 8),
            "ema20": round(float(last["ema20"]), 8), "ema50": round(float(last["ema50"]), 8),
            "pctb": round(percent_b, 3), "atr": round(atr_value, 8),
            "vol_ratio": round(volume_ratio, 2) if volume_ratio is not None else None,
        },
        "execution": "PAPER_ANALYSIS_ONLY",
        "warning": "Technical confluence is not a guarantee. Confirm higher-timeframe bias, news risk, spread and account risk before any paper setup.",
    }
