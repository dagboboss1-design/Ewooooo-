from __future__ import annotations
from datetime import date
from .config import Settings
from .models import DataBundle
from .providers.oanda import OandaClient
from .providers.dukascopy import DukascopyClient
from .providers.calendar import BiquoteCalendarClient
from .providers.gdelt import GdeltClient
from .snapshots import SnapshotWriter
from .db import init_db, record_snapshot

async def ingest_candles(settings: Settings, instrument: str, granularity: str, count: int):
    token = settings.oanda_live_token if settings.oanda_environment == "live" else settings.oanda_practice_token
    client = OandaClient(token, settings.oanda_environment)
    frame = await client.candles(instrument, granularity, count, settings.oanda_price_component)
    return persist(settings, DataBundle(provider=f"oanda:{settings.oanda_environment}", datasets={"candles": frame},
                                        metadata={"instrument": instrument, "granularity": granularity}))

async def ingest_dukascopy(settings: Settings, instrument: str, day: date, hour: int):
    frame = await DukascopyClient().ticks(instrument, day, hour)
    return persist(settings, DataBundle(provider="dukascopy", datasets={"ticks": frame},
                                        metadata={"instrument": instrument, "date": day.isoformat(), "hour": hour}))

async def ingest_calendar(settings: Settings):
    frame = await BiquoteCalendarClient(settings.biquote_calendar_url).upcoming(
        settings.biquote_importance, settings.biquote_countries)
    return persist(settings, DataBundle(provider="biquote", datasets={"calendar": frame}))

async def ingest_news(settings: Settings):
    frame = await GdeltClient(settings.gdelt_doc_url).articles(settings.gdelt_query, settings.gdelt_lookback_minutes)
    return persist(settings, DataBundle(provider="gdelt", datasets={"news": frame}))

def persist(settings: Settings, bundle: DataBundle):
    writer = SnapshotWriter(settings.data_dir)
    manifest = writer.write(bundle)
    engine = init_db(settings.database_url)
    record_snapshot(engine, snapshot_id=bundle.snapshot_id, created_at=bundle.created_at,
                    provider=bundle.provider, schema_version="1.0.0",
                    row_counts={k: len(v) for k, v in bundle.datasets.items()},
                    manifest_path=str(manifest.resolve()))
    return manifest
