# Phase 4 Market Data Notes

- Added TwelveDataClient for quote and OHLC time-series retrieval through Twelve Data REST endpoints.
- Twelve Data is the default read-only market-data provider; OANDA remains an optional provider.
- Added /api/market/candles with M5, M15, M30, H1 and H4 mappings.
- Credentials are read only from server environment variables. No API key is committed.
- Bid/ask are left null unless the provider returns them; close is labelled mid for display and must not be interpreted as executable bid/ask.
- DXY is deliberately marked unavailable until a dedicated index feed is configured.
- Metals and crypto availability depends on the user's Twelve Data plan, symbol coverage and API credits. Provider errors are surfaced per instrument rather than replaced with invented values.
- Live quotes and candles are not yet visually charted; the dashboard chart rendering and strategy-to-signal pipeline remain next tasks.
- LIVE_TRADING remains false; this integration is read-only.
