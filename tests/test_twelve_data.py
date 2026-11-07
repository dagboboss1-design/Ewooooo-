import httpx
import pytest
import respx

from forex_quant.providers.twelve_data import TwelveDataClient


@pytest.mark.asyncio
@respx.mock
async def test_quote_normalizes_verified_price():
    route = respx.get("https://api.twelvedata.com/quote").mock(
        return_value=httpx.Response(200, json={"symbol": "EUR/USD", "close": "1.08321", "datetime": "2026-11-08 10:15:00"})
    )
    quote = await TwelveDataClient("test-key").quote("EUR/USD")
    assert route.called
    assert quote["mid"] == 1.08321
    assert quote["bid"] is None and quote["ask"] is None
    assert quote["source"] == "twelve_data"


@pytest.mark.asyncio
@respx.mock
async def test_candles_parse_ohlc():
    respx.get("https://api.twelvedata.com/time_series").mock(
        return_value=httpx.Response(200, json={"values": [{"datetime": "2026-11-08 10:15:00", "open": "1.1", "high": "1.2", "low": "1.0", "close": "1.15", "volume": "12"}]})
    )
    frame = await TwelveDataClient("test-key").candles("EUR/USD", "15min", 1)
    assert len(frame) == 1
    assert frame.iloc[0]["close"] == 1.15


@pytest.mark.asyncio
@respx.mock
async def test_provider_errors_are_not_silently_converted():
    respx.get("https://api.twelvedata.com/quote").mock(
        return_value=httpx.Response(200, json={"code": 429, "message": "API credits exhausted", "status": "error"})
    )
    with pytest.raises(LookupError, match="API credits exhausted"):
        await TwelveDataClient("test-key").quote("EUR/USD")
