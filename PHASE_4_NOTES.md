# Phase 4 implementation notes

## Delivered

- FastAPI application serving a responsive mobile-first dashboard.
- Multi-asset watchlist for seven FX pairs, XAU/USD, XAG/USD, BTC/USD and DXY.
- M5, M15, M30, H1 and H4 timeframe controls; M15 is the initial selection.
- API contracts for dashboard config/status, market quotes, signals and news.
- Tests for page serving, watchlist/timeframe coverage, no fabricated quote values and execution remaining off.

## Important limitations

- This is a working dashboard shell and API contract, not yet a live trading terminal.
- Provider adapters have not yet been wired into the dashboard endpoints. Quotes, signals and news remain explicitly empty until verified feed services are integrated.
- Instrument availability varies by provider and account. DXY needs a dedicated index feed; it is not presumed to be available through OANDA.
- The chart panel is currently a data-waiting state; candle rendering and real-time updates are the next integration task.
- No order placement, modification or closing is exposed.

## Local validation

Run `pip install -e ".[dev]"`, then `pytest -q`. Start the dashboard with `uvicorn forex_quant.dashboard.app:app --host 0.0.0.0 --port 8000`.
