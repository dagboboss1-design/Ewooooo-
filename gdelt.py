from __future__ import annotations
from datetime import datetime, timedelta, timezone
import httpx
import pandas as pd

class GdeltClient:
    def __init__(self, endpoint: str, timeout: float = 30.0):
        self.endpoint, self.timeout = endpoint, timeout

    async def articles(self, query: str, lookback_minutes: int = 180) -> pd.DataFrame:
        end = datetime.now(timezone.utc)
        start = end - timedelta(minutes=lookback_minutes)
        params = {
            "query": query, "mode": "ArtList", "format": "json",
            "startdatetime": start.strftime("%Y%m%d%H%M%S"),
            "enddatetime": end.strftime("%Y%m%d%H%M%S"),
            "maxrecords": 250, "sort": "DateDesc",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
        payload = response.json()
        rows = []
        for article in payload.get("articles", []):
            rows.append({
                "published_at": pd.to_datetime(article.get("seendate"), utc=True, errors="coerce"),
                "title": article.get("title"),
                "url": article.get("url"),
                "domain": article.get("domain"),
                "language": article.get("language"),
                "source_country": article.get("sourcecountry"),
                "source": "gdelt",
            })
        return pd.DataFrame(rows)
