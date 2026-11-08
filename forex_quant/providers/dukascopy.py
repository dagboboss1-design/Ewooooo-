from __future__ import annotations
from datetime import date, datetime, timedelta, timezone
import asyncio
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
        # Dukascopy tick prices use instrument-specific point scales.
        if instrument.startswith(("XAU", "XAG")):
            scale = 1000
        else:
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
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url)
            if response.status_code == 404:
                return pd.DataFrame(columns=["time","instrument","ask","bid","ask_volume","bid_volume","mid","spread","source"])
            response.raise_for_status()
        return decode_bi5(response.content, instrument, day, hour)


    async def candles(self, instrument: str, timeframe: str, outputsize: int = 300) -> pd.DataFrame:
        """Build completed OHLC bars from public hourly tick files.

        This is a historical recovery path, not a guaranteed live quote feed.
        Only intraday FX/metal bars are supported; insufficient/stale history
        raises so callers can keep the signal at WAIT.
        """
        rules = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h"}
        if timeframe not in rules:
            raise ValueError("Dukascopy historical fallback supports intraday timeframes only.")
        if not (instrument.endswith(("USD", "JPY", "CAD", "CHF", "GBP", "AUD", "NZD")) or instrument.startswith(("XAU", "XAG"))):
            raise ValueError("Instrument is not enabled for the Dukascopy historical fallback.")
        now = datetime.now(timezone.utc)
        end_hour = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)
        # Fetch a bounded recent window; the public archive can lag and may omit closed hours.
        history_hours = 72 if timeframe == "H4" else 36
        hours = [end_hour - timedelta(hours=i) for i in range(history_hours - 1, -1, -1)]
        semaphore = asyncio.Semaphore(5)

        async def load_hour(stamp):
            async with semaphore:
                try:
                    return await self.ticks(instrument, stamp.date(), stamp.hour)
                except (httpx.HTTPError, lzma.LZMAError, ValueError, struct.error):
                    return pd.DataFrame()

        frames = await asyncio.gather(*(load_hour(stamp) for stamp in hours))
        frames = [frame for frame in frames if not frame.empty]
        if not frames:
            raise LookupError("Dukascopy returned no recent historical ticks.")
        ticks = pd.concat(frames, ignore_index=True)
        ticks = ticks.dropna(subset=["time", "mid"]).sort_values("time")
        if ticks.empty:
            raise LookupError("Dukascopy returned no usable ticks.")
        latest = ticks["time"].max()
        if (now - latest.to_pydatetime()).total_seconds() > 3 * 3600:
            raise LookupError("Dukascopy backup data is older than three hours; refusing stale candles.")
        bars = (ticks.set_index("time")["mid"]
                .resample(rules[timeframe])
                .ohlc()
                .dropna())
        duration = pd.Timedelta(rules[timeframe])
        bars = bars[(bars.index + duration) <= pd.Timestamp(now)]
        minimum_bars = 18 if timeframe == "H4" else min(30, outputsize)
        if len(bars) < minimum_bars:
            raise LookupError(f"Only {len(bars)} completed {timeframe} bars are available; at least {minimum_bars} are required.")
        bars = bars.tail(outputsize).reset_index()
        bars.columns = ["time", "open", "high", "low", "close"]
        bars["time"] = bars["time"].map(lambda value: value.isoformat())
        bars["instrument"] = instrument
        bars["granularity"] = timeframe
        bars["volume"] = None
        bars["source"] = "dukascopy_historical"
        return bars[["time", "instrument", "granularity", "open", "high", "low", "close", "volume", "source"]]
