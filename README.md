# Forex Quant System — Phase 1 Data Layer

Python 3.11+. Phase 1 provides OANDA candle ingestion, Dukascopy tick download/decoding,
biquote calendar ingestion, GDELT news ingestion, UTC/data-quality normalization,
Parquet snapshots, and SQLAlchemy snapshot metadata.

## Safety and scope

- OANDA `practice` and `live` are supported as **market-data environments**.
- Selecting `OANDA_ENVIRONMENT=live` does not place orders.
- Phase 1 is data-only. There is no order-routing implementation.
- `LIVE_TRADING=false` is retained as a fail-closed deployment setting.
- Never commit `.env`, tokens, account IDs, or downloaded private data.

## Hosted deployment

See [DEPLOY_RAILWAY.md](DEPLOY_RAILWAY.md) for the password-protected Railway deployment checklist. Use the development branch and keep live trading disabled.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

Fill in OANDA credentials. For PostgreSQL, install `.[postgres]` and set `DATABASE_URL`.
SQLite is the local-development default.

## Run tests

```bash
pytest -q
```

## Ingest OANDA candles

```bash
python -m forex_quant.cli candles --instrument EUR_USD --granularity H1 --count 500
```

For live market-data access, set `OANDA_ENVIRONMENT=live` and `OANDA_LIVE_TOKEN`.
For practice data, set `OANDA_ENVIRONMENT=practice` and `OANDA_PRACTICE_TOKEN`.

## Ingest Dukascopy ticks

```bash
python -m forex_quant.cli dukascopy --instrument EURUSD --date 2024-01-02 --hour 13
```

Dukascopy's public historical feed is not guaranteed to have every instrument/hour.
An unavailable archive is recorded as a provider error rather than fabricated as an empty
market observation.

## Ingest calendar and news

```bash
python -m forex_quant.cli calendar
python -m forex_quant.cli news
```

The calendar adapter expects the biquote response to contain an event list. Provider schema
changes are surfaced as validation errors. GDELT results are news articles, not an official
economic calendar and not a substitute for verified event actual/forecast values.

## Snapshot layout

Each ingestion creates a unique snapshot directory:

```text
data/
  snapshots/<snapshot_id>/
    candles.parquet
    ticks.parquet
    calendar.parquet
    news.parquet
    quality.json
    manifest.json
  metadata.db
```

Only datasets included in that snapshot are written. Snapshot IDs are immutable UUIDs.
The manifest stores provider, ingestion time, schema version, row counts, and SHA-256 checksums.

## Notes and limitations

- OANDA candle volume is candle activity count, not centralized FX exchange volume.
- Dukascopy tick volume is provider-specific and should not be treated as consolidated market volume.
- GDELT sentiment is not FinBERT sentiment. This phase stores source metadata and article text;
  model-based sentiment belongs to the later feature/model phases.
- The biquote endpoint and response schema must be verified against the provider's current service.
- Historical availability and licensing vary by provider and instrument.
- Phase 1 does not calculate features, generate trades, or submit orders.
