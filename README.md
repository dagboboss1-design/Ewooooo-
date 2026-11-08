# Ewooooo Forex Quant

Mobile-first Forex market analysis and paper-trading dashboard.

## Market data providers

- **Primary: Dukascopy.** The app builds intraday OHLC candles from Dukascopy's public historical tick archive. This path requires no OANDA account or OANDA API key.
- **Secondary: Twelve Data.** Configure `TWELVE_DATA_API_KEY` privately to provide backup candles and live quote polling. It is optional; never commit the key.
- **OANDA: optional legacy adapter only.** OANDA credentials are not required for startup, charts, signals, or paper trading. Do not set `MARKET_DATA_PROVIDER=oanda` unless eligible credentials are available.

Set `MARKET_DATA_PROVIDER=dukascopy` for the intended Nigerian deployment. Dukascopy's public archive is historical data, not a guaranteed real-time quote stream. The dashboard must label archive candles as historical and must not claim live prices when no live quote provider is connected. D1 candles and live quote polling require the optional Twelve Data backup key.

## Safety and paper trading

- Paper trading only. `LIVE_TRADING=false` must remain set.
- Virtual balance and paper positions are not broker orders.
- Missing, stale, or insufficient market data must result in WAIT/unavailable, never fabricated prices or signals.
- Dukascopy tick volume is provider-specific, not consolidated FX exchange volume.
- Never commit `.env`, provider tokens, account IDs, or downloaded private data.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Set `MARKET_DATA_PROVIDER=dukascopy`. A Twelve Data key may be added privately as a secondary feed. OANDA credentials are not needed.

For PostgreSQL, set `DATABASE_URL` to the Railway PostgreSQL connection string. SQLite remains the local-development default.

## Run tests

```bash
pytest -q
```

## Run the dashboard

```bash
uvicorn forex_quant.dashboard.app:app --host 0.0.0.0 --port 8080
```

## Data-source limitations

Dukascopy's public historical archive may omit hours or lag. The adapter only uses completed intraday bars and rejects stale/insufficient history. Its current adapter does not provide D1 bars or a guaranteed streaming quote feed. When Dukascopy history is unavailable, Twelve Data can serve as a backup if its optional key is configured. Otherwise the API returns an unavailable/WAIT state.

Economic-calendar and news adapters are separate from price feeds. GDELT articles are not verified economic actual/forecast values. No provider failure is replaced with zero or synthetic market observations.
