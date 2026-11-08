# Phase 4 — Responsive Dashboard

The Phase 4 dashboard is a responsive dark institutional-style web interface, designed to work on mobile screens and desktop browsers.

## Included watchlist

- FX: EUR/USD, GBP/USD, USD/JPY, AUD/USD, USD/CAD, EUR/GBP, AUD/NZD
- Metals: XAU/USD, XAG/USD
- Crypto: BTC/USD
- Index: DXY

Selectable chart timeframes: M5, M15, M30, H1, H4, D1 (1 day). The default selection is M15. The dashboard also calculates a provisional daily bias from the last completed daily candles versus EMA20 and its recent slope; the newest daily candle is excluded to avoid using a still-forming bar. This is contextual analysis, not a standalone trade signal.

## Run locally

```bash
pip install -e ".[dev]"
uvicorn forex_quant.dashboard.app:app --host 0.0.0.0 --port 8000
```

Open `http://127.0.0.1:8000` in a browser. On a phone connected to the same Wi-Fi, use the computer's LAN IP with port 8000.

## API

- `GET /api/dashboard/config` — supported watchlist and timeframes
- `GET /api/dashboard/status` — connection and execution state
- `GET /api/market` — verified market quote payload (empty until feed integration)
- `GET /api/signals` — signal payload (empty until connected)
- `GET /api/news` — event payload (empty until connected)
- `GET /docs` — interactive API documentation

## Data integrity and safety

The dashboard deliberately does not display example prices or fabricated signals as live. All feeds currently report disconnected until real provider adapters are connected and validated. DXY requires a suitable index data source; it is not assumed to be an OANDA instrument. Availability of BTC/USD and metal instruments depends on the connected provider/account. Live order execution is not implemented or enabled.


## Container deployment

A production-oriented Dockerfile is included. Build and run locally:

```bash
docker build -t ewooooo-quant .
docker run --rm -p 8000:8000 -e PORT=8000 -e TWELVE_DATA_API_KEY= -e OPENAI_API_KEY= -v ewooooo-data:/app/data ewooooo-quant
```

Set real provider credentials as private host environment variables (never in the image or repository). Persist `/app/data` with a mounted volume when using the default SQLite journal database. The container runs as a non-root user and exposes `/healthz` for liveness; `/readyz` reports whether optional market-data and AI credentials are configured. A ready HTTP process does not mean provider connectivity has been validated. Broker execution remains disabled.
