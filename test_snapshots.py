import json
import pandas as pd
from forex_quant.models import DataBundle
from forex_quant.snapshots import SnapshotWriter

def test_snapshot_is_written_with_manifest(tmp_path):
    bundle = DataBundle(provider="test", datasets={
        "candles": pd.DataFrame({
            "time": ["2024-01-01T00:00:00Z"],
            "open": [1.0], "high": [1.1], "low": [0.9], "close": [1.05]
        })
    })
    manifest_path = SnapshotWriter(str(tmp_path)).write(bundle)
    manifest = json.loads(manifest_path.read_text())
    assert manifest["snapshot_id"] == bundle.snapshot_id
    assert manifest["row_counts"]["candles"] == 1
    assert "candles.parquet" in manifest["sha256"]
