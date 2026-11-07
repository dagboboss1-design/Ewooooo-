from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class AlertResult:
    accepted: bool
    duplicate: bool
    telegram_sent: bool
    webhook_sent: bool
    errors: tuple[str, ...] = ()


def format_signal_message(signal: dict[str, Any]) -> str:
    """Render a compact, deterministic alert from a complete signal payload."""
    required = ("instrument", "timestamp", "side", "entry", "stop_loss",
                "take_profit", "units", "risk_fraction", "confidence_score")
    missing = [key for key in required if key not in signal]
    if missing:
        raise ValueError(f"Incomplete signal; missing: {', '.join(missing)}")
    side = str(signal["side"]).upper()
    if side not in {"BUY", "SELL"}:
        raise ValueError("Signal side must be buy or sell")
    return (
        f"FOREX SIGNAL | {signal['instrument']} | {side}\n"
        f"Time: {signal['timestamp']}\n"
        f"Entry: {signal['entry']} | SL: {signal['stop_loss']} | "
        f"TP: {signal['take_profit']}\n"
        f"Units: {signal['units']} | Risk: "
        f"{float(signal['risk_fraction']) * 100:.2f}% | "
        f"Confluence: {float(signal['confidence_score']):.2f}\n"
        f"Strategy: {signal.get('strategy', 'unspecified')} | "
        f"Regime: {signal.get('regime', 'unknown')}\n"
        "Research alert only — not an order."
    )


class AlertDispatcher:
    """Outbound Telegram/webhook alerts with in-process dedupe and rate limiting.

    Configure secrets through environment variables in the deployment layer;
    never hard-code bot tokens or chat IDs in source control.
    """

    TELEGRAM_URL = "https://api.telegram.org/bot{token}/sendMessage"

    def __init__(
        self,
        *,
        telegram_bot_token: str = "",
        telegram_chat_id: str = "",
        webhook_url: str = "",
        dedupe_seconds: int = 60,
        telegram_min_interval_seconds: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if dedupe_seconds < 0 or telegram_min_interval_seconds < 0:
            raise ValueError("Alert timing settings cannot be negative")
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.webhook_url = webhook_url
        self.dedupe_seconds = dedupe_seconds
        self.telegram_min_interval_seconds = telegram_min_interval_seconds
        self._client = client
        self._last_sent: dict[str, float] = {}
        self._last_telegram_at = 0.0
        self._telegram_lock = asyncio.Lock()

    @staticmethod
    def _fingerprint(signal: dict[str, Any]) -> str:
        identity = {
            key: signal.get(key)
            for key in ("instrument", "timestamp", "side", "strategy")
        }
        payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    async def _post(self, url: str, payload: dict[str, Any]) -> None:
        if self._client is not None:
            response = await self._client.post(url, json=payload, timeout=10.0)
            response.raise_for_status()
            return
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

    async def _send_telegram(self, message: str) -> None:
        async with self._telegram_lock:
            wait = self.telegram_min_interval_seconds - (
                time.monotonic() - self._last_telegram_at
            )
            if wait > 0:
                await asyncio.sleep(wait)
            await self._post(
                self.TELEGRAM_URL.format(token=self.telegram_bot_token),
                {"chat_id": self.telegram_chat_id, "text": message},
            )
            self._last_telegram_at = time.monotonic()

    async def dispatch(self, signal: dict[str, Any]) -> AlertResult:
        message = format_signal_message(signal)
        now = time.monotonic()
        fingerprint = self._fingerprint(signal)
        self._last_sent = {
            key: sent_at for key, sent_at in self._last_sent.items()
            if now - sent_at < self.dedupe_seconds
        }
        if fingerprint in self._last_sent:
            return AlertResult(False, True, False, False)
        self._last_sent[fingerprint] = now

        errors: list[str] = []
        telegram_sent = False
        webhook_sent = False
        if self.telegram_bot_token and self.telegram_chat_id:
            try:
                await self._send_telegram(message)
                telegram_sent = True
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                errors.append(f"telegram: {type(exc).__name__}")
        if self.webhook_url:
            try:
                await self._post(
                    self.webhook_url,
                    {"event": "forex.signal", "signal": signal, "message": message},
                )
                webhook_sent = True
            except (httpx.HTTPError, asyncio.TimeoutError) as exc:
                errors.append(f"webhook: {type(exc).__name__}")
        return AlertResult(
            accepted=telegram_sent or webhook_sent,
            duplicate=False,
            telegram_sent=telegram_sent,
            webhook_sent=webhook_sent,
            errors=tuple(errors),
        )
