from __future__ import annotations
import httpx
import pandas as pd

class OandaClient:
    BASE_URLS = {
        "practice": "https://api-fxpractice.oanda.com",
        "live": "https://api-fxtrade.oanda.com",
    }

    def __init__(self, token: str, environment: str = "practice", timeout: float = 20.0):
        if environment not in self.BASE_URLS:
            raise ValueError("environment must be practice or live")
        if not token:
            raise ValueError("OANDA token is required")
        self.base_url = self.BASE_URLS[environment]
        self.token = token
        self.timeout = timeout

    async def candles(self, instrument: str, granularity="H1", count=500, price="MBA") -> pd.DataFrame:
        if count < 1 or count > 5000:
            raise ValueError("count must be between 1 and 5000")
        url = f"{self.base_url}/v3/instruments/{instrument}/candles"
        headers = {"Authorization": f"Bearer {self.token}", "Accept-Datetime-Format": "RFC3339"}
        params = {"granularity": granularity, "count": count, "price": price}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
        payload = response.json()
        rows = []
        for candle in payload.get("candles", []):
            if not candle.get("complete", False):
                continue
            mid = candle.get("mid") or {}
            bid = candle.get("bid") or {}
            ask = candle.get("ask") or {}
            rows.append({
                "time": candle["time"], "instrument": instrument, "granularity": granularity,
                "open": float(mid["o"]) if mid else None,
                "high": float(mid["h"]) if mid else None,
                "low": float(mid["l"]) if mid else None,
                "close": float(mid["c"]) if mid else None,
                "volume": int(candle.get("volume", 0)),
                "bid_close": float(bid["c"]) if bid else None,
                "ask_close": float(ask["c"]) if ask else None,
                "spread_close": (float(ask["c"]) - float(bid["c"])) if ask and bid else None,
                "source": "oanda",
            })
        return pd.DataFrame(rows)
