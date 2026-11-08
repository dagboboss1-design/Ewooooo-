# Phase 4 implementation notes

## Delivered

- Responsive mobile-first dark dashboard with multi-asset watchlist and M5/M15/M30/H1/H4/D1 chart controls.
- Read-only Twelve Data and OANDA quote/candle adapters; unavailable instruments are explicitly identified rather than assigned invented prices.
- Candlestick chart with OHLC inspection, refresh handling and D1 EMA20 context.
- AI chat endpoint with optional chart image analysis, verified candle context, voice input and spoken replies in supported browsers.
- Risk-gated on-demand signal scanner using completed candles, explicit account equity and quote-to-account conversion, and the 0.5% default trade-risk policy.
- Telegram/webhook alerts through the existing alert dispatcher when privately configured.
- AI setup journal actions and scanner setup journal action. Scanner candidates can be saved as taken only after risk approval; saving creates a paper-journal record, never a broker order.
- Journal trade tracking and performance summaries.
- Docker support, health/readiness endpoints, and automated tests.

## Current configuration and limitations

- Twelve Data API key and OpenAI API key are not configured in the repository. Add them only as private server environment variables. ChatGPT subscription does not include OpenAI API credits.
- Provider/account plan determines whether all requested instruments (especially metals and crypto) are available. DXY requires a dedicated index feed.
- AI chat and live market data remain unavailable until their respective private credentials are configured and validated.
- Scanner output is an experimental baseline candidate, not a calibrated probability or promise of profit. Supplied equity, conversion rate and current loss figures must be accurate.
- Confidence/confluence score is not a win probability. Pair-specific walk-forward and out-of-sample validation remain necessary.
- Broker order placement is disabled. Journal saving is a paper record only.
- News feed integration and production deployment/credential validation remain outstanding.

## Local validation

Run `pip install -e ".[dev]"`, then `pytest -q`. Start with `uvicorn forex_quant.dashboard.app:app --host 0.0.0.0 --port 8000`.
