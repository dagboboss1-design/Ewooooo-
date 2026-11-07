from fastapi.testclient import TestClient

from forex_quant.dashboard.app import app

client = TestClient(app)


def test_dashboard_serves_mobile_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Ewooooo" in response.text
    assert 'name="viewport"' in response.text
    assert "AI Trading Assistant" in response.text


def test_watchlist_contains_requested_assets_and_timeframes():
    payload = client.get("/api/dashboard/config").json()
    symbols = {asset["symbol"] for asset in payload["assets"]}
    assert {"XAU/USD", "XAG/USD", "BTC/USD", "DXY"} <= symbols
    assert {"M5", "M15", "M30", "H1", "H4"} <= set(payload["timeframes"])


def test_market_endpoint_does_not_fabricate_quotes(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        twelve_data_api_key="", market_data_provider="twelve_data"
    ))
    payload = client.get("/api/market").json()
    assert payload["quotes"] == []
    assert payload["as_of"] is None
    assert payload["status"] == "awaiting_provider_credentials"


def test_candle_endpoint_requires_key(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        twelve_data_api_key="", market_data_provider="twelve_data"
    ))
    response = client.get("/api/market/candles?symbol=EUR/USD&timeframe=M15")
    assert response.status_code == 503


def test_ai_chat_requires_private_server_key(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(openai_api_key=""))
    response = client.post("/api/ai/chat", json={"message": "Explain RSI"})
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_live_execution_is_not_enabled():
    payload = client.get("/api/dashboard/status").json()
    assert payload["execution_enabled"] is False
