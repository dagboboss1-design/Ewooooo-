# Phase 3 — Alerts

Use the dispatcher to send a complete Phase 2 signal to Telegram, an outbound webhook, or both.

```python
from forex_quant.alerts import AlertDispatcher

dispatcher = AlertDispatcher(
    telegram_bot_token="read-from-environment",
    telegram_chat_id="read-from-environment",
    webhook_url="https://your-service.example/alerts",
)
result = await dispatcher.dispatch(signal.to_dict())
```

The dispatcher deduplicates identical signal identities for 60 seconds by default and
serializes Telegram sends with a one-second minimum interval. Inject an `httpx.AsyncClient`
for tests or managed connection lifecycles. This sends notifications only; it never places
orders. Keep credentials outside source control.
