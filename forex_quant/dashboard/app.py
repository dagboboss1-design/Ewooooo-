from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
import httpx

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
app = FastAPI(title="Ewooooo Forex Quant Signal System", version="0.4.2")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    chart_image: str | None = Field(default=None, max_length=5_500_000)


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
        "ai_chat_configured": bool(settings.openai_api_key),
        "signal_engine_connected": False,
        "news_feed_connected": False,
        "execution_enabled": False,
        "message": "Market-data credentials configured; quotes are validated at request time." if connected else "Add a supported market-data provider credential securely on the server to enable live quotes.",
    }


@app.get("/api/market")
async def market() -> dict[str, Any]:
    settings = get_settings()
    token = selected_oanda_token(settings)
    if not token or not settings.oanda_account_id:
        return {"status": "awaiting_provider_credentials", "as_of": None, "quotes": [], "unavailable": [a["symbol"] for a in ASSETS], "message": "Configure market-data credentials securely on the server to fetch current prices."}

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


@app.post("/api/ai/chat")
async def ai_chat(payload: ChatRequest) -> dict[str, Any]:
    settings = get_settings()
    if not settings.openai_api_key:
        raise HTTPException(status_code=503, detail="AI chat is not configured yet. Add OPENAI_API_KEY to the server environment.")
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=422, detail="Please enter a trading question.")

    image_url = None
    if payload.chart_image:
        try:
            header, encoded = payload.chart_image.split(",", 1)
            if header not in {"data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"}:
                raise ValueError("Unsupported chart image type.")
            image_bytes = base64.b64decode(encoded, validate=True)
            if len(image_bytes) > 4_000_000:
                raise ValueError("Chart image must be 4 MB or smaller.")
            image_url = payload.chart_image
        except (ValueError, binascii.Error):
            raise HTTPException(status_code=400, detail="Upload a valid PNG, JPEG or WebP chart image under 4 MB.")

    try:
        market_context = await market()
    except Exception:
        market_context = {"status": "unavailable", "quotes": [], "unavailable": ["Market context could not be retrieved."]}
    verified_quotes = market_context.get("quotes", [])
    context_text = (
        "Verified market snapshot (only use these prices if present): "
        + (str(verified_quotes) if verified_quotes else "No verified live quotes are connected. Do not invent prices.")
        + ". Market feed status: " + str(market_context.get("status"))
        + ". News feed and automated signal feed are not yet connected. Do not pretend otherwise."
    )
    instructions = (
        "You are Ewooooo AI, a specialist trading education and market-analysis assistant. "
        "Answer broad trading questions clearly and helpfully: forex, metals, crypto, indices, "
        "technical/fundamental analysis, price action, risk, strategies, psychology and news. "
        "When a chart image is attached, inspect only visible evidence and state the timeframe "
        "or price levels only when legible. Distinguish observation from inference. "
        "When asked for a trade setup, give BUY, SELL or WAIT only when evidence supports it; "
        "otherwise say WAIT/insufficient data. Include instrument, timeframe, entry zone, stop, "
        "targets, risk/reward, rationale, invalidation and key risks when these can be grounded. "
        "Never fabricate live prices, candles, news, indicators or backtest results. "
        "If no verified live quotes are provided, say so and ask for a chart screenshot or data. "
        "Confidence is analytical conviction, not a calibrated win probability. Never guarantee "
        "profit or claim superiority over every AI. Explain that trading carries risk. "
        "Never place, route, modify or close orders; execution is disabled. "
        "Do not ask users to reveal API keys or credentials. " + context_text
    )
    content: list[dict[str, Any]] = [{"type": "input_text", "text": message}]
    if image_url:
        content.append({"type": "input_image", "image_url": image_url})
    request_body = {
        "model": settings.openai_model,
        "instructions": instructions,
        "input": [{"role": "user", "content": content}],
        "max_output_tokens": 1200,
    }
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://api.openai.com/v1/responses",
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                json=request_body,
            )
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(status_code=502, detail="The server's AI credential was rejected. Check OPENAI_API_KEY in the hosting environment.")
        if exc.response.status_code == 429:
            raise HTTPException(status_code=503, detail="The AI service is temporarily rate-limited or out of API quota. Check API billing and limits.")
        raise HTTPException(status_code=502, detail="The AI service returned an error. Please try again.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Could not reach the AI service. Please try again.")
    answer = data.get("output_text")
    if not answer:
        answer = "\n".join(
            item.get("text", "")
            for output in data.get("output", [])
            for item in output.get("content", [])
            if item.get("type") == "output_text"
        ).strip()
    if not answer:
        raise HTTPException(status_code=502, detail="The AI service returned no text. Please try again.")
    return {"answer": answer, "model": settings.openai_model, "market_data_status": market_context.get("status"), "chart_received": bool(image_url)}


@app.get("/api/signals")
async def signals() -> dict[str, Any]:
    return {"status": "no_signal_feed", "signals": []}


@app.get("/api/news")
async def news() -> dict[str, Any]:
    return {"status": "no_news_feed", "events": []}
