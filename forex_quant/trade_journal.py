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


def performance_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute closed-trade R statistics and breakdowns."""
    def r_multiple(t):
        entry, stop, exit_price = t.get("entry"), t.get("stop_loss"), t.get("exit_price")
        if entry is None or stop is None or exit_price is None:
            return None
        risk = abs(float(entry) - float(stop))
        if risk <= 0:
            return None
        move = float(exit_price) - float(entry)
        return (-move if t.get("side") == "SELL" else move) / risk
    closed = [t for t in trades if t.get("status") == "closed"]
    scored = [(t, r_multiple(t)) for t in closed]
    scored = [(t, r) for t, r in scored if r is not None]
    scored.sort(key=lambda pair: pair[0].get("created_at") or "")
    def stats(items):
        rs = [r for _, r in items]
        gains = sum(r for r in rs if r > 0)
        losses = abs(sum(r for r in rs if r < 0))
        equity = peak = drawdown = 0.0
        for r in rs:
            equity += r
            peak = max(peak, equity)
            drawdown = max(drawdown, peak - equity)
        return {"trades": len(rs), "wins": sum(r > 0 for r in rs), "losses": sum(r < 0 for r in rs),
                "win_rate_pct": round(sum(r > 0 for r in rs) / len(rs) * 100, 2) if rs else None,
                "average_r": round(sum(rs) / len(rs), 3) if rs else None,
                "profit_factor_r": round(gains / losses, 3) if losses else None,
                "max_drawdown_r": round(drawdown, 3) if rs else None}
    by_timeframe = {}
    for trade, r in scored:
        by_timeframe.setdefault(str(trade.get("timeframe") or "—"), []).append((trade, r))
    result = stats(scored)
    result.update({"total_records": len(trades), "open_trades": sum(t.get("status") == "open" for t in trades),
                   "skipped_setups": sum(t.get("status") == "skipped" for t in trades), "closed_trades": len(closed),
                   "unscored_closed": len(closed) - len(scored),
                   "realized_pnl": round(sum(float(t.get("pnl") or 0) for t in closed), 2),
                   "by_timeframe": {tf: stats(items) for tf, items in sorted(by_timeframe.items())}})
    return result