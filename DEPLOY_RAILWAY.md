# Deploy Ewooooo safely on Railway

This project is a Python FastAPI application. Railway should build it from the repository's Dockerfile.

## Deploy from the development branch

1. Connect the Railway account and create a new project from the GitHub repository `dagboboss1-design/Ewooooo-`.
2. Select branch `fix/phase-1-package-structure`. Do not select or change `main`.
3. Confirm Railway detects and builds the repository Dockerfile. The service listens on Railway's supplied `PORT` and has a `/healthz` health check.
4. Add a PostgreSQL service to the same Railway project.
5. Add a persistent volume to the app service mounted at `/app/data` for downloaded snapshots and local data files.
6. Add the following app-service variables:
   - `DATABASE_URL=${{Postgres.DATABASE_URL}}` (use the exact PostgreSQL service name if it differs from `Postgres`)
   - `DASHBOARD_AUTH_REQUIRED=true`
   - `DASHBOARD_USERNAME=<choose-a-username>`
   - `DASHBOARD_PASSWORD=<generate-a-long-unique-random-secret-in-Railway>`
   - `DATA_DIR=/app/data`
   - `LIVE_TRADING=false`
   - `OANDA_ENVIRONMENT=practice`
   - `MARKET_DATA_PROVIDER=twelve_data`
7. Deploy, wait for the health check, then use Railway's generated HTTPS domain. The first visit should ask for the dashboard username and password.

## Optional provider secrets

Add only the provider credentials you have actually obtained, using Railway's private Variables interface. Examples include `TWELVE_DATA_API_KEY`, `OPENAI_API_KEY`, `CLOUDFLARE_WORKER_URL`, and `TELEGRAM_BOT_TOKEN`. Never commit these values or paste them into source code, chat, or the dashboard.

## Before sharing the URL

- Confirm the HTTP Basic login prompt appears in a private/incognito browser.
- Confirm `/healthz` reports healthy and the dashboard is not publicly readable without credentials.
- Confirm PostgreSQL is connected and the persistent volume is mounted.
- Confirm `/readyz` does not imply a market-data or AI provider is connected unless the provider actually works.
- Keep live trading disabled. This app has no authorized live broker execution.
- Do not use a public unauthenticated domain for this dashboard.

## Important

A Railway account, GitHub authorization, and user-owned project are required. Deployment creates a publicly reachable hostname even though the dashboard is password-protected. Hosting charges or usage limits depend on the user's Railway plan. This document is a deployment checklist, not evidence that the app has already been deployed.
