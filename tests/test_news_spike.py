from forex_quant.news_spike import (
    impacted_instruments,
    normalized_surprise,
    spread_guard,
    tick_spike_score,
)


def test_surprise_requires_history():
    result = normalized_surprise(105, 100, [1])
    assert result.normalized is None
    assert result.classification == "insufficient_history"


def test_surprise_classifies_large_positive_miss():
    result = normalized_surprise(104, 100, [-2, -1, 0, 1, 2])
    assert result.normalized == 2.82842712474619
    assert result.classification == "large_surprise"
    assert result.direction_hint == "positive"


def test_small_surprise_is_no_edge():
    result = normalized_surprise(100.2, 100, [-1, 0, 1])
    assert result.classification == "no_edge"


def test_tick_spike_score_detects_outlier():
    prices = [100 + i * 0.01 for i in range(32)]
    prices[-1] = prices[-2] * 1.01
    score = tick_spike_score(prices, window=30)
    assert score is not None and score > 3


def test_tick_spike_requires_enough_ticks():
    assert tick_spike_score([1, 1.01, 1.02], window=30) is None


def test_spread_guard_blocks_wide_or_invalid_spread():
    assert spread_guard(0.8, 1.0)
    assert not spread_guard(1.2, 1.0)
    assert not spread_guard(-0.1, 1.0)


def test_currency_mapping_is_explicit():
    assert "USD/JPY" in impacted_instruments("USD")
    assert impacted_instruments("UNKNOWN") == ()
