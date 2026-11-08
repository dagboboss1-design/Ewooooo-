from __future__ import annotations

import asyncio
from collections import deque
import os
import time

import httpx
import pandas as pd


# Twelve Data Basic allows 8 API credits/minute. Reserve one credit of headroom
# and enforce a shared process-wide budget so the watchlist cannot flood the API.
_REQUEST_TIMESTAMPS: deque[float] = deque()
_REQUEST_LOCK = asyncio.Lock()
_RATE_LIMITED_UNTIL = 0.0
_CREDITS_PER_MINUTE = max(1, min(600, int(os.getenv("TWELVE_DATA_CREDITS_PER_MINUTE", "7"))))


class TwelveDataClient:
    """Read-only Twelve Data market-data client. Never places orders."""

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str, timeout: float = 20.0):
        if not api_key:
            raise ValueError("Twelve Data API key is required")
        self.api_key = api_key
        self.timeout = timeout

    async def _get(self, endpoint: str, params: dict) -> dict:
        global _RATE_LIMITED_UNTIL
        async with _REQUEST_LOCK:
            now = time.monotonic()
            while _REQUEST_TIMESTAMPS and now - _REQUEST_TIMESTAMPS[0] >= 60:
                _REQUEST_TIMESTAMPS.popleft()
            if now < _RATE_LIMITED_UNTIL:
                raise LookupError("Twelve Data rate limit cooldown is active; retry after the next minute.")
            if len(_REQUEST_TIMESTAMPS) >= _CREDITS_PER_MINUTE:
                raise LookupError("Local Twelve Data quota guard reached; preserving the remaining Basic-plan credits.")
            _REQUEST_TIMESTAMPS.append(now)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/{endpoint}",
                params={**params, "apikey": self.api_key},
            )
            if response.status_code == 429:
                async with _REQUEST_LOCK:
                    _RATE_LIMITED_UNTIL = time.monotonic() + 60
                raise LookupError("Twelve Data returned HTTP 429 (API credits exhausted); requests paused for 60 seconds.")
            response.raise_for_status()
            payload = response.json()
        if payload.get("status") == "error" or payload.get("code"):
            raise LookupError(str(payload.get("message", "Twelve Data returned an error"))[:240])
        return payload

    async def quote(self, symbol: str) -> dict:
        payload = await self._get("quote", {"symbol": symbol})
        close = payload.get("close") or payload.get("price")
        if close in (None, ""):
            raise LookupError(f"No current quote returned for {symbol}")
        price = float(close)
        bid = float(payload["bid"]) if payload.get("bid") not in (None, "") else None
        ask = float(payload["ask"]) if payload.get("ask") not in (None, "") else None
        return {
            "symbol": symbol.replace("/", "_"),
            "bid": bid,
            "ask": ask,
            "mid": price,
            "spread": ask - bid if bid is not None and ask is not None else None,
            "time": payload.get("datetime") or payload.get("timestamp"),
            "tradeable": False,
            "status": "live",
            "source": "twelve_data",
        }

    async def candles(self, symbol: str, interval: str = "15min", outputsize: int = 500) -> pd.DataFrame:
        if not 1 <= outputsize <= 5000:
            raise ValueError("outputsize must be between 1 and 5000")
        payload = await self._get(
            "time_series",
            {"symbol": symbol, "interval": interval, "outputsize": outputsize, "order": "ASC"},
        )
        rows = []
        for candle in payload.get("values", []):
            rows.append({
                "time": candle["datetime"],
                "instrument": symbol.replace("/", "_"),
                "granularity": interval,
                "open": float(candle["open"]),
                "high": float(candle["high"]),
                "low": float(candle["low"]),
                "close": float(candle["close"]),
                "volume": float(candle["volume"]) if candle.get("volume") not in (None, "") else None,
                "source": "twelve_data",
            })
        if not rows:
            raise LookupError(f"No candles returned for {symbol} at {interval}")
        return pd.DataFrame(rows)
