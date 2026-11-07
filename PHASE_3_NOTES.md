# Phase 3 Notes — Alert Delivery

## Delivered
- Deterministic signal-message formatter with required-field validation.
- Async Telegram Bot API delivery and optional outbound JSON webhook.
- Per-process duplicate suppression using instrument, timestamp, side and strategy (60-second default).
- Telegram send serialization and 1-second default minimum interval.
- Channel-level error reporting; a failed alert is not reported as delivered.
- Tests for formatting, required fields, deduplication, delivery and failures.

## Configuration
Pass Telegram bot token, chat ID and webhook URL from environment-backed deployment settings.
Do not commit secrets. No credentials are required for tests.

## Boundaries
- This is outbound alert delivery only; it does not place, modify or close trades.
- Dedupe and rate-limit state are in memory and reset on process restart. Multi-worker deployments need shared storage/locking.
- Webhook delivery is outbound. The inbound webhook receiver and its immediate-ack/async processing belong to the API service phase.
- Telegram delivery and external webhook behavior require credentialed deployment smoke tests.
