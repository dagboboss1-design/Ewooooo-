from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Any
from sqlalchemy import DateTime, Float, String, Text, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from forex_quant.db import Base

class JournalTrade(Base):
    __tablename__ = "journal_trades"
    trade_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(8), nullable=False)
    entry: Mapped[float | None] = mapped_column(Float, nullable=True)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)
    exit_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    source: Mapped[str] = mapped_column(String(20), nullable=False)
    setup_text: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

_engines: dict[str, Any] = {}
def _factory(url: str):
    engine = _engines.get(url)
    if engine is None:
        engine = create_engine(url, future=True, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        _engines[url] = engine
    return sessionmaker(bind=engine, expire_on_commit=False)

def serialize(t):
    return {k: (getattr(t,k).isoformat() if k in {"created_at","updated_at"} else getattr(t,k)) for k in ("trade_id","created_at","updated_at","symbol","side","timeframe","entry","stop_loss","take_profit","exit_price","pnl","status","source","setup_text","notes")}

def create_trade(url: str, values: dict):
    now=datetime.now(timezone.utc)
    trade=JournalTrade(trade_id=str(uuid.uuid4()),created_at=now,updated_at=now,**values)
    Session=_factory(url)
    with Session.begin() as s: s.add(trade)
    return serialize(trade)

def list_trades(url: str):
    Session=_factory(url)
    with Session() as s: return [serialize(t) for t in s.scalars(select(JournalTrade).order_by(JournalTrade.created_at.desc())).all()]

def update_trade(url: str, trade_id: str, values: dict):
    Session=_factory(url)
    with Session.begin() as s:
        t=s.get(JournalTrade,trade_id)
        if t is None: return None
        for k,v in values.items(): setattr(t,k,v)
        t.updated_at=datetime.now(timezone.utc)
        s.flush()
        result=serialize(t)
    return result
