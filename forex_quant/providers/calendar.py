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

    async def event_history(self, event_id: str) -> list[dict]:
        """Fetch historical actual/forecast observations for one event."""
        from urllib.parse import quote
        if not event_id or len(event_id) > 160:
            raise ValueError("Invalid calendar event id.")
        base = self.endpoint.rsplit("/", 1)[0]
        url = f"{base}/{quote(event_id, safe='')}/history"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(url)
            response.raise_for_status()
        payload = response.json()
        rows = payload if isinstance(payload, list) else payload.get("history", payload.get("events"))
        if not isinstance(rows, list):
            raise ValueError("Unexpected biquote history schema: expected list or {'history': list}")
        return [{"event_time": row.get("time", row.get("date")), "actual": row.get("actual"), "forecast": row.get("forecast"), "previous": row.get("previous"), "revised_previous": row.get("revisedPrevious")} for row in rows if isinstance(row, dict)]
