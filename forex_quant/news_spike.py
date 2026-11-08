"""Deterministic Phase 5 event-surprise and tick-spike primitives.

These functions do not predict direction or claim live feed connectivity.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, sqrt
from statistics import mean, pstdev
from typing import Iterable

CURRENCY_IMPACT: dict[str, tuple[str, ...]] = {
    "USD": ("EUR/USD", "GBP/USD", "USD/JPY", "AUD/USD", "USD/CAD", "XAU/USD", "BTC/USD", "DXY"),
    "EUR": ("EUR/USD", "EUR/GBP"),
    "GBP": ("GBP/USD", "EUR/GBP"),
    "JPY": ("USD/JPY",),
    "AUD": ("AUD/USD", "AUD/NZD"),
    "CAD": ("USD/CAD",),
    "NZD": ("AUD/NZD",),
    "CHF": (),
}


@dataclass(frozen=True)
class SurpriseScore:
    normalized: float | None
    classification: str
    direction_hint: str | None


def normalized_surprise(
    actual: float, forecast: float, historical_surprises: Iterable[float]
) -> SurpriseScore:
    """Normalize an actual-vs-forecast miss by historical surprise volatility.

    A directional hint is only the sign of the surprise, not a trade direction.
    """
    history = [float(value) for value in historical_surprises if isfinite(float(value))]
    if len(history) < 2:
        return SurpriseScore(None, "insufficient_history", None)
    scale = pstdev(history)
    if scale <= 0:
        return SurpriseScore(None, "zero_historical_variance", None)
    score = (float(actual) - float(forecast)) / scale
    magnitude = abs(score)
    if magnitude < 0.5:
        label = "no_edge"
    elif magnitude > 1.5:
        label = "large_surprise"
    else:
        label = "moderate_surprise"
    return SurpriseScore(score, label, "positive" if score > 0 else "negative" if score < 0 else None)


def tick_spike_score(prices: Iterable[float], window: int = 30) -> float | None:
    """Return the latest absolute tick-return z-score against prior ticks."""
    values = [float(value) for value in prices]
    if window < 5 or len(values) < window + 2:
        return None
    if any(not isfinite(value) or value <= 0 for value in values):
        return None
    returns = [values[i] / values[i - 1] - 1 for i in range(1, len(values))]
    baseline = returns[-(window + 1):-1]
    sigma = pstdev(baseline)
    if sigma <= 0:
        return None
    return abs((returns[-1] - mean(baseline)) / sigma)


def spread_guard(spread: float, maximum_allowed: float) -> bool:
    """True only when a finite non-negative spread is within the configured cap."""
    return (
        isfinite(float(spread))
        and isfinite(float(maximum_allowed))
        and float(spread) >= 0
        and float(maximum_allowed) >= 0
        and float(spread) <= float(maximum_allowed)
    )


def impacted_instruments(currency: str) -> tuple[str, ...]:
    """Return the configured watchlist instruments associated with a currency."""
    return CURRENCY_IMPACT.get(currency.upper(), ())
