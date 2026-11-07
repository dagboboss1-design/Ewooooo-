from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

SCHEMA_VERSION = "1.0.0"

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

@dataclass
class DataBundle:
    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=utc_now)
    provider: str = "mixed"
    datasets: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
