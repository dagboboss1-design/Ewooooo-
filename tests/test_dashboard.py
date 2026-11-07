from fastapi.testclient import TestClient

from forex_quant.dashboard.app import app

client = TestClient(app)


def test_dashboard_serves_mobile_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Ewooooo" in response.text
    assert 'name="viewport"' in response.text


def test_watchlist_contains_requested_assets_and_timeframes():
    response = client.get("/api/dashboard/config")
    assert response.status_code == 200
    payload = response.json()
    symbols = {asset["symbol"] for asset in payload["assets"]}
    assert {"XAU_USD", "XAG_USD", "BTC_USD", "DXY"} <= symbols
    assert {"M5", "M15"} <= set(payload["timeframes"])


def test_dashboard_never_fabricates_live_quotes():
    response = client.get("/api/market")
    assert response.status_code == 200
    payload = response.json()
    assert payload["quotes"] == []
    assert payload["as_of"] is None
    assert payload["status"] == "no_verified_feed"


def test_live_execution_is_not_enabled():
    payload = client.get("/api/dashboard/status").json()
    assert payload["execution_enabled"] is False
