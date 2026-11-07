from pathlib import Path
from datetime import datetime

from sqlalchemy import create_engine, String, DateTime, JSON
from sqlalchemy.orm import (
    DeclarativeBase, Mapped, mapped_column, sessionmaker
)


class Base(DeclarativeBase):
    pass


class SnapshotRecord(Base):
    __tablename__ = "snapshots"

    snapshot_id: Mapped[str] = mapped_column(
        String(36), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(100), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(20), nullable=False)
    row_counts: Mapped[dict] = mapped_column(JSON, nullable=False)
    manifest_path: Mapped[str] = mapped_column(
        String(1024), nullable=False
    )


def make_engine(database_url: str):
    if database_url.startswith("sqlite:///"):
        path = database_url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, future=True)

    return create_engine(
        database_url, pool_pre_ping=True, future=True
    )


def init_db(database_url: str):
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    return engine


def record_snapshot(
    engine, *, snapshot_id, created_at, provider,
    schema_version, row_counts, manifest_path
):
    Session = sessionmaker(bind=engine)

    with Session.begin() as session:
        session.add(
            SnapshotRecord(
                snapshot_id=snapshot_id,
                created_at=created_at,
                provider=provider,
                schema_version=schema_version,
                row_counts=row_counts,
                manifest_path=manifest_path,
            )
        )
