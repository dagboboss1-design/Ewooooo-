from __future__ import annotations
import httpx
import pandas as pd

class BiquoteCalendarClient:
    def __init__(self, endpoint: str, timeout: float = 20.0):
        self.endpoint, self.timeout = endpoint, timeout

    async def upcoming(self, importance="high", countries="US,EU,GB,JP,AU,CA,NZ,CH") -> pd.DataFrame:
        params = {"importance": importance, "countries": countries}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
        payload = response.json()
        events = payload if isinstance(payload, list) else payload.get("events")
        if not isinstance(events, list):
            raise ValueError("Unexpected biquote calendar schema: expected list or {'events': list}")
        rows = []
        for event in events:
            rows.append({
                "event_id": event.get("eventId", event.get("id")),
                "event_time": event.get("time", event.get("date")),
                "country": event.get("country"),
                "currency": event.get("currency"),
                "title": event.get("title", event.get("name")),
                "importance": event.get("importance"),
                "actual": event.get("actual"),
                "forecast": event.get("forecast"),
                "previous": event.get("previous"),
                "revised_previous": event.get("revisedPrevious"),
                "source": "biquote",
            })
        frame = pd.DataFrame(rows)
        if not frame.empty:
            frame["event_time"] = pd.to_datetime(frame["event_time"], utc=True, errors="coerce")
        return frame
