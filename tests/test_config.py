import pytest
from forex_quant.config import Settings

def test_live_market_data_environment_is_allowed():
    s = Settings(oanda_environment="live", oanda_live_token="test")
    assert s.oanda_environment == "live"

def test_invalid_environment_rejected():
    with pytest.raises(ValueError):
        Settings(oanda_environment="demo")

def test_phase1_rejects_live_trading_flag():
    with pytest.raises(ValueError):
        Settings(live_trading=True)
