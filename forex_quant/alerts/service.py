from __future__ import annotations
import asyncio, hashlib, json, time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import httpx
from forex_quant.db import init_db, load_alert_delivery, save_alert_delivery, prune_alert_deliveries

@dataclass(frozen=True)
class AlertResult:
    accepted: bool
    duplicate: bool
    telegram_sent: bool
    webhook_sent: bool
    errors: tuple[str, ...] = ()

def format_signal_message(signal: dict[str, Any]) -> str:
    required = ("instrument", "timestamp", "side", "entry", "stop_loss", "take_profit", "units", "risk_fraction", "confidence_score")
    missing = [key for key in required if key not in signal]
    if missing:
        raise ValueError(f"Incomplete signal; missing: {', '.join(missing)}")
    side = str(signal["side"]).upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("Signal side must be buy or sell")
    return (f"FOREX SIGNAL | {signal['instrument']} | {side}\n"
        f"Time: {signal['timestamp']}\nEntry: {signal['entry']} | SL: {signal['stop_loss']} | TP: {signal['take_profit']}\n"
        f"Units: {signal['units']} | Risk: {float(signal['risk_fraction']) * 100:.2f}% | "
        f"Confluence: {float(signal['confidence_score']):.2f}\n"
        f"Strategy: {signal.get('strategy', 'unspecified')} | Regime: {signal.get('regime', 'unknown')}\n"
        "Research alert only — not an order.")

class AlertDispatcher:
    TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
    RETRYABLE_ERRORS = (httpx.HTTPError, asyncio.TimeoutError)

    def __init__(self, *, telegram_bot_token="", telegram_chat_id="", webhook_url="", dedupe_seconds=60,
        telegram_min_interval_seconds=1.0, retry_attempts=3, retry_delay_seconds=1.0,
        database_url: str | None=None, client: httpx.AsyncClient | None=None):
        if dedupe_seconds < 0 or telegram_min_interval_seconds < 0 or retry_attempts < 1 or retry_delay_seconds < 0:
            raise ValueError("Alert timing and retry settings are invalid")
        self.telegram_bot_token, self.telegram_chat_id, self.webhook_url = telegram_bot_token, telegram_chat_id, webhook_url
        self.dedupe_seconds, self.telegram_min_interval_seconds = dedupe_seconds, telegram_min_interval_seconds
        self.retry_attempts, self.retry_delay_seconds = retry_attempts, retry_delay_seconds
        self._client = client
        self._delivered: dict[str, tuple[float, set[str]]] = {}
        self._last_telegram_at = 0.0
        self._telegram_lock = asyncio.Lock()
        self._engine = init_db(database_url) if database_url else None

    @staticmethod
    def _fingerprint(signal):
        identity = {key: signal.get(key) for key in ("instrument", "timestamp", "side", "strategy")}
        return hashlib.sha256(json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def _load_sent(self, fingerprint, now):
        if self._engine is None:
            self._delivered = {k:v for k,v in self._delivered.items() if now-v[0] < self.dedupe_seconds}
            return set(self._delivered.get(fingerprint, (now,set()))[1])
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.dedupe_seconds)
        prune_alert_deliveries(self._engine, older_than=cutoff)
        record = load_alert_delivery(self._engine, fingerprint)
        if record is None: return set()
        created = record["created_at"]
        if created.tzinfo is None: created = created.replace(tzinfo=timezone.utc)
        if (datetime.now(timezone.utc)-created).total_seconds() >= self.dedupe_seconds: return set()
        return set(record["delivered"])

    def _save_sent(self, fingerprint, sent, now):
        if self._engine is None:
            self._delivered[fingerprint] = (now, sent)
        else:
            save_alert_delivery(self._engine, fingerprint=fingerprint,
                created_at=datetime.now(timezone.utc), delivered=sorted(sent))

    async def _post(self, url, payload):
        if self._client is not None:
            response = await self._client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        if "api.telegram.org" in url and response.json().get("ok") is not True:
            raise httpx.HTTPStatusError("Telegram API returned ok=false", request=response.request, response=response)

    async def _send_telegram(self, message):
        async with self._telegram_lock:
            wait = self.telegram_min_interval_seconds - (time.monotonic()-self._last_telegram_at)
            if wait > 0: await asyncio.sleep(wait)
            await self._post(self.TELEGRAM_URL.format(token=self.telegram_bot_token),
                {"chat_id":self.telegram_chat_id,"text":message})
            self._last_telegram_at = time.monotonic()

    async def _retry(self, label, operation: Callable[[], Awaitable[None]], errors):
        for attempt in range(self.retry_attempts):
            try:
                await operation()
                return True
            except self.RETRYABLE_ERRORS as exc:
                if attempt+1 == self.retry_attempts:
                    errors.append(f"{label}: {type(exc).__name__}")
                    return False
                delay = self.retry_delay_seconds * (2**attempt)
                if delay: await asyncio.sleep(delay)
        return False

    async def dispatch(self, signal: dict[str, Any]) -> AlertResult:
        message = format_signal_message(signal)
        now, fingerprint = time.monotonic(), self._fingerprint(signal)
        configured = set()
        if self.telegram_bot_token and self.telegram_chat_id: configured.add("telegram")
        if self.webhook_url: configured.add("webhook")
        sent = self._load_sent(fingerprint, now)
        if configured and configured.issubset(sent): return AlertResult(False, True, False, False)
        errors, telegram_sent, webhook_sent = [], False, False
        if "telegram" in configured and "telegram" not in sent:
            telegram_sent = await self._retry("telegram", lambda:self._send_telegram(message), errors)
            if telegram_sent: sent.add("telegram")
        if "webhook" in configured and "webhook" not in sent:
            webhook_sent = await self._retry("webhook", lambda:self._post(self.webhook_url,
                {"event":"forex.signal","signal":signal,"message":message}), errors)
            if webhook_sent: sent.add("webhook")
        if sent: self._save_sent(fingerprint, sent, now)
        return AlertResult(telegram_sent or webhook_sent, False, telegram_sent, webhook_sent, tuple(errors))
