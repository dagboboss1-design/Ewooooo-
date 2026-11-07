from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .models import DataBundle, SCHEMA_VERSION
from .quality import normalize_utc, quality_report


def sha256_file(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


class SnapshotWriter:
    def __init__(self, data_dir):
        self.root = Path(data_dir) / "snapshots"
        self.root.mkdir(parents=True, exist_ok=True)

    def write(self, bundle: DataBundle, expected_frequency="1h"):
        target = self.root / bundle.snapshot_id
        target.mkdir(parents=True, exist_ok=False)

        row_counts = {}
        checksums = {}
        quality = {}

        try:
            for name, frame in bundle.datasets.items():
                if not isinstance(frame, pd.DataFrame):
                    raise TypeError(f"{name} must be a DataFrame")

                output = frame.copy()

                time_column = next(
                    (column for column in (
                        "time", "timestamp",
                        "event_time", "published_at"
                    ) if column in output.columns),
                    None
                )

                if time_column and not output.empty:
                    output = normalize_utc(output, time_column)

                    if time_column == "time":
                        quality[name] = quality_report(
                            output,
                            time_column=time_column,
                            expected_frequency=expected_frequency
                        )
                    else:
                        quality[name] = {"rows": len(output)}

                path = target / f"{name}.parquet"
                output.to_parquet(path, index=False)

                row_counts[name] = len(output)
                checksums[path.name] = sha256_file(path)

            (target / "quality.json").write_text(
                json.dumps(quality, indent=2, default=str)
            )

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
            manifest_path.write_text(
                json.dumps(manifest, indent=2, default=str)
            )

            return manifest_path

        except Exception:
            import shutil
            shutil.rmtree(target, ignore_errors=True)
            raise
