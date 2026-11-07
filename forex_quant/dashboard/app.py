from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from forex_quant.config import Settings
from forex_quant.providers.oanda import OandaClient

ROOT = Path(__file__).resolve().parent
ASSETS = [
    {"symbol": "EUR_USD", "label": "EUR/USD", "class": "forex", "provider": "oanda"},
    {"symbol": "GBP_USD", "label": "GBP/USD", "class": "forex", "provider": "oanda"},
    {"symbol": "USD_JPY", "label": "USD/JPY", "class": "forex", "provider": "oanda"},
    {"symbol": "AUD_USD", "label": "AUD/USD", "class": "forex", "provider": "oanda"},
    {"symbol": "USD_CAD", "label": "USD/CAD", "class": "forex", "provider": "oanda"},
    {"symbol": "EUR_GBP", "label": "EUR/GBP", "class": "forex", "provider": "oanda"},
    {"symbol": "AUD_NZD", "label": "AUD/NZD", "class": "forex", "provider": "oanda"},
    {"symbol": "XAU_USD", "label": "XAU/USD", "class": "metal", "provider": "oanda"},
    {"symbol": "XAG_USD", "label": "XAG/USD", "class": "metal", "provider": "oanda"},
    {"symbol": "BTC_USD", "label": "BTC/USD", "class": "crypto", "provider": "oanda"},
    {"symbol": "DXY", "label": "DXY", "class": "index", "provider": "external_index_feed"},
]
TIMEFRAMES = ["M5", "M15", "M30", "H1", "H4"]
app = FastAPI(title="Ewooooo Forex Quant Signal System", version="0.4.1")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


def get_settings() -> Settings:
    return Settings()


def selected_oanda_token(settings: Settings) -> str:
    return settings.oanda_live_token if settings.oanda_environment == "live" else settings.oanda_practice_token


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/api/dashboard/config")
async def dashboard_config() -> dict[str, Any]:
    return {"assets": ASSETS, "timeframes": TIMEFRAMES, "default_timeframe": "M15"}


@app.get("/api/dashboard/status")
async def dashboard_status() -> dict[str, Any]:
    settings = get_settings()
    connected = bool(settings.oanda_account_id and selected_oanda_token(settings))
    return {
        "status": "credentials_configured" if connected else "awaiting_provider_credentials",
        "market_data_connected": connected,
        "signal_engine_connected": False,
        "news_feed_connected": False,
        "execution_enabled": False,
        "message": "OANDA credentials configured; each instrument quote is validated at request time." if connected else "Add OANDA account ID and token as server environment secrets to enable live quotes.",
    }


@app.get("/api/market")
async def market() -> dict[str, Any]:
    settings = get_settings()
    token = selected_oanda_token(settings)
    if not token or not settings.oanda_account_id:
        return {"status": "awaiting_provider_credentials", "as_of": None, "quotes": [], "unavailable": [a["symbol"] for a in ASSETS], "message": "Configure OANDA credentials securely on the server to fetch current prices."}

    client = OandaClient(token=token, environment=settings.oanda_environment)
    quotes, unavailable = [], []
    for asset in ASSETS:
        if asset["provider"] != "oanda":
            unavailable.append({"symbol": asset["symbol"], "reason": "A dedicated DXY index data provider is not configured."})
            continue
        try:
            quote = await client.prices(settings.oanda_account_id, asset["symbol"])
            quote["label"] = asset["label"]
            quotes.append(quote)
        except (httpx.HTTPError, LookupError, ValueError) as exc:
            unavailable.append({"symbol": asset["symbol"], "reason": str(exc)[:240]})
    return {"status": "live" if quotes else "no_verified_quotes", "as_of": max((q["time"] for q in quotes if q.get("time")), default=None), "quotes": quotes, "unavailable": unavailable, "environment": settings.oanda_environment}


@app.get("/api/signals")
async def signals() -> dict[str, Any]:
    return {"status": "no_signal_feed", "signals": []}


@app.get("/api/news")
async def news() -> dict[str, Any]:
    return {"status": "no_news_feed", "events": []}
