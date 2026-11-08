from __future__ import annotations

import base64
import binascii
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, ConfigDict

from forex_quant.config import Settings
from forex_quant.providers.oanda import OandaClient
from forex_quant.providers.twelve_data import TwelveDataClient
from forex_quant.trade_journal import create_trade, list_trades, update_trade, performance_summary

ROOT = Path(__file__).resolve().parent
ASSETS = [
    {"symbol": "EUR/USD", "label": "EUR/USD", "class": "forex"},
    {"symbol": "GBP/USD", "label": "GBP/USD", "class": "forex"},
    {"symbol": "USD/JPY", "label": "USD/JPY", "class": "forex"},
    {"symbol": "AUD/USD", "label": "AUD/USD", "class": "forex"},
    {"symbol": "USD/CAD", "label": "USD/CAD", "class": "forex"},
    {"symbol": "EUR/GBP", "label": "EUR/GBP", "class": "forex"},
    {"symbol": "AUD/NZD", "label": "AUD/NZD", "class": "forex"},
    {"symbol": "XAU/USD", "label": "XAU/USD", "class": "metal"},
    {"symbol": "XAG/USD", "label": "XAG/USD", "class": "metal"},
    {"symbol": "BTC/USD", "label": "BTC/USD", "class": "crypto"},
    {"symbol": "DXY", "label": "DXY", "class": "index"},
]
TIMEFRAMES = ["M5", "M15", "M30", "H1", "H4", "D1"]
INTERVALS = {"M5": "5min", "M15": "15min", "M30": "30min", "H1": "1h", "H4": "4h", "D1": "1day"}
app = FastAPI(title="Ewooooo Forex Quant Signal System", version="0.4.3")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class JournalCreate(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)
    side: str
    timeframe: str = Field(default="—", max_length=8)
    entry: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    setup_text: str = Field(min_length=1, max_length=10000)
    source: str = Field(default="ai", pattern="^(ai|manual)$")
    status: str = Field(default="open", pattern="^(open|skipped)$")

class JournalUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    exit_price: float | None = None
    pnl: float | None = None
    status: str | None = Field(default=None, pattern="^(open|closed|cancelled|skipped)$")
    notes: str | None = Field(default=None, max_length=4000)

class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    chart_image: str | None = Field(default=None, max_length=5_500_000)
    symbol: str = Field(default="EUR/USD", min_length=2, max_length=20)
    timeframe: str = Field(default="M15", pattern="^(M5|M15|M30|H1|H4|D1)$")


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
    connected = bool(settings.twelve_data_api_key) if settings.market_data_provider == "twelve_data" else bool(settings.oanda_account_id and selected_oanda_token(settings))
    return {
        "status": "credentials_configured" if connected else "awaiting_provider_credentials",
        "market_data_provider": settings.market_data_provider,
        "market_data_connected": connected,
        "ai_chat_configured": bool(settings.openai_api_key),
        "signal_engine_connected": False,
        "news_feed_connected": False,
        "execution_enabled": False,
        "message": "Provider credentials configured; quote requests still need validation." if connected else "Add the selected provider key privately on the server to enable live market data.",
    }


@app.get("/api/market")
async def market() -> dict[str, Any]:
    settings = get_settings()
    if settings.market_data_provider == "twelve_data":
        if not settings.twelve_data_api_key:
            return {"status": "awaiting_provider_credentials", "provider": "twelve_data", "as_of": None, "quotes": [], "unavailable": [{"symbol": a["symbol"], "reason": "TWELVE_DATA_API_KEY is not configured."} for a in ASSETS]}
        client = TwelveDataClient(settings.twelve_data_api_key)
        quotes, unavailable = [], []
        for asset in ASSETS:
            if asset["symbol"] == "DXY":
                unavailable.append({"symbol": "DXY", "reason": "DXY index feed is not configured; it is not being approximated."})
                continue
            try:
                quote = await client.quote(asset["symbol"])
                quote["label"] = asset["label"]
                quotes.append(quote)
            except (httpx.HTTPError, LookupError, ValueError) as exc:
                unavailable.append({"symbol": asset["symbol"], "reason": str(exc)[:240]})
        return {"status": "live" if quotes else "no_verified_quotes", "provider": "twelve_data", "as_of": max((q["time"] for q in quotes if q.get("time")), default=None), "quotes": quotes, "unavailable": unavailable}

    token = selected_oanda_token(settings)
    if not token or not settings.oanda_account_id:
        return {"status": "awaiting_provider_credentials", "provider": "oanda", "as_of": None, "quotes": [], "unavailable": [a["symbol"] for a in ASSETS], "message": "Configure OANDA credentials privately."}
    client = OandaClient(token=token, environment=settings.oanda_environment)
    quotes, unavailable = [], []
    for asset in ASSETS:
        if asset["symbol"] == "DXY":
            unavailable.append({"symbol": "DXY", "reason": "A dedicated DXY index data provider is not configured."})
            continue
        instrument = asset["symbol"].replace("/", "_")
        try:
            quote = await client.prices(settings.oanda_account_id, instrument)
            quote["label"] = asset["label"]
            quotes.append(quote)
        except (httpx.HTTPError, LookupError, ValueError) as exc:
            unavailable.append({"symbol": asset["symbol"], "reason": str(exc)[:240]})
    return {"status": "live" if quotes else "no_verified_quotes", "provider": "oanda", "as_of": max((q["time"] for q in quotes if q.get("time")), default=None), "quotes": quotes, "unavailable": unavailable}


@app.get("/api/market/candles")
async def market_candles(symbol: str = "EUR/USD", timeframe: str = "M15", outputsize: int = 300) -> dict[str, Any]:
    if symbol not in {a["symbol"] for a in ASSETS if a["symbol"] != "DXY"}:
        raise HTTPException(status_code=400, detail="Unsupported symbol.")
    if timeframe not in INTERVALS:
        raise HTTPException(status_code=400, detail="Unsupported timeframe.")
    if not 1 <= outputsize <= 500:
        raise HTTPException(status_code=400, detail="outputsize must be between 1 and 500.")
    settings = get_settings()
    try:
        if settings.market_data_provider == "twelve_data":
            if not settings.twelve_data_api_key:
                raise HTTPException(status_code=503, detail="TWELVE_DATA_API_KEY is not configured.")
            frame = await TwelveDataClient(settings.twelve_data_api_key).candles(symbol, INTERVALS[timeframe], outputsize)
        else:
            token = selected_oanda_token(settings)
            if not token or not settings.oanda_account_id:
                raise HTTPException(status_code=503, detail="OANDA credentials are not configured.")
            frame = await OandaClient(token, settings.oanda_environment).candles(symbol.replace("/", "_"), "D" if timeframe == "D1" else timeframe, outputsize)
    except HTTPException:
        raise
    except (httpx.HTTPError, LookupError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Market candle request failed: {str(exc)[:200]}")
    return {"symbol": symbol, "timeframe": timeframe, "provider": settings.market_data_provider, "candles": frame.to_dict(orient="records")}


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
    if payload.symbol not in {a["symbol"] for a in ASSETS if a["symbol"] != "DXY"}:
        raise HTTPException(status_code=400, detail="Unsupported analysis instrument.")
    candle_context = {"symbol": payload.symbol, "selected_timeframe": payload.timeframe, "provider": settings.market_data_provider, "daily_bias": "UNAVAILABLE", "daily_candles": [], "entry_candles": []}
    async def get_analysis_candles(tf: str, count: int):
        if settings.market_data_provider == "twelve_data":
            if not settings.twelve_data_api_key:
                raise LookupError("Twelve Data API key is not configured.")
            return await TwelveDataClient(settings.twelve_data_api_key).candles(payload.symbol, INTERVALS[tf], count)
        token = selected_oanda_token(settings)
        if not token or not settings.oanda_account_id:
            raise LookupError("OANDA credentials are not configured.")
        granularity = "D" if tf == "D1" else tf
        return await OandaClient(token, settings.oanda_environment).candles(payload.symbol.replace("/", "_"), granularity, count)
    try:
        daily = await get_analysis_candles("D1", 80)
        daily_rows = daily.to_dict(orient="records")
        completed_daily = daily_rows[:-1] if settings.market_data_provider == "twelve_data" else daily_rows
        closes = [float(row["close"]) for row in completed_daily if row.get("close") is not None]
        if len(closes) >= 25:
            alpha = 2 / 21
            ema = closes[0]
            ema_values = []
            for close in closes:
                ema = close * alpha + ema * (1 - alpha)
                ema_values.append(ema)
            latest, ema20 = closes[-1], ema_values[-1]
            prior_ema = ema_values[max(0, len(ema_values) - 6)]
            bias = "BULLISH" if latest > ema20 and ema20 > prior_ema else "BEARISH" if latest < ema20 and ema20 < prior_ema else "NEUTRAL"
            candle_context.update(daily_bias=bias, daily_last_completed_close=latest, daily_ema20=ema20, daily_completed_bars=len(closes))
        candle_context["daily_candles"] = completed_daily[-60:]
        if payload.timeframe != "D1":
            entry = await get_analysis_candles(payload.timeframe, 100)
            candle_context["entry_candles"] = entry.to_dict(orient="records")[-80:]
        else:
            candle_context["entry_candles"] = completed_daily[-80:]
        candle_context["status"] = "verified_candles_loaded"
    except (httpx.HTTPError, LookupError, ValueError, KeyError) as exc:
        candle_context["status"] = "unavailable"
        candle_context["error"] = str(exc)[:200]
    context_text = "Verified OHLC candle context: " + str(candle_context) + ". Use only observed values. If unavailable, state that clearly and never invent prices or bias. D1 bias is contextual, not a guaranteed direction. Explain conflicts between D1 and the selected timeframe; prefer WAIT when evidence conflicts."
    instructions = (
        "You are Ewooooo AI, a specialist trading education and market-analysis assistant. "
        "Answer broad questions about forex, metals, crypto, indices, technical/fundamental analysis, "
        "risk, strategies, psychology and news. Inspect attached chart images, but state levels/timeframes "
        "only when legible. Distinguish observations from inference. For setups, say BUY, SELL or WAIT; "
        "if evidence is insufficient, say WAIT. Include instrument, timeframe, entry, stop, targets, "
        "risk/reward, rationale, invalidation and risks only when grounded. Never fabricate live prices, "
        "candles, news, indicators or backtests. Confidence is not a calibrated win probability. Never "
        "guarantee profit. Never place or manage orders; execution is disabled. Do not request credentials. "
        + context_text
    )
    content: list[dict[str, Any]] = [{"type": "input_text", "text": message}]
    if image_url:
        content.append({"type": "input_image", "image_url": image_url})
    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post("https://api.openai.com/v1/responses", headers={"Authorization": f"Bearer {settings.openai_api_key}"}, json={"model": settings.openai_model, "instructions": instructions, "input": [{"role": "user", "content": content}], "max_output_tokens": 1200})
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401:
            raise HTTPException(status_code=502, detail="The server's AI credential was rejected.")
        if exc.response.status_code == 429:
            raise HTTPException(status_code=503, detail="AI service rate limit or API quota reached.")
        raise HTTPException(status_code=502, detail="AI service returned an error.")
    except (httpx.HTTPError, ValueError):
        raise HTTPException(status_code=502, detail="Could not reach the AI service.")
    answer = data.get("output_text") or "\n".join(item.get("text", "") for output in data.get("output", []) for item in output.get("content", []) if item.get("type") == "output_text").strip()
    if not answer:
        raise HTTPException(status_code=502, detail="AI service returned no text.")
    return {"answer": answer, "model": settings.openai_model, "market_data_status": candle_context.get("status"), "daily_bias": candle_context.get("daily_bias"), "symbol": payload.symbol, "timeframe": payload.timeframe, "chart_received": bool(image_url)}

@app.get("/api/journal")
async def journal_list():
    trades = list_trades(get_settings().database_url)
    closed = [t for t in trades if t["status"] == "closed"]
    return {"trades": trades, "count": len(trades), "closed_count": len(closed),
            "realized_pnl": sum((t["pnl"] or 0) for t in closed), "analytics": performance_summary(trades)}

@app.post("/api/journal", status_code=201)
async def journal_create(payload: JournalCreate):
    symbol = payload.symbol.strip().upper()
    if symbol not in {a["symbol"] for a in ASSETS}:
        raise HTTPException(status_code=400, detail="Unsupported journal instrument.")
    side = payload.side.upper()
    if side not in {"BUY", "SELL"}:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL.")
    values = payload.model_dump()
    values.update(symbol=symbol, side=side, status=payload.status, exit_price=None, pnl=None, notes="")
    trade = create_trade(get_settings().database_url, values)
    return {"trade": trade, "message": "Saved to paper journal. No broker order was placed."}

@app.patch("/api/journal/{trade_id}")
async def journal_update(trade_id: str, payload: JournalUpdate):
    values = payload.model_dump(exclude_unset=True)
    if not values:
        raise HTTPException(status_code=400, detail="No journal changes supplied.")
    if values.get("exit_price") is not None and values["exit_price"] <= 0:
        raise HTTPException(status_code=400, detail="Exit price must be positive.")
    trade = update_trade(get_settings().database_url, trade_id, values)
    if trade is None:
        raise HTTPException(status_code=404, detail="Journal trade not found.")
    return {"trade": trade}

@app.get("/api/signals")
async def signals() -> dict[str, Any]:
    return {"status": "no_signal_feed", "signals": []}


@app.get("/api/news")
async def news() -> dict[str, Any]:
    return {"status": "no_news_feed", "events": []}
