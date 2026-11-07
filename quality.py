from __future__ import annotations
import pandas as pd

TIME_COLUMNS = ("time", "timestamp", "datetime")

def normalize_utc(frame: pd.DataFrame, time_column: str = "time") -> pd.DataFrame:
    if time_column not in frame.columns:
        raise ValueError(f"Missing time column: {time_column}")
    out = frame.copy()
    out[time_column] = pd.to_datetime(out[time_column], utc=True, errors="raise")
    return out.sort_values(time_column, kind="stable").reset_index(drop=True)

def duplicate_timestamps(frame: pd.DataFrame, time_column: str = "time") -> list[str]:
    if time_column not in frame:
        raise ValueError(f"Missing time column: {time_column}")
    vals = frame.loc[frame[time_column].duplicated(keep=False), time_column]
    return sorted(pd.to_datetime(vals, utc=True).astype(str).unique().tolist())

def detect_gaps(frame: pd.DataFrame, *, time_column="time", expected_frequency="1h") -> list[str]:
    if frame.empty:
        return []
    normalized = normalize_utc(frame, time_column)
    idx = pd.DatetimeIndex(normalized[time_column].drop_duplicates())
    if len(idx) < 2:
        return []
    expected = pd.date_range(idx.min(), idx.max(), freq=expected_frequency, tz="UTC")
    missing = expected.difference(idx)
    # This reports calendar gaps too; FX weekend/holiday interpretation is a later market-calendar policy.
    return [x.isoformat() for x in missing]

def validate_ohlc(frame: pd.DataFrame) -> list[str]:
    required = {"open", "high", "low", "close"}
    if not required.issubset(frame.columns):
        return [f"Missing OHLC columns: {sorted(required - set(frame.columns))}"]
    errors = []
    bad = (frame["high"] < frame[["open", "close", "low"]].max(axis=1)) | (
        frame["low"] > frame[["open", "close", "high"]].min(axis=1)
    )
    if bad.any():
        errors.append(f"{int(bad.sum())} rows violate OHLC bounds")
    return errors

def quality_report(frame: pd.DataFrame, *, time_column="time", expected_frequency="1h"):
    normalized = normalize_utc(frame, time_column) if not frame.empty else frame.copy()
    return {
        "rows": int(len(frame)),
        "duplicate_timestamps": duplicate_timestamps(normalized, time_column) if not frame.empty else [],
        "gaps": detect_gaps(normalized, time_column=time_column, expected_frequency=expected_frequency),
        "ohlc_errors": validate_ohlc(normalized) if {"open","high","low","close"}.issubset(normalized.columns) else [],
    }
