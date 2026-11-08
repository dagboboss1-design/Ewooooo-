# Phase 3 — Alerts

The dispatcher sends complete Phase 2 signals to Telegram, an outbound webhook, or both.
Configure Telegram credentials and the optional backup URL only in private deployment
settings. Never commit real credentials.

Delivery retries transient HTTP and timeout failures with exponential backoff
(1s, 2s, ... by default). Successful destinations are remembered separately, so a retry
after partial success does not resend to a destination that already accepted the alert.
Identical signal identities are deduplicated for 60 seconds after delivery. Telegram sends
are serialized with a one-second minimum interval.

Environment settings: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALERTS_ENABLED,
TELEGRAM_RETRY_ATTEMPTS, TELEGRAM_RETRY_DELAY_SECONDS, and optional ALERT_WEBHOOK_URL.

Recovery limitation: retry and deduplication state currently lives in process memory.
It does not survive a restart and is not a durable queue. A persistent database-backed
outbox and worker are still required for recovery after a host restart or prolonged outage.
These alerts are notifications only; they never place orders.
