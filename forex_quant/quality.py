from __future__ import annotations
import pandas as pd


def normalize_utc(frame, time_column="time"):
    if time_column not in frame.columns:
        raise ValueError(f"Missing time column: {time_column}")

    out = frame.copy()
    out[time_column] = pd.to_datetime(
        out[time_column], utc=True, errors="raise"
    )
    return out.sort_values(
        time_column, kind="stable"
    ).reset_index(drop=True)


def duplicate_timestamps(frame, time_column="time"):
    if time_column not in frame.columns:
        raise ValueError(f"Missing time column: {time_column}")

    values = frame.loc[
        frame[time_column].duplicated(keep=False), time_column
    ]
    return sorted(
        pd.to_datetime(values, utc=True).astype(str).unique().tolist()
    )


def detect_gaps(frame, time_column="time", expected_frequency="1h"):
    if frame.empty:
        return []

    normalized = normalize_utc(frame, time_column)
    index = pd.DatetimeIndex(
        normalized[time_column].drop_duplicates()
    )

    if len(index) < 2:
        return []

    expected = pd.date_range(
        index.min(), index.max(),
        freq=expected_frequency, tz="UTC"
    )

    return [
        value.isoformat()
        for value in expected.difference(index)
    ]


def validate_ohlc(frame):
    required = {"open", "high", "low", "close"}

    if not required.issubset(frame.columns):
        return [f"Missing OHLC columns: {sorted(required - set(frame.columns))}"]

    bad = (
        (frame["high"] < frame[["open", "close", "low"]].max(axis=1))
        | (frame["low"] > frame[["open", "close", "high"]].min(axis=1))
    )

    return (
        [f"{int(bad.sum())} rows violate OHLC bounds"]
        if bad.any() else []
    )


def quality_report(frame, time_column="time", expected_frequency="1h"):
    normalized = normalize_utc(frame, time_column) if not frame.empty else frame.copy()

    return {
        "rows": len(frame),
        "duplicate_timestamps": duplicate_timestamps(normalized, time_column) if not frame.empty else [],
        "gaps": detect_gaps(normalized, time_column, expected_frequency),
        "ohlc_errors": validate_ohlc(normalized)
        if {"open", "high", "low", "close"}.issubset(normalized.columns)
        else [],
    }
