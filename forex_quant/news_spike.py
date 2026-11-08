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


def session_spike_threshold(scores: Iterable[float], percentile: float = 99.0) -> float | None:
    """Return a historical session percentile threshold; never infer one from live data alone."""
    values = sorted(float(value) for value in scores)
    if not values or any(not isfinite(value) or value < 0 for value in values):
        return None
    if not isfinite(float(percentile)) or not 0 < float(percentile) <= 100:
        raise ValueError("percentile must be greater than 0 and at most 100")
    # Nearest-rank percentile: deterministic and conservative for small samples.
    rank = max(1, int((float(percentile) / 100.0) * len(values) + 0.999999))
    return values[min(len(values), rank) - 1]


def event_window_status(event_time, observed_time, window_seconds: int = 120) -> dict:
    """Classify an observation relative to a scheduled event using UTC timestamps."""
    from datetime import datetime, timezone
    if window_seconds < 0:
        raise ValueError("window_seconds cannot be negative")
    def parse(value):
        if isinstance(value, datetime):
            dt = value
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return dt.astimezone(timezone.utc)
    event = parse(event_time)
    observed = parse(observed_time)
    delta = (observed - event).total_seconds()
    return {
        "within_window": abs(delta) <= window_seconds,
        "seconds_from_event": delta,
        "window_seconds": window_seconds,
        "window_start": (event.timestamp() - window_seconds),
        "window_end": (event.timestamp() + window_seconds),
    }
