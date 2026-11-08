from fastapi.testclient import TestClient

from forex_quant.dashboard.app import app

client = TestClient(app)


def test_dashboard_serves_mobile_page():
    response = client.get("/")
    assert response.status_code == 200
    assert "Ewooooo" in response.text
    assert 'name="viewport"' in response.text
    assert "AI Trading Assistant" in response.text
    assert 'id="candles"' in response.text
    assert 'id="chart-symbol"' in response.text


def test_watchlist_contains_requested_assets_and_timeframes():
    payload = client.get("/api/dashboard/config").json()
    symbols = {asset["symbol"] for asset in payload["assets"]}
    assert {"XAU/USD", "XAG/USD", "BTC/USD", "DXY"} <= symbols
    assert {"M5", "M15", "M30", "H1", "H4", "D1"} <= set(payload["timeframes"])


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


def test_candle_endpoint_rejects_unknown_market(monkeypatch):
    response = client.get("/api/market/candles?symbol=INVALID&timeframe=M15")
    assert response.status_code == 400


def test_ai_chat_falls_back_to_offline_mode_without_private_server_key(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(openai_api_key=""))
    response = client.post("/api/ai/chat", json={"message": "Explain RSI"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_mode"] == "offline"
    assert payload["model"] == "ewo-offline-guide"
    assert "RSI measures recent momentum" in payload["answer"]
    assert payload["market_data_status"] == "not_connected"


def test_live_execution_is_not_enabled():
    payload = client.get("/api/dashboard/status").json()
    assert payload["execution_enabled"] is False



def test_journal_create_close_and_summary(tmp_path, monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    db_url = "sqlite:///" + str(tmp_path / "journal.db")
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(database_url=db_url))
    created = client.post("/api/journal", json={"symbol":"EUR/USD","side":"BUY","timeframe":"M15","setup_text":"BUY EUR/USD"})
    assert created.status_code == 201
    trade = created.json()["trade"]
    assert trade["status"] == "open"
    assert "No broker order was placed" in created.json()["message"]
    closed = client.patch("/api/journal/" + trade["trade_id"], json={"exit_price":1.09,"pnl":12.5,"status":"closed"})
    assert closed.status_code == 200
    summary = client.get("/api/journal").json()
    assert summary["count"] == 1 and summary["closed_count"] == 1
    assert summary["realized_pnl"] == 12.5


def test_journal_rejects_invalid_side():
    response = client.post("/api/journal", json={"symbol":"EUR/USD","side":"HOLD","setup_text":"test"})
    assert response.status_code == 400


def test_daily_timeframe_maps_to_provider_interval(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    import pandas as pd
    class FakeTwelveData:
        def __init__(self, key, timeout=20): pass
        async def candles(self, symbol, interval, outputsize):
            assert interval == "1day"
            return pd.DataFrame([{"time":"2026-11-05","open":1.0,"high":1.1,"low":0.9,"close":1.05}])
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(twelve_data_api_key="test", market_data_provider="twelve_data"))
    monkeypatch.setattr(dashboard_module, "TwelveDataClient", FakeTwelveData)
    response = client.get("/api/market/candles?symbol=EUR/USD&timeframe=D1&outputsize=80")
    assert response.status_code == 200
    assert response.json()["timeframe"] == "D1"
    assert response.json()["candles"][0]["close"] == 1.05

def test_ai_chat_uses_daily_and_selected_timeframe_candles(monkeypatch):
    import pandas as pd
    from forex_quant.dashboard import app as dashboard_module
    dashboard_module._PROVIDER_CACHE.clear()
    class FakeProvider:
        def __init__(self, key): pass
        async def candles(self, symbol, interval, outputsize):
            assert interval in {"1day", "15min"}
            return pd.DataFrame([{"time":f"2026-10-{i:02d}","open":1.0+i*.001,"high":1.01+i*.001,"low":.99+i*.001,"close":1.005+i*.001,"volume":10} for i in range(1, 81)])
    captured = {}
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"output_text":"WAIT. Daily context is bullish."}
    class FakeAsyncClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            captured.update(json)
            return FakeResponse()
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(openai_api_key="test-openai", twelve_data_api_key="test-data", market_data_provider="twelve_data"))
    monkeypatch.setattr(dashboard_module, "TwelveDataClient", FakeProvider)
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post("/api/ai/chat", json={"message":"Analyse EUR/USD", "symbol":"EUR/USD", "timeframe":"M15"})
    assert response.status_code == 200
    assert response.json()["daily_bias"] in {"BULLISH", "BEARISH", "NEUTRAL"}
    assert "daily_bias" in captured["instructions"] and "entry_candles" in captured["instructions"]
    assert "technical_analysis" in captured["instructions"] and "indicators" in captured["instructions"]


def test_ai_chat_rejects_unsupported_timeframe():
    response = client.post("/api/ai/chat", json={"message":"Analyse", "timeframe":"W1"})
    assert response.status_code == 422



def test_chat_frontend_displays_daily_bias_metadata():
    from pathlib import Path
    script = Path("forex_quant/dashboard/static/app.js").read_text()
    assert "D1 BIAS:" in script
    assert "market_data_status" in script

def test_journal_analytics_calculates_r_and_timeframe_breakdown():
    from forex_quant.trade_journal import performance_summary
    trades = [
        {"status":"closed","side":"BUY","entry":1.10,"stop_loss":1.09,"exit_price":1.12,"timeframe":"M15","pnl":20},
        {"status":"closed","side":"SELL","entry":1.20,"stop_loss":1.21,"exit_price":1.18,"timeframe":"H1","pnl":20},
        {"status":"open","side":"BUY","entry":1.1,"stop_loss":1.09,"exit_price":None,"timeframe":"M15"},
        {"status":"skipped","side":"BUY","entry":1.1,"stop_loss":1.09,"exit_price":None,"timeframe":"M15"},
    ]
    result = performance_summary(trades)
    assert result["trades"] == 2
    assert result["win_rate_pct"] == 100
    assert result["average_r"] == 2.0
    assert result["open_trades"] == 1
    assert result["skipped_setups"] == 1
    assert set(result["by_timeframe"]) == {"M15", "H1"}

def test_journal_frontend_has_analytics_and_skip_action():
    from pathlib import Path
    script = Path("forex_quant/dashboard/static/app.js").read_text()
    page = Path("forex_quant/dashboard/static/index.html").read_text()
    assert "Skip setup · Log" in script
    assert "journal-analytics" in page
    assert "renderJournalAnalytics" in script


def test_journal_can_log_skipped_setup(tmp_path, monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    db_url = "sqlite:///" + str(tmp_path / "skipped.db")
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(database_url=db_url))
    response = client.post("/api/journal", json={"symbol":"EUR/USD","side":"BUY","timeframe":"M15","entry":1.1,"stop_loss":1.09,"take_profit":1.12,"setup_text":"Test setup","status":"skipped"})
    assert response.status_code == 201
    assert response.json()["trade"]["status"] == "skipped"
    summary = client.get("/api/journal").json()["analytics"]
    assert summary["skipped_setups"] == 1


def test_chart_refresh_rejects_stale_responses_and_clears_failed_data():
    from pathlib import Path
    script = Path("forex_quant/dashboard/static/app.js").read_text()
    assert "let candleRequestId=0" in script
    assert "if(requestId!==candleRequestId)return" in script
    assert "window.lastCandleRows=null" in script
    assert "setInterval(loadCandles,900000)" in script
    assert "setInterval(loadDailyBias,21600000)" in script


def test_health_and_readiness_probes(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        market_data_provider="twelve_data", twelve_data_api_key="", openai_api_key=""
    ))
    health = client.get("/healthz")
    ready = client.get("/readyz")
    assert health.status_code == 200 and health.json() == {"status": "ok"}
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    assert ready.json()["market_data_configured"] is False
    assert ready.json()["ai_configured"] is False
    assert ready.json()["execution_enabled"] is False



def test_signal_scan_requires_explicit_provider_credentials(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        market_data_provider="twelve_data", twelve_data_api_key=""
    ))
    response = client.post("/api/signals/scan", json={
        "symbol":"EUR/USD", "timeframe":"M15", "equity":10000,
        "quote_to_account_rate":1
    })
    assert response.status_code == 503


def test_signal_scan_uses_only_completed_candles(monkeypatch):
    import pandas as pd
    from forex_quant.dashboard import app as dashboard_module
    captured = {}
    class FakeProvider:
        def __init__(self, key): pass
        async def candles(self, symbol, interval, outputsize):
            return pd.DataFrame([{
                "time":f"2026-10-{i:02d}", "open":1.0, "high":1.1,
                "low":0.9, "close":1.01
            } for i in range(1, 71)])
    def no_signal(frame, instrument, equity, **kwargs):
        captured["rows"] = len(frame)
        return None
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        market_data_provider="twelve_data", twelve_data_api_key="test"
    ))
    monkeypatch.setattr(dashboard_module, "TwelveDataClient", FakeProvider)
    monkeypatch.setattr(dashboard_module, "generate_signal", no_signal)
    response = client.post("/api/signals/scan", json={
        "symbol":"EUR/USD", "timeframe":"M15", "equity":10000,
        "quote_to_account_rate":1
    })
    assert response.status_code == 200
    assert response.json()["status"] == "no_setup"
    assert captured["rows"] == 69


def test_signal_scan_rejects_unknown_symbol():
    response = client.post("/api/signals/scan", json={
        "symbol":"DXY", "timeframe":"M15", "equity":10000,
        "quote_to_account_rate":1
    })
    assert response.status_code == 400


def test_dashboard_has_five_focused_pages_and_navigation():
    from pathlib import Path
    page = client.get("/").text
    script = Path("forex_quant/dashboard/static/app.js").read_text()
    for page_id, label in [
        ("markets", "Markets"),
        ("signals", "Signals"),
        ("ai", "AI Assistant"),
        ("journal", "Journal"),
        ("news", "News"),
    ]:
        assert f'href="#{ "ai-chat" if page_id == "ai" else page_id }" data-page="{page_id}"' in page
        assert f'data-page="{page_id}"' in page
        assert label in page
    assert "function show(page)" in script
    assert "panel.hidden=panel.dataset.page!==page" in script
    assert "location.hash" in script
    assert "if(page==='signals')" in script
    assert "requestAnimationFrame" in script
    assert "drawCandles(window.lastCandleRows)" in script
    assert "appendAIDiagnostics(pending,data)" in script
    assert "AI CONNECTION DIAGNOSTIC" in script
    assert '[data-page][hidden]' in Path("forex_quant/dashboard/static/styles.css").read_text()



def test_news_endpoint_returns_calendar_and_headlines(monkeypatch):
    import pandas as pd
    from forex_quant.dashboard import app as dashboard_module
    class FakeCalendar:
        def __init__(self, endpoint): pass
        async def upcoming(self, importance, countries):
            assert importance == "high"
            assert "US" in countries
            return pd.DataFrame([{"event_id":"evt-1","title":"US CPI","event_time":pd.Timestamp("2026-11-08T12:30:00Z"),"source":"biquote"}])
    class FakeGdelt:
        def __init__(self, endpoint): pass
        async def articles(self, query, lookback_minutes):
            assert "forex" in query
            return pd.DataFrame([{"title":"Central bank update","url":"https://example.com/story","published_at":pd.Timestamp("2026-11-08T11:00:00Z"),"source":"gdelt"}])
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings())
    monkeypatch.setattr(dashboard_module, "BiquoteCalendarClient", FakeCalendar)
    monkeypatch.setattr(dashboard_module, "GdeltClient", FakeGdelt)
    response = client.get("/api/news")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "live"
    assert payload["events"][0]["title"] == "US CPI"
    assert payload["headlines"][0]["title"] == "Central bank update"
    assert payload["errors"] == {}


def test_news_endpoint_reports_provider_errors_without_fake_events(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    class BrokenProvider:
        def __init__(self, endpoint): pass
        async def upcoming(self, **kwargs):
            raise ValueError("calendar schema changed")
    class EmptyHeadlines:
        def __init__(self, endpoint): pass
        async def articles(self, **kwargs):
            import pandas as pd
            return pd.DataFrame()
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings())
    monkeypatch.setattr(dashboard_module, "BiquoteCalendarClient", BrokenProvider)
    monkeypatch.setattr(dashboard_module, "GdeltClient", EmptyHeadlines)
    response = client.get("/api/news")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "unavailable"
    assert payload["events"] == []
    assert payload["headlines"] == []
    assert "schema changed" in payload["errors"]["calendar"]
    assert payload["headlines_status"] == "empty"

 
def test_ai_chat_offline_mode_answers_without_openai_key(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(openai_api_key=""))
    response = client.post("/api/ai/chat", json={"message":"Explain RSI and MACD", "symbol":"EUR/USD", "timeframe":"M15"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["assistant_mode"] == "offline"
    assert payload["model"] == "ewo-offline-guide"
    assert "RSI measures recent momentum" in payload["answer"]
    assert "Execution remains OFF" in payload["answer"]
    assert payload["market_data_status"] == "not_connected"


def test_ai_chat_uses_openai_when_configured(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"output_text": "OpenAI verified response"}
    class FakeAsyncClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            assert url == "https://api.openai.com/v1/responses"
            assert headers["Authorization"] == "Bearer test-openai"
            assert json["model"] == "gpt-4.1-mini"
            return FakeResponse()
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        openai_api_key="test-openai", openai_model="gpt-4.1-mini"
    ))
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post("/api/ai/chat", json={"message":"Explain RSI"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "openai"
    assert payload["assistant_mode"] == "openai"
    assert payload["answer"] == "OpenAI verified response"
    assert payload["execution_enabled"] is False


def test_ai_chat_offline_mode_does_not_claim_to_analyse_chart(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(openai_api_key=""))
    response = client.post("/api/ai/chat", json={
        "message":"Analyse this chart", "chart_image":"data:image/png;base64,aGVsbG8="
    })
    assert response.status_code == 200
    payload = response.json()
    assert payload["chart_received"] is True
    assert payload["chart_analysis"] == "not_supported_offline"
    assert "cannot perform visual chart recognition" in payload["answer"]


def test_news_spike_check_enforces_spread_guard():
    ticks = [100+i*0.01 for i in range(32)]
    ticks[-1] = ticks[-2] * 1.01
    response = client.post("/api/news/spike-check", json={"ticks":ticks,"spread":2.0,"maximum_spread":1.0})
    assert response.status_code == 200
    assert response.json()["spike_detected"] is True
    assert response.json()["alert_eligible"] is False
    assert response.json()["execution_enabled"] is False


def test_news_currency_impact_mapping():
    response = client.get("/api/news/impact/USD")
    assert response.status_code == 200 and "EUR/USD" in response.json()["instruments"]


def test_calendar_history_route_returns_provider_records(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    class FakeCalendar:
        def __init__(self, endpoint): pass
        async def event_history(self, event_id):
            assert event_id == "evt-1"
            return [{"actual":3.1,"forecast":3.0,"previous":2.9}]
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings())
    monkeypatch.setattr(dashboard_module, "BiquoteCalendarClient", FakeCalendar)
    response = client.get("/api/news/events/evt-1/history")
    assert response.status_code == 200 and response.json()["observations"] == 1


def test_news_spike_check_rejects_nonfinite_tick_values():
    response = client.post('/api/news/spike-check', json={'ticks':[100, 100.1, "nan"], 'spread':0.5, 'maximum_spread':1.0})
    assert response.status_code == 422


def test_ai_chat_prefers_cloudflare_worker_and_passes_market_context(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    captured = {}
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"answer":"Claude response with current sources","model":"claude-sonnet-current","web_search_used":True,"citations":[{"url":"https://example.com"}]}
    class FakeAsyncClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, json, **kwargs):
            captured.update(json)
            assert url == "https://worker.example/ai"
            return FakeResponse()
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        cloudflare_worker_url="https://worker.example/ai", openai_api_key="", pollinations_api_key=""
    ))
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post("/api/ai/chat", json={"message":"Analyse gold","symbol":"XAU/USD","timeframe":"M15"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["provider"] == "cloudflare_worker"
    assert payload["web_search_used"] is True
    assert captured["symbol"] == "XAU/USD"
    assert "daily_bias" in captured["market_context"]


def test_ai_chat_uses_pollinations_when_worker_is_not_configured(monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    class FakeResponse:
        def raise_for_status(self): pass
        def json(self): return {"choices":[{"message":{"content":"Pollinations backup answer"}}]}
    class FakeAsyncClient:
        def __init__(self, timeout): pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def post(self, url, headers, json):
            assert url == "https://gen.pollinations.ai/v1/chat/completions"
            assert headers["Authorization"] == "Bearer test-pollinations"
            assert json["model"] == "anthropic/claude-sonnet-4.6"
            return FakeResponse()
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(
        cloudflare_worker_url="", pollinations_api_key="test-pollinations", openai_api_key=""
    ))
    monkeypatch.setattr(dashboard_module.httpx, "AsyncClient", FakeAsyncClient)
    response = client.post("/api/ai/chat", json={"message":"Explain RSI"})
    assert response.status_code == 200
    assert response.json()["provider"] == "pollinations"
    assert response.json()["web_search_used"] is False


def test_phase5_session_percentile_and_event_window():
    from forex_quant.news_spike import session_spike_threshold, event_window_status
    assert session_spike_threshold([1,2,3,4,5], 99) == 5
    assert session_spike_threshold([], 99) is None
    result = event_window_status("2026-11-08T12:30:00Z", "2026-11-08T12:31:30Z")
    assert result["within_window"] is True
    assert result["seconds_from_event"] == 90
    outside = event_window_status("2026-11-08T12:30:00Z", "2026-11-08T12:32:01Z")
    assert outside["within_window"] is False


def test_phase5_event_window_requires_timezone():
    from forex_quant.news_spike import event_window_status
    import pytest
    with pytest.raises(ValueError):
        event_window_status("2026-11-08T12:30:00", "2026-11-08T12:31:00Z")


def test_phase5_event_analysis_returns_surprise_not_trade_signal():
    response = client.post("/api/news/event-analysis", json={
        "actual": 3.2, "forecast": 3.0, "historical_surprises": [-0.1, 0.0, 0.1],
        "event_time": "2026-11-08T12:30:00Z", "observed_time": "2026-11-08T12:31:00Z"
    })
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "large_surprise"
    assert data["surprise_sign"] == "positive"
    assert data["event_window"]["within_window"] is True
    assert "not a BUY/SELL" in data["interpretation"]
    assert data["execution_enabled"] is False


def test_phase5_session_threshold_endpoint():
    response = client.post("/api/news/session-threshold", json={"historical_scores": list(range(1, 101))})
    assert response.status_code == 200
    data = response.json()
    assert data["percentile"] == 99
    assert data["threshold"] == 99
    assert data["status"] == "ready"


def test_phase5_event_analysis_rejects_missing_history_shape():
    response = client.post("/api/news/event-analysis", json={"actual": 3, "forecast": 2, "historical_surprises": "bad"})
    assert response.status_code == 422


def test_paper_account_persists_and_partial_closes_reconcile(tmp_path, monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    db_url = "sqlite:///" + str(tmp_path / "paper-account.db")
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(database_url=db_url))
    configured = client.put("/api/paper/account", json={
        "starting_balance": 10000, "currency": "USD", "spread": 0.0002,
        "slippage": 0.0001, "commission_per_unit": 0.001,
        "contract_specs": {"EUR/USD": {"contract_size": 1, "quote_to_account_rate": 1}}
    })
    assert configured.status_code == 200
    assert configured.json()["execution_enabled"] is False
    assert client.get("/api/paper/account").json()["account"]["currency"] == "USD"

    opened = client.post("/api/paper/orders", json={
        "symbol": "EUR/USD", "side": "BUY", "timeframe": "M15",
        "entry": 1.1, "stop_loss": 1.095, "take_profit": 1.11,
        "account_balance": 10000
    })
    assert opened.status_code == 201
    trade_id = opened.json()["trade"]["trade_id"]
    assert abs(opened.json()["simulated_entry_fill"] - 1.1002) < 1e-8

    partial = client.post(f"/api/paper/positions/{trade_id}/partial-close", json={
        "quantity": 4000, "exit_price": 1.105
    })
    assert partial.status_code == 200
    assert partial.json()["close"]["remaining_quantity"] == 6000
    assert partial.json()["execution_enabled"] is False

    final = client.post(f"/api/paper/positions/{trade_id}/partial-close", json={
        "quantity": 6000, "exit_price": 1.105
    })
    assert final.status_code == 200
    assert final.json()["status"] == "paper_position_closed"
    assert final.json()["trade"]["status"] == "closed"
    assert abs(final.json()["trade"]["pnl"] - 26.0) < 1e-8
    import json
    history = json.loads(final.json()["trade"]["setup_text"])["partial_closes"]
    assert len(history) == 2
    snapshot = client.post("/api/paper/account/snapshot", json={"marks": {}})
    assert snapshot.status_code == 200
    assert snapshot.json()["realized_pnl"] == 26.0
    assert snapshot.json()["fees"] == 20.0
    assert snapshot.json()["equity"] == 10026.0
    assert snapshot.json()["execution_enabled"] is False
    reconciliation = client.get("/api/paper/reconcile").json()
    assert reconciliation["status"] == "consistent"
    assert reconciliation["checked_paper_records"] == 1
    assert reconciliation["execution_enabled"] is False
    assert client.get("/api/paper/positions").json()["count"] == 0


def test_paper_partial_close_requires_explicit_contract_specs(tmp_path, monkeypatch):
    from forex_quant.dashboard import app as dashboard_module
    db_url = "sqlite:///" + str(tmp_path / "paper-no-spec.db")
    monkeypatch.setattr(dashboard_module, "get_settings", lambda: dashboard_module.Settings(database_url=db_url))
    opened = client.post("/api/paper/orders", json={
        "symbol": "EUR/USD", "side": "BUY", "timeframe": "M15",
        "entry": 1.1, "stop_loss": 1.095, "take_profit": 1.11,
        "account_balance": 10000
    })
    trade_id = opened.json()["trade"]["trade_id"]
    response = client.post(f"/api/paper/positions/{trade_id}/partial-close", json={
        "quantity": 1000, "exit_price": 1.105
    })
    assert response.status_code == 409
    assert "Configure the paper account" in response.json()["detail"]


def test_paper_account_dashboard_has_manual_order_equity_and_reconciliation_controls():
    from pathlib import Path
    page = Path("forex_quant/dashboard/static/index.html").read_text()
    script = Path("forex_quant/dashboard/static/app.js").read_text()
    for element_id in ("paper-balance", "paper-currency", "paper-contracts",
                       "submit-paper-order", "paper-equity", "refresh-paper-equity",
                       "run-paper-reconcile", "paper-positions"):
        assert f'id="{element_id}"' in page
    assert "fetch('/api/paper/orders'" in script
    assert "fetch('/api/paper/account/snapshot'" in script
    assert "fetch('/api/paper/reconcile'" in script

def test_hosted_dashboard_requires_basic_auth_when_enabled(monkeypatch):
    monkeypatch.setenv("DASHBOARD_AUTH_REQUIRED", "true")
    monkeypatch.setenv("DASHBOARD_USERNAME", "ewooooo-test")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "test-password")
    denied = client.get("/", follow_redirects=False)
    assert denied.status_code == 401
    assert "WWW-Authenticate" in denied.headers
    allowed = client.get("/", auth=("ewooooo-test", "test-password"))
    assert allowed.status_code == 200
    health = client.get("/healthz")
    assert health.status_code == 200


def test_hosted_dashboard_fails_closed_if_auth_secret_missing(monkeypatch):
    monkeypatch.setenv("DASHBOARD_AUTH_REQUIRED", "true")
    monkeypatch.delenv("DASHBOARD_USERNAME", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)
    response = client.get("/")
    assert response.status_code == 503
