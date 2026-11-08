from __future__ import annotations

import base64
import binascii
import json
from math import isfinite
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
from forex_quant.providers.calendar import BiquoteCalendarClient
from forex_quant.providers.gdelt import GdeltClient
from forex_quant.trade_journal import create_trade, list_trades, update_trade, performance_summary
from forex_quant.signals import generate_signal, RiskPolicy
from forex_quant.alerts import AlertDispatcher
from forex_quant.news_spike import tick_spike_score, spread_guard, impacted_instruments

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

class SignalScanRequest(BaseModel):
    symbol: str = Field(min_length=2, max_length=20)
    timeframe: str = Field(default="M15", pattern="^(M5|M15|M30|H1|H4|D1)$")
    equity: float = Field(gt=0)
    quote_to_account_rate: float = Field(gt=0)
    daily_loss_fraction: float = Field(default=0, ge=0, lt=1)
    weekly_loss_fraction: float = Field(default=0, ge=0, lt=1)
    consecutive_losses: int = Field(default=0, ge=0)
    kill_switch: bool = False


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=6000)
    chart_image: str | None = Field(default=None, max_length=5_500_000)
    symbol: str = Field(default="EUR/USD", min_length=2, max_length=20)
    timeframe: str = Field(default="M15", pattern="^(M5|M15|M30|H1|H4|D1)$")



def offline_trading_answer(message: str, symbol: str, timeframe: str, chart_attached: bool) -> str:
    """Deterministic educational fallback; does not claim live market analysis."""
    q = message.lower()
    if any(w in q for w in ("risk", "lot size", "position size", "0.5%")):
        answer = ("RISK MANAGEMENT\\nAt 0.5% initial risk, planned cash risk = account equity × 0.005. "
                  "Position size depends on stop distance, pip/tick value and quote-to-account conversion. "
                  "Verify contract specifications and costs; never assume a universal lot size. "
                  "System limits: 2% daily loss, 5% weekly loss and a consecutive-loss pause.")
    elif any(w in q for w in ("rsi", "macd", "bollinger", "indicator")):
        answer = ("INDICATORS\\nRSI measures recent momentum; overbought/oversold readings are not automatic reversals. "
                  "MACD compares moving averages to describe momentum. Bollinger Bands show price relative to a "
                  "moving average and volatility. Combine indicators with market structure and risk controls.")
    elif any(w in q for w in ("stop loss", "take profit", "risk reward", "risk/reward")):
        answer = ("STOPS & TARGETS\\nA stop-loss marks where the trade idea is invalidated; a take-profit is a planned exit. "
                  "Risk/reward = potential reward divided by amount risked. A 2:1 target does not imply a 2-in-3 "
                  "chance of winning. Define invalidation before entry.")
    elif any(w in q for w in ("trend", "support", "resistance", "market structure")):
        answer = ("MARKET STRUCTURE\\nAn uptrend typically forms higher highs and higher lows; a downtrend forms "
                  "lower highs and lower lows. Support and resistance are reaction zones, not guaranteed barriers. "
                  "Wait for confirmation and define invalidation.")
    elif any(w in q for w in ("signal", "buy", "sell", "entry", "setup", "analyse", "analyze")):
        answer = (f"SETUP CHECK · {symbol} · {timeframe}\\nOffline mode cannot inspect live prices or calculate a "
                  "verified entry. Check completed candles, D1 bias, H4 context, spread and news risk. Require "
                  "independent evidence and clear invalidation. If evidence conflicts or data is missing, WAIT.")
    elif any(w in q for w in ("hello", "hi", "hey")):
        answer = ("Hello! I'm Ewooooo's offline trading helper. Ask about forex basics, indicators, trends, "
                  "stop-losses, position sizing or risk management.")
    else:
        answer = ("OFFLINE GUIDE\\nI can answer common educational questions about forex, indicators, market "
                  "structure, trade planning and risk management. This is a limited built-in guide, not a "
                  "general-purpose AI model. Add the OpenAI key privately for broader conversational answers.")
    if chart_attached:
        answer += ("\\n\\nCHART NOTE: The image was received, but offline mode cannot perform visual chart "
                   "recognition. I will not invent levels or claim to have analysed it.")
    return answer + ("\\n\\nDATA STATUS: Live prices and candles are not verified. Educational guidance only. "
                     "Execution remains OFF.")


def get_settings() -> Settings:
    return Settings()


def selected_oanda_token(settings: Settings) -> str:
    return settings.oanda_live_token if settings.oanda_environment == "live" else settings.oanda_practice_token


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard() -> str:
    return (ROOT / "static" / "index.html").read_text(encoding="utf-8")


@app.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness probe: confirms the ASGI process can answer HTTP requests."""
    return {"status": "ok"}


@app.get("/readyz")
async def readyz() -> dict[str, Any]:
    """Readiness/configuration probe; missing optional credentials do not crash startup."""
    settings = get_settings()
    market_configured = (
        bool(settings.twelve_data_api_key)
        if settings.market_data_provider == "twelve_data"
        else bool(settings.oanda_account_id and selected_oanda_token(settings))
    )
    return {
        "status": "ready",
        "market_data_configured": market_configured,
        "ai_configured": bool(settings.cloudflare_worker_url or settings.pollinations_api_key or settings.openai_api_key),
        "execution_enabled": False,
    }


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
        "ai_chat_configured": bool(settings.cloudflare_worker_url or settings.pollinations_api_key or settings.openai_api_key),
        "ai_provider_priority": ["cloudflare_worker", "pollinations", "openai_legacy", "offline"],
        "ai_provider_configured": ("cloudflare_worker" if settings.cloudflare_worker_url else "pollinations" if settings.pollinations_api_key else "openai_legacy" if settings.openai_api_key else "offline"),
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
    message = payload.message.strip()
    if not message and not payload.chart_image:
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

    # Primary: Cloudflare Worker. Keep Anthropic credentials inside the Worker.
    if settings.cloudflare_worker_url:
        try:
            async with httpx.AsyncClient(timeout=60) as worker_client:
                wr = await worker_client.post(settings.cloudflare_worker_url, json={
                    "message": message, "symbol": payload.symbol, "timeframe": payload.timeframe,
                    "chart_image": image_url, "market_context": candle_context, "instructions": instructions,
                })
            wr.raise_for_status()
            wd = wr.json()
            answer = wd.get("answer") or wd.get("output_text")
            if answer:
                return {"answer": answer, "model": wd.get("model", "cloudflare-worker"),
                    "assistant_mode": "cloudflare_worker", "provider": "cloudflare_worker",
                    "web_search_used": bool(wd.get("web_search_used", False)),
                    "citations": wd.get("citations", []),
                    "market_data_status": candle_context.get("status", "unavailable"),
                    "daily_bias": candle_context.get("daily_bias", "UNAVAILABLE"),
                    "symbol": payload.symbol, "timeframe": payload.timeframe,
                    "chart_received": bool(image_url), "execution_enabled": False}
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            pass

    # Backup: Pollinations' OpenAI-compatible Chat Completions API.
    if settings.pollinations_api_key:
        try:
            user_content = message + "\\n\\nVerified market context: " + str(candle_context)
            if image_url:
                user_content = [{"type": "text", "text": user_content},
                                {"type": "image_url", "image_url": {"url": image_url}}]
            async with httpx.AsyncClient(timeout=60) as poll_client:
                pr = await poll_client.post("https://gen.pollinations.ai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {settings.pollinations_api_key}"},
                    json={"model": settings.pollinations_model, "messages":[
                        {"role":"system","content":instructions},
                        {"role":"user","content":user_content}], "max_tokens":1200})
            pr.raise_for_status()
            pd = pr.json()
            answer = pd.get("choices", [{}])[0].get("message", {}).get("content")
            if answer:
                return {"answer":answer,"model":settings.pollinations_model,
                    "assistant_mode":"pollinations","provider":"pollinations",
                    "web_search_used":False,"citations":[],
                    "market_data_status":candle_context.get("status","unavailable"),
                    "daily_bias":candle_context.get("daily_bias","UNAVAILABLE"),
                    "symbol":payload.symbol,"timeframe":payload.timeframe,
                    "chart_received":bool(image_url),"execution_enabled":False}
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            pass

    if not settings.openai_api_key:
        answer = offline_trading_answer(message, payload.symbol, payload.timeframe, bool(payload.chart_image))
        return {"answer":answer,"model":"ewo-offline-guide","assistant_mode":"offline",
            "provider":"offline","web_search_used":False,"citations":[],
            "market_data_status":candle_context.get("status","not_connected"),
            "daily_bias":candle_context.get("daily_bias","UNAVAILABLE"),
            "symbol":payload.symbol,"timeframe":payload.timeframe,
            "chart_received":bool(payload.chart_image),
            "chart_analysis":"not_supported_offline" if payload.chart_image else None,
            "execution_enabled":False}
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
    return {"answer": answer, "model": settings.openai_model, "assistant_mode": "full_ai", "market_data_status": candle_context.get("status"), "daily_bias": candle_context.get("daily_bias"), "symbol": payload.symbol, "timeframe": payload.timeframe, "chart_received": bool(image_url)}

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

@app.post("/api/signals/scan")
async def scan_signal(payload: SignalScanRequest) -> dict[str, Any]:
    """Scan one instrument using completed candles and an explicit account-risk context."""
    if payload.symbol not in {a["symbol"] for a in ASSETS if a["symbol"] != "DXY"}:
        raise HTTPException(status_code=400, detail="Unsupported signal instrument.")
    settings = get_settings()
    try:
        if settings.market_data_provider == "twelve_data":
            if not settings.twelve_data_api_key:
                raise HTTPException(status_code=503, detail="TWELVE_DATA_API_KEY is not configured.")
            frame = await TwelveDataClient(settings.twelve_data_api_key).candles(
                payload.symbol, INTERVALS[payload.timeframe], 120
            )
        else:
            token = selected_oanda_token(settings)
            if not token or not settings.oanda_account_id:
                raise HTTPException(status_code=503, detail="OANDA credentials are not configured.")
            frame = await OandaClient(token, settings.oanda_environment).candles(
                payload.symbol.replace("/", "_"), "D" if payload.timeframe == "D1" else payload.timeframe, 120
            )
    except HTTPException:
        raise
    except (httpx.HTTPError, LookupError, ValueError) as exc:
        raise HTTPException(status_code=502, detail=f"Signal candle request failed: {str(exc)[:200]}")

    # Exclude the newest provider candle: it may still be forming.
    completed = frame.iloc[:-1].copy()
    if len(completed) < 60:
        return {"status": "insufficient_completed_candles", "symbol": payload.symbol,
                "timeframe": payload.timeframe, "signals": []}

    policy = RiskPolicy()
    decision = policy.evaluate(
        daily_loss_fraction=payload.daily_loss_fraction,
        weekly_loss_fraction=payload.weekly_loss_fraction,
        consecutive_losses=payload.consecutive_losses,
        kill_switch=payload.kill_switch,
    )
    try:
        candidate = generate_signal(
            completed, payload.symbol, payload.equity,
            quote_to_account_rate=payload.quote_to_account_rate,
            risk_fraction=policy.trade_risk_fraction,
        )
    except (ValueError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=f"Signal calculation rejected the data: {str(exc)[:180]}")
    if candidate is None:
        return {"status": "no_setup", "symbol": payload.symbol, "timeframe": payload.timeframe,
                "completed_candles": len(completed), "signals": []}

    signal = candidate.to_dict()
    if not decision.approved:
        return {"status": "blocked_by_risk", "symbol": payload.symbol, "timeframe": payload.timeframe,
                "risk": {"approved": False, "reason": decision.reason}, "signals": [signal],
                "alert": "not_sent"}

    destinations = bool(settings.telegram_alerts_enabled and settings.telegram_bot_token and settings.telegram_chat_id) or bool(settings.alert_webhook_url)
    alert_result = None
    if destinations:
        dispatcher = AlertDispatcher(
            telegram_bot_token=settings.telegram_bot_token if settings.telegram_alerts_enabled else "",
            telegram_chat_id=settings.telegram_chat_id if settings.telegram_alerts_enabled else "",
            webhook_url=settings.alert_webhook_url,
            retry_attempts=settings.telegram_retry_attempts,
            retry_delay_seconds=settings.telegram_retry_delay_seconds,
            database_url=settings.database_url,
        )
        alert_result = await dispatcher.dispatch(signal)
    return {"status": "signal_candidate", "symbol": payload.symbol, "timeframe": payload.timeframe,
            "completed_candles": len(completed), "risk": {"approved": True,
            "effective_risk_fraction": decision.effective_risk_fraction}, "signals": [signal],
            "alert": ({"accepted": alert_result.accepted, "duplicate": alert_result.duplicate,
            "telegram_sent": alert_result.telegram_sent, "webhook_sent": alert_result.webhook_sent,
            "errors": list(alert_result.errors)} if alert_result else "not_configured"),
            "execution_enabled": False}


@app.get("/api/signals")
async def signals() -> dict[str, Any]:
    return {"status": "scan_on_request", "signals": []}


@app.get("/api/news/events/{event_id}/history")
async def news_event_history(event_id: str) -> dict[str, Any]:
    """Return provider-sourced historical releases for event calibration."""
    settings = get_settings()
    if not settings.biquote_history_enabled:
        raise HTTPException(status_code=503, detail="Calendar history is disabled.")
    try:
        history = await BiquoteCalendarClient(settings.biquote_calendar_url).event_history(event_id)
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=502, detail=f"Calendar history unavailable: {str(exc)[:180]}")
    return {"event_id": event_id, "source": "biquote", "history": history, "observations": len(history), "calibration_status": "ready" if len(history) >= 2 else "insufficient_history"}

@app.post("/api/news/spike-check")
async def news_spike_check(payload: dict[str, Any]) -> dict[str, Any]:
    """Score provider-observed ticks and enforce a spread cap; never fabricate ticks."""
    ticks, spread, maximum = payload.get("ticks"), payload.get("spread"), payload.get("maximum_spread")
    if not isinstance(ticks, list) or len(ticks) > 5000:
        raise HTTPException(status_code=422, detail="ticks must be a list of up to 5000 observed prices.")
    try:
        values = [float(value) for value in ticks]
        spread_value, maximum_value = float(spread), float(maximum)
        if any(not isfinite(value) or value <= 0 for value in values) or not isfinite(spread_value) or not isfinite(maximum_value):
            raise ValueError("All tick and spread values must be finite and valid.")
    except (TypeError, ValueError):
        raise HTTPException(status_code=422, detail="Supply numeric positive ticks, spread and maximum_spread.")
    score = tick_spike_score(values, window=30)
    allowed = spread_guard(spread_value, maximum_value)
    detected = score is not None and score >= 3.0
    return {"tick_count": len(values), "spike_z_score": score, "spike_detected": detected, "spread": spread_value, "maximum_spread": maximum_value, "spread_allowed": allowed, "alert_eligible": bool(detected and allowed), "execution_enabled": False, "note": "Observed ticks only; no live stream is implied."}

@app.get("/api/news/impact/{currency}")
async def news_currency_impact(currency: str) -> dict[str, Any]:
    instruments = impacted_instruments(currency)
    return {"currency": currency.upper(), "instruments": instruments, "status": "configured_mapping" if instruments else "no_mapping"}

@app.get("/api/news")
async def news() -> dict[str, Any]:
    """Fetch calendar events and recent FX-related headlines; report provider failures separately."""
    settings = get_settings()
    calendar_events: list[dict[str, Any]] = []
    headlines: list[dict[str, Any]] = []
    errors: dict[str, str] = {}

    try:
        calendar = await BiquoteCalendarClient(settings.biquote_calendar_url).upcoming(
            importance=settings.biquote_importance,
            countries=settings.biquote_countries,
        )
        calendar_events = json.loads(calendar.to_json(orient="records", date_format="iso"))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        errors["calendar"] = str(exc)[:240]

    try:
        articles = await GdeltClient(settings.gdelt_doc_url).articles(
            query=settings.gdelt_query,
            lookback_minutes=settings.gdelt_lookback_minutes,
        )
        headlines = json.loads(articles.to_json(orient="records", date_format="iso"))
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        errors["headlines"] = str(exc)[:240]

    connected = bool(calendar_events or headlines)
    return {
        "status": "live" if connected else "unavailable",
        "calendar_status": "live" if calendar_events else ("empty" if "calendar" not in errors else "unavailable"),
        "headlines_status": "live" if headlines else ("empty" if "headlines" not in errors else "unavailable"),
        "events": calendar_events,
        "headlines": headlines,
        "errors": errors,
    }
