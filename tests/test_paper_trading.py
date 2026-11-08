from dataclasses import replace
from forex_quant.paper_trading import PaperOrder, PaperTradingAdapter

def sample(**changes):
    order = PaperOrder(symbol="EUR/USD", side="BUY", timeframe="M15",
        entry=1.10, stop_loss=1.095, take_profit=1.11, account_balance=10_000)
    return replace(order, **changes)

def test_paper_order_simulates_fill_and_applies_half_percent_risk():
    result = PaperTradingAdapter().submit(sample())
    assert result.accepted is True
    assert result.status == "filled"
    assert result.source == "paper"
    assert result.execution_mode == "simulation_only"
    assert result.risk_amount == 50.0
    assert result.units == 10_000.0

def test_rejects_invalid_buy_stop_and_target_geometry():
    result = PaperTradingAdapter().submit(sample(stop_loss=1.101))
    assert not result.accepted
    assert result.reason == "buy_requires_stop_below_entry_and_target_above"

def test_sell_order_requires_inverse_geometry():
    assert not PaperTradingAdapter().submit(sample(side="SELL")).accepted

def test_kill_switch_blocks_paper_order():
    result = PaperTradingAdapter().submit(sample(kill_switch=True))
    assert not result.accepted
    assert result.reason == "kill_switch_active"

def test_daily_weekly_and_loss_streak_guards():
    adapter = PaperTradingAdapter()
    assert adapter.submit(sample(daily_loss_fraction=0.02)).reason == "daily_loss_limit_reached"
    assert adapter.submit(sample(weekly_loss_fraction=0.05)).reason == "weekly_loss_limit_reached"
    assert adapter.submit(sample(consecutive_losses=3)).reason == "consecutive_loss_pause"

def test_non_finite_values_are_rejected():
    result = PaperTradingAdapter().submit(sample(entry=float("nan")))
    assert not result.accepted
    assert result.reason == "non_finite_order_value"

def test_sell_order_valid_geometry_is_accepted():
    result = PaperTradingAdapter().submit(sample(side="SELL", stop_loss=1.105, take_profit=1.09))
    assert result.accepted
    assert result.side == "SELL"
