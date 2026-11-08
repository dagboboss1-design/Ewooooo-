import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from forex_quant.ai_trader import analyze, enrich, rsi
from forex_quant.dashboard import app as dashboard_module


def sample_candles(count=120):
    steps = np.arange(count, dtype=float)
    close = 1.10 + steps * 0.00012 + np.sin(steps / 3.0) * 0.00035
    open_price = close - np.sin(steps / 2.0) * 0.00012
    return pd.DataFrame({
        "time": pd.date_range("2026-01-01", periods=count, freq="15min", tz="UTC"),
        "open": open_price,
        "high": np.maximum(open_price, close) + 0.0005,
        "low": np.minimum(open_price, close) - 0.0005,
        "close": close,
        "volume": np.zeros(count),
    }).set_index("time")


def test_enrich_adds_all_requested_indicators_without_volume():
    frame = sample_candles().drop(columns=["volume"])
    result = enrich(frame)
    assert {"ema20", "ema50", "rsi", "macd", "macd_sig", "bb_upper", "bb_lower", "pctb", "atr", "volume"} <= set(result)
    assert result["volume"].eq(0).all()
    assert result[["ema20", "ema50", "rsi", "macd", "pctb", "atr"]].notna().all().all()


def test_rsi_handles_zero_loss_series():
    values = rsi(pd.Series([1.0 + i for i in range(30)]))
    assert values.iloc[-1] == 100.0


def test_analysis_returns_paper_only_confluence_and_no_fake_volume_vote():
    result = analyze(sample_candles(), "EUR/USD", "M15")
    assert result["symbol"] == "EUR/USD"
    assert result["timeframe"] == "M15"
    assert result["execution"] == "PAPER_ANALYSIS_ONLY"
    assert result["indicators"]["vol_ratio"] is None
    assert any("Volume inconclusive" in note for note in result["notes"])
    assert result["signal"] in {"BUY", "SELL", "STRONG BUY", "STRONG SELL", "HOLD / NO TRADE"}


def test_analysis_rejects_insufficient_candles():
    with pytest.raises(ValueError, match="at least 60"):
        analyze(sample_candles(50), "EUR/USD", "M15")


def test_dashboard_technical_analysis_uses_existing_market_candle_adapter(monkeypatch):
    async def fake_market_candles(symbol="EUR/USD", timeframe="M15", outputsize=300):
        frame = sample_candles()
        records = frame.reset_index().rename(columns={"index": "time"}).to_dict(orient="records")
        for row in records:
            row["time"] = row["time"].isoformat()
        return {
            "symbol": symbol,
            "timeframe": timeframe,
            "provider": "test_provider",
            "data_status": "primary_feed",
            "candles": records,
        }

    monkeypatch.setattr(dashboard_module, "market_candles", fake_market_candles)
    client = TestClient(dashboard_module.app)
    response = client.get("/api/analysis/technical?symbol=EUR%2FUSD&timeframe=M15")
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "test_provider"
    assert payload["candles_used"] >= 60
    assert payload["execution"] == "PAPER_ANALYSIS_ONLY"
    assert "indicators" in payload


def test_dashboard_technical_analysis_rejects_unsupported_dxy():
    client = TestClient(dashboard_module.app)
    response = client.get("/api/analysis/technical?symbol=DXY&timeframe=M15")
    assert response.status_code == 400
