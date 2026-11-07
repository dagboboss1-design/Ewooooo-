from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent

# These are watchlist definitions, not claims that a provider currently streams them.
ASSETS = [
    {"symbol": "EUR_USD", "label": "EUR/USD", "class": "forex"},
    {"symbol": "GBP_USD", "label": "GBP/USD", "class": "forex"},
    {"symbol": "USD_JPY", "label": "USD/JPY", "class": "forex"},
    {"symbol": "AUD_USD", "label": "AUD/USD", "class": "forex"},
    {"symbol": "USD_CAD", "label": "USD/CAD", "class": "forex"},
    {"symbol": "EUR_GBP", "label": "EUR/GBP", "class": "forex"},
    {"symbol": "AUD_NZD", "label": "AUD/NZD", "class": "forex"},
    {"symbol": "XAU_USD", "label": "XAU/USD", "class": "metal"},
    {"symbol": "XAG_USD", "label": "XAG/USD", "class": "metal"},
    {"symbol": "BTC_USD", "label": "BTC/USD", "class": "crypto"},
    {"symbol": "DXY", "label": "DXY", "class": "index"},
]
TIMEFRAMES = ["M5", "M15", "M30", "H1", "H4"]

app = FastAPI(
    title="Ewooooo Forex Quant Signal System",
    version="0.4.0",
    description="Phase 4 responsive dashboard API. Market values remain empty until verified feeds are connected.",
)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/dashboard/config")
async def dashboard_config() -> dict[str, Any]:
    return {"assets": ASSETS, "timeframes": TIMEFRAMES, "default_timeframe": "M15"}


@app.get("/api/dashboard/status")
async def dashboard_status() -> dict[str, Any]:
    return {
        "status": "awaiting_provider_connection",
        "market_data_connected": False,
        "signal_engine_connected": False,
        "news_feed_connected": False,
        "execution_enabled": False,
        "message": "Dashboard is running. Connect and validate provider feeds before displaying live values.",
    }


@app.get("/api/market")
async def market() -> dict[str, Any]:
    return {
        "status": "no_verified_feed",
        "as_of": None,
        "quotes": [],
        "message": "No live quotes are available yet; no sample prices are substituted.",
    }


@app.get("/api/signals")
async def signals() -> dict[str, Any]:
    return {"status": "no_signal_feed", "signals": []}


@app.get("/api/news")
async def news() -> dict[str, Any]:
    return {"status": "no_news_feed", "events": []}
