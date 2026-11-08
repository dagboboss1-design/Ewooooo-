# Phase 3 — Alerts

The dispatcher sends complete Phase 2 signals to Telegram, an outbound webhook, or both.
Configure Telegram credentials and the optional backup URL only in private deployment
settings. Never commit real credentials.

Delivery retries transient HTTP and timeout failures with exponential backoff. Successful
destinations are remembered separately, so a retry after partial success does not resend
to a destination that already accepted the alert. Identical signal identities are
deduplicated for 60 seconds. Telegram sends are serialized with a one-second minimum gap.

Pass the same persistent \`database_url\` used by the application to \`AlertDispatcher\`
to retain destination delivery state across process restarts. The dispatcher creates
the \`alert_deliveries\` table and prunes expired records. Without \`database_url\`,
deduplication remains process-local. This persistence protects against routine restart
duplicates and allows later dispatches to retry destinations that had not accepted delivery.
It is not a durable scheduled worker or guaranteed delivery queue: an outbox worker with
leases and monitoring is still needed for unattended retry if a process exits before
another dispatch occurs.

Environment settings: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TELEGRAM_ALERTS_ENABLED,
TELEGRAM_RETRY_ATTEMPTS, TELEGRAM_RETRY_DELAY_SECONDS, and optional ALERT_WEBHOOK_URL.
Notifications only; no broker orders are placed.
