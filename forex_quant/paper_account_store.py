"""Persistent, explicit paper-account configuration (never broker credentials)."""
from __future__ import annotations

import json
from sqlalchemy import String, Text, create_engine
from sqlalchemy.orm import Mapped, mapped_column, sessionmaker
from forex_quant.db import Base


class PaperAccountConfig(Base):
    __tablename__ = "paper_account_config"
    account_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)


_engines = {}\n\ndef _session(database_url: str):
    engine = _engines.get(database_url)
    if engine is None:
        engine = create_engine(database_url, future=True, pool_pre_ping=True)
        Base.metadata.create_all(engine)
        _engines[database_url] = engine
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_paper_account(database_url: str) -> dict | None:
    Session = _session(database_url)
    with Session() as session:
        row = session.get(PaperAccountConfig, "default")
        return json.loads(row.config_json) if row else None


def save_paper_account(database_url: str, config: dict) -> dict:
    Session = _session(database_url)
    encoded = json.dumps(config, sort_keys=True, allow_nan=False)
    with Session.begin() as session:
        row = session.get(PaperAccountConfig, "default")
        if row is None:
            row = PaperAccountConfig(account_id="default", config_json=encoded)
            session.add(row)
        else:
            row.config_json = encoded
    return json.loads(encoded)
