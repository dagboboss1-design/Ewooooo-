import httpx
import pytest
import respx
from forex_quant.alerts import AlertDispatcher, format_signal_message

SIGNAL = {
    "instrument": "EUR_USD", "timestamp": "2026-01-01T10:00:00+00:00",
    "side": "buy", "entry": 1.1, "stop_loss": 1.095, "take_profit": 1.11,
    "units": 1000, "risk_fraction": 0.005, "confidence_score": 1.0,
    "strategy": "test_strategy", "regime": "ranging",
}

def test_message_requires_complete_signal():
    with pytest.raises(ValueError, match="Incomplete signal"):
        format_signal_message({"instrument": "EUR_USD"})

def test_message_contains_risk_and_no_order_disclaimer():
    message = format_signal_message(SIGNAL)
    assert "Risk: 0.50%" in message
    assert "not an order" in message

@pytest.mark.asyncio
@respx.mock
async def test_dispatch_sends_telegram_and_webhook_then_dedupes():
    telegram = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    webhook = respx.post("https://example.test/alerts").mock(return_value=httpx.Response(202))
    async with httpx.AsyncClient() as client:
        dispatcher = AlertDispatcher(telegram_bot_token="TEST_TOKEN", telegram_chat_id="123",
            webhook_url="https://example.test/alerts", telegram_min_interval_seconds=0,
            retry_delay_seconds=0, client=client)
        first = await dispatcher.dispatch(SIGNAL)
        second = await dispatcher.dispatch(SIGNAL)
    assert first.accepted and first.telegram_sent and first.webhook_sent
    assert second.duplicate
    assert telegram.call_count == webhook.call_count == 1

@pytest.mark.asyncio
@respx.mock
async def test_dispatch_retries_transient_failure():
    telegram = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})])
    async with httpx.AsyncClient() as client:
        dispatcher = AlertDispatcher(telegram_bot_token="TEST_TOKEN", telegram_chat_id="123",
            telegram_min_interval_seconds=0, retry_delay_seconds=0, client=client)
        result = await dispatcher.dispatch(SIGNAL)
    assert result.accepted and result.telegram_sent
    assert telegram.call_count == 2

@pytest.mark.asyncio
@respx.mock
async def test_partial_success_retries_only_failed_destination():
    telegram = respx.post("https://api.telegram.org/botTEST_TOKEN/sendMessage").mock(
        return_value=httpx.Response(200, json={"ok": True}))
    webhook = respx.post("https://example.test/alerts").mock(
        side_effect=[httpx.Response(503), httpx.Response(202)])
    async with httpx.AsyncClient() as client:
        dispatcher = AlertDispatcher(telegram_bot_token="TEST_TOKEN", telegram_chat_id="123",
            webhook_url="https://example.test/alerts", telegram_min_interval_seconds=0,
            retry_attempts=1, retry_delay_seconds=0, client=client)
        first = await dispatcher.dispatch(SIGNAL)
        second = await dispatcher.dispatch(SIGNAL)
    assert first.telegram_sent and not first.webhook_sent
    assert second.webhook_sent and not second.telegram_sent
    assert telegram.call_count == 1 and webhook.call_count == 2

@pytest.mark.asyncio
@respx.mock
async def test_dispatch_reports_channel_failure_without_crashing():
    respx.post("https://example.test/alerts").mock(return_value=httpx.Response(500))
    async with httpx.AsyncClient() as client:
        dispatcher = AlertDispatcher(webhook_url="https://example.test/alerts",
            retry_attempts=1, client=client)
        result = await dispatcher.dispatch(SIGNAL)
    assert not result.accepted
    assert result.errors == ("webhook: HTTPStatusError",)

def test_negative_timing_or_retry_configuration_rejected():
    with pytest.raises(ValueError):
        AlertDispatcher(dedupe_seconds=-1)
    with pytest.raises(ValueError):
        AlertDispatcher(retry_attempts=0)
