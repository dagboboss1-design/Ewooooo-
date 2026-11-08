from __future__ import annotations
import asyncio, hashlib, json, time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable
import httpx

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
    return (
        f"FOREX SIGNAL | {signal['instrument']} | {side}\n"
        f"Time: {signal['timestamp']}\n"
        f"Entry: {signal['entry']} | SL: {signal['stop_loss']} | TP: {signal['take_profit']}\n"
        f"Units: {signal['units']} | Risk: {float(signal['risk_fraction']) * 100:.2f}% | "
        f"Confluence: {float(signal['confidence_score']):.2f}\n"
        f"Strategy: {signal.get('strategy', 'unspecified')} | Regime: {signal.get('regime', 'unknown')}\n"
        "Research alert only — not an order."
    )

class AlertDispatcher:
    """Outbound alerts with retry, rate limiting and process-local destination dedupe."""
    TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"
    RETRYABLE_ERRORS = (httpx.HTTPError, asyncio.TimeoutError)

    def __init__(self, *, telegram_bot_token="", telegram_chat_id="", webhook_url="",
                 dedupe_seconds=60, telegram_min_interval_seconds=1.0,
                 retry_attempts=3, retry_delay_seconds=1.0,
                 client: httpx.AsyncClient | None=None):
        if (dedupe_seconds < 0 or telegram_min_interval_seconds < 0
                or retry_attempts < 1 or retry_delay_seconds < 0):
            raise ValueError("Alert timing and retry settings are invalid")
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
        self.dedupe_seconds = dedupe_seconds
        self.telegram_min_interval_seconds = telegram_min_interval_seconds
        self.retry_attempts = retry_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self._client = client
        self._delivered: dict[str, tuple[float, set[str]]] = {}
        self._last_telegram_at = 0.0
        self._telegram_lock = asyncio.Lock()

    @staticmethod
    def _fingerprint(signal):
        identity = {key: signal.get(key) for key in ("instrument", "timestamp", "side", "strategy")}
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _post(self, url, payload):
        if self._client is not None:
            response = await self._client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
        else:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
        if "api.telegram.org" in url and response.json().get("ok") is not True:
            raise httpx.HTTPStatusError(
                "Telegram API returned ok=false", request=response.request, response=response
            )

    async def _send_telegram(self, message):
        async with self._telegram_lock:
            wait = self.telegram_min_interval_seconds - (time.monotonic() - self._last_telegram_at)
            if wait > 0:
                await asyncio.sleep(wait)
            await self._post(self.TELEGRAM_URL.format(token=self.telegram_bot_token),
                             {"chat_id": self.telegram_chat_id, "text": message})
            self._last_telegram_at = time.monotonic()

    async def _retry(self, label: str, operation: Callable[[], Awaitable[None]], errors: list[str]) -> bool:
        for attempt in range(self.retry_attempts):
            try:
                await operation()
                return True
            except self.RETRYABLE_ERRORS as exc:
                if attempt + 1 == self.retry_attempts:
                    errors.append(f"{label}: {type(exc).__name__}")
                    return False
                delay = self.retry_delay_seconds * (2 ** attempt)
                if delay:
                    await asyncio.sleep(delay)
        return False

    async def dispatch(self, signal: dict[str, Any]) -> AlertResult:
        message = format_signal_message(signal)
        now = time.monotonic()
        fingerprint = self._fingerprint(signal)
        self._delivered = {key: value for key, value in self._delivered.items()
                           if now - value[0] < self.dedupe_seconds}
        configured = set()
        if self.telegram_bot_token and self.telegram_chat_id:
            configured.add("telegram")
        if self.webhook_url:
            configured.add("webhook")
        sent = self._delivered.get(fingerprint, (now, set()))[1]
        if configured and configured.issubset(sent):
            return AlertResult(False, True, False, False)

        errors = []
        telegram_sent = webhook_sent = False
        if "telegram" in configured and "telegram" not in sent:
            telegram_sent = await self._retry("telegram", lambda: self._send_telegram(message), errors)
            if telegram_sent:
                sent.add("telegram")
        if "webhook" in configured and "webhook" not in sent:
            webhook_sent = await self._retry(
                "webhook",
                lambda: self._post(self.webhook_url, {"event": "forex.signal", "signal": signal, "message": message}),
                errors,
            )
            if webhook_sent:
                sent.add("webhook")
        if sent:
            self._delivered[fingerprint] = (now, sent)
        return AlertResult(telegram_sent or webhook_sent, False, telegram_sent, webhook_sent, tuple(errors))
