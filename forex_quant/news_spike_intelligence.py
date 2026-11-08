"""Pre-release directional forecast using the existing technical strategy and cross-asset bias.

This module never predicts the surprise value of an unreleased announcement and never
submits orders. It combines completed/available M15 market structure with currency
strength inferred from correlated pairs and gold's inverse USD relationship.
"""
from __future__ import annotations

from math import tanh
from statistics import mean
from typing import Any

import pandas as pd

from forex_quant.signals.indicators import atr, bollinger, classify_regime, macd_histogram, rsi


def _instrument_score(frame: pd.DataFrame) -> dict[str, Any] | None:
    required = {"open", "high", "low", "close", "time"}
    if frame is None or len(frame) < 60 or not required.issubset(frame.columns):
        return None
    data = frame.copy().sort_values("time", kind="stable").reset_index(drop=True)
    close = pd.to_numeric(data["close"], errors="coerce")
    if close.isna().any() or (close <= 0).any():
        return None
    volatility = atr(data)
    strength = rsi(close)
    macd = macd_histogram(close)
    mid, upper, lower = bollinger(close)
    values = [volatility.iloc[-1], strength.iloc[-1], macd.iloc[-1], macd.iloc[-2],
              upper.iloc[-1], lower.iloc[-1], mid.iloc[-1]]
    if any(pd.isna(value) for value in values):
        return None

    price = float(close.iloc[-1])
    atr_value = float(volatility.iloc[-1])
    if price <= 0 or atr_value <= 0:
        return None
    recent_return = price / float(close.iloc[-5]) - 1.0
    trend_component = tanh(recent_return / max((atr_value / price) * 2.0, 1e-9))
    macd_component = tanh(float(macd.iloc[-1]) / atr_value * 3.0)
    rsi_component = max(-1.0, min(1.0, (float(strength.iloc[-1]) - 50.0) / 25.0))

    regime = classify_regime(data)
    mean_reversion_component = 0.0
    if regime == "ranging":
        if price <= float(lower.iloc[-1]) * 1.001 and float(strength.iloc[-1]) < 35 and macd.iloc[-1] > macd.iloc[-2]:
            mean_reversion_component = 1.0
        elif price >= float(upper.iloc[-1]) * 0.999 and float(strength.iloc[-1]) > 65 and macd.iloc[-1] < macd.iloc[-2]:
            mean_reversion_component = -1.0

    score = (
        0.40 * trend_component
        + 0.25 * macd_component
        + 0.20 * rsi_component
        + 0.15 * mean_reversion_component
    )
    return {
        "score": max(-1.0, min(1.0, score)),
        "rsi": round(float(strength.iloc[-1]), 2),
        "regime": regime,
        "atr_fraction": round(atr_value / price, 6),
    }


def build_pre_news_forecast(currency: str, frames: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Return BUY/SELL/WAIT for the first affected FX pair, with confluence gating."""
    currency = str(currency or "").upper()
    fx_symbols = [
        symbol for symbol in frames
        if "/" in symbol and symbol not in {"XAU/USD", "XAG/USD", "BTC/USD"}
    ]
    if not fx_symbols:
        return {"direction": "WAIT", "instrument": None, "strength": "LOW",
                "status": "insufficient_data", "confluence": 0.0, "instruments_used": []}

    scores: dict[str, dict[str, Any]] = {}
    for symbol, frame in frames.items():
        result = _instrument_score(frame)
        if result is not None:
            scores[symbol] = result

    valid_fx = [symbol for symbol in fx_symbols if symbol in scores]
    if not valid_fx:
        return {"direction": "WAIT", "instrument": fx_symbols[0], "strength": "LOW",
                "status": "insufficient_data", "confluence": 0.0, "instruments_used": []}

    currency_strengths: dict[str, list[float]] = {}
    for symbol in valid_fx:
        base, quote = symbol.split("/", 1)
        value = scores[symbol]["score"]
        currency_strengths.setdefault(base, []).append(value)
        currency_strengths.setdefault(quote, []).append(-value)

    # Gold is an inverse USD pressure gauge, not a substitute for a missing DXY feed.
    if currency == "USD" and "XAU/USD" in scores:
        gold_score = scores["XAU/USD"]["score"]
        currency_strengths.setdefault("USD", []).append(-gold_score)

    target = next((symbol for symbol in fx_symbols if symbol in scores), fx_symbols[0])
    base, quote = target.split("/", 1)
    base_values = currency_strengths.get(base, [])
    quote_values = currency_strengths.get(quote, [])
    if not base_values or not quote_values or len(scores) < 2:
        return {"direction": "WAIT", "instrument": target, "strength": "LOW",
                "status": "insufficient_confluence", "confluence": 0.0,
                "instruments_used": list(scores)}

    base_strength = mean(base_values)
    quote_strength = mean(quote_values)
    combined = max(-1.0, min(1.0, (base_strength - quote_strength) / 2.0))
    aligned_effects: list[float] = []
    for symbol, value in scores.items():
        score = value["score"]
        if symbol == "XAU/USD" and currency == "USD":
            effect = score if quote == "USD" else -score if base == "USD" else 0.0
        elif "/" in symbol:
            pair_base, pair_quote = symbol.split("/", 1)
            effect = 0.0
            if pair_base == base:
                effect += score
            if pair_quote == base:
                effect -= score
            if pair_base == quote:
                effect -= score
            if pair_quote == quote:
                effect += score
        else:
            effect = 0.0
        if effect:
            aligned_effects.append(effect)
    aligned = sum(1 for effect in aligned_effects if effect * combined > 0)
    confluence = aligned / max(1, len(aligned_effects))

    if abs(combined) < 0.18 or confluence < 0.60:
        direction, status = "WAIT", "conflicting_or_weak_bias"
    else:
        direction, status = ("BUY" if combined > 0 else "SELL"), "forecast_ready"

    strength = "HIGH" if abs(combined) >= 0.45 and confluence >= 0.75 else (
        "MEDIUM" if abs(combined) >= 0.25 and confluence >= 0.60 else "LOW"
    )
    return {
        "direction": direction,
        "instrument": target,
        "strength": strength,
        "status": status,
        "confluence": round(confluence, 2),
        "instruments_used": list(scores),
        "strategy": "M15 Bollinger/RSI/MACD forecast + cross-asset currency strength",
        "dxy_available": False,
    }
