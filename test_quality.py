import pandas as pd
from forex_quant.quality import normalize_utc, duplicate_timestamps, detect_gaps, validate_ohlc

def test_normalize_utc_and_sort():
    df = pd.DataFrame({"time": ["2024-01-01T01:00:00+01:00", "2024-01-01T00:00:00Z"]})
    out = normalize_utc(df)
    assert str(out.time.iloc[0]) == "2024-01-01 00:00:00+00:00"

def test_duplicate_detection():
    df = pd.DataFrame({"time": ["2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z"]})
    assert len(duplicate_timestamps(df)) == 1

def test_gap_detection():
    df = pd.DataFrame({"time": ["2024-01-01T00:00:00Z", "2024-01-01T02:00:00Z"]})
    assert len(detect_gaps(df, expected_frequency="1h")) == 1

def test_ohlc_bounds():
    good = pd.DataFrame({"open":[1.0],"high":[1.2],"low":[0.9],"close":[1.1]})
    bad = pd.DataFrame({"open":[1.0],"high":[0.8],"low":[0.9],"close":[1.1]})
    assert validate_ohlc(good) == []
    assert validate_ohlc(bad)
