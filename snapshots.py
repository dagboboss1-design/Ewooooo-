from __future__ import annotations
import hashlib, json
from pathlib import Path
import pandas as pd
from .models import DataBundle, SCHEMA_VERSION
from .quality import quality_report, normalize_utc

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

class SnapshotWriter:
    def __init__(self, data_dir: str):
        self.root = Path(data_dir) / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, bundle: DataBundle, expected_frequency="1h") -> Path:
        target = self.root / bundle.snapshot_id
        target.mkdir(parents=True, exist_ok=False)
        row_counts, checksums, quality = {}, {}, {}
        for name, frame in bundle.datasets.items():
            if not isinstance(frame, pd.DataFrame):
                raise TypeError(f"Dataset {name} must be a pandas DataFrame")
            out = frame.copy()
            time_col = next((c for c in ("time", "timestamp", "event_time", "published_at") if c in out.columns), None)
            if time_col and not out.empty:
                out = normalize_utc(out, time_col)
                quality[name] = quality_report(out, time_column=time_col, expected_frequency=expected_frequency) if time_col == "time" else {"rows": len(out)}
            path = target / f"{name}.parquet"
            out.to_parquet(path, index=False)
            row_counts[name] = int(len(out))
            checksums[path.name] = _sha256(path)
        (target / "quality.json").write_text(json.dumps(quality, indent=2, default=str))
        manifest = {
            "snapshot_id": bundle.snapshot_id,
            "created_at": bundle.created_at.isoformat(),
            "provider": bundle.provider,
            "schema_version": SCHEMA_VERSION,
            "metadata": bundle.metadata,
            "row_counts": row_counts,
            "sha256": checksums,
        }
        manifest_path = target / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, indent=2, default=str))
        return manifest_path
