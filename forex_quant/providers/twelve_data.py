from __future__ import annotations

import httpx
import pandas as pd


class TwelveDataClient:
    """Read-only Twelve Data market-data client. Never places orders."""

    BASE_URL = "https://api.twelvedata.com"

    def __init__(self, api_key: str, timeout: float = 20.0):
        if not api_key:
            raise ValueError("Twelve Data API key is required")
        self.api_key = api_key
        self.timeout = timeout

    async def _get(self, endpoint: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.BASE_URL}/{endpoint}",
                params={**params, "apikey": self.api_key},
            )
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
