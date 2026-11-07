from __future__ import annotations
from datetime import date
import lzma
import struct
import httpx
import pandas as pd

BASE = "https://datafeed.dukascopy.com/datafeed"

def decode_bi5(payload: bytes, instrument: str, day: date, hour: int) -> pd.DataFrame:
    raw = lzma.decompress(payload)
    record = struct.Struct(">IIIff")
    if len(raw) % record.size:
        raise ValueError(f"Unexpected Dukascopy tick payload length: {len(raw)}")
    rows = []
    from datetime import datetime, timedelta, timezone
    hour_start = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    for offset in range(0, len(raw), record.size):
        millis, ask_i, bid_i, ask_vol, bid_vol = record.unpack_from(raw, offset)
        # Standard FX price scale is 1e-5; JPY pairs commonly use 1e-3.
        scale = 1000 if instrument.endswith("JPY") else 100000
        rows.append({
            "time": hour_start + timedelta(milliseconds=millis),
            "instrument": instrument,
            "ask": ask_i / scale,
            "bid": bid_i / scale,
            "ask_volume": float(ask_vol),
            "bid_volume": float(bid_vol),
            "mid": ((ask_i + bid_i) / 2) / scale,
            "spread": (ask_i - bid_i) / scale,
            "source": "dukascopy",
        })
    return pd.DataFrame(rows)

class DukascopyClient:
    async def ticks(self, instrument: str, day: date, hour: int) -> pd.DataFrame:
        if not 0 <= hour <= 23:
            raise ValueError("hour must be 0..23")
        url = (f"{BASE}/{instrument}/{day.year}/{day.month-1:02d}/{day.day:02d}/"
               f"{hour:02d}h_ticks.bi5")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return pd.DataFrame(columns=["time","instrument","ask","bid","ask_volume","bid_volume","mid","spread","source"])
            response.raise_for_status()
        return decode_bi5(response.content, instrument, day, hour)
