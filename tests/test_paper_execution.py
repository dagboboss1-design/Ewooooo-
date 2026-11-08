import pytest

from forex_quant.paper_execution import (
    ContractSpecification, CostModel, PaperPosition, account_snapshot, close_partial,
)


def position(side="BUY"):
    return PaperPosition("p1", "EUR/USD", side, 1.1000, 1000, 1000)


def test_cost_model_applies_spread_and_slippage_symmetrically():
    costs = CostModel(spread=0.0002, slippage=0.0001)
    assert costs.entry_fill("BUY", 1.1) == pytest.approx(1.1002)
    assert costs.entry_fill("SELL", 1.1) == pytest.approx(1.0998)
    assert costs.exit_fill("BUY", 1.1) == pytest.approx(1.0998)
    assert costs.exit_fill("SELL", 1.1) == pytest.approx(1.1002)


def test_partial_close_tracks_remaining_quantity_and_account_pnl():
    p = position()
    result = close_partial(
        p, 400, 1.1010, CostModel(commission_per_unit=0.01),
        ContractSpecification(contract_size=1, quote_to_account_rate=1),
    )
    assert result.closed_quantity == 400
    assert result.remaining_quantity == 600
    assert result.status == "open"
    assert result.realized_pnl_account == pytest.approx(0.36)


def test_final_close_marks_position_closed():
    p = position("SELL")
    close_partial(p, 400, 1.0990, CostModel(), ContractSpecification(1, 1))
    result = close_partial(p, 600, 1.0980, CostModel(), ContractSpecification(1, 1))
    assert result.status == "closed"
    assert result.remaining_quantity == 0


def test_rejects_over_close_and_missing_account_specs():
    p = position()
    with pytest.raises(ValueError):
        close_partial(p, 1001, 1.101, CostModel(), ContractSpecification(1, 1))
    with pytest.raises(ValueError):
        ContractSpecification(0, 1)


def test_account_snapshot_marks_open_position_with_exit_costs():
    p = position()
    snapshot = account_snapshot(
        10_000, [p], {"p1": 1.1010}, CostModel(spread=0.0002),
        ContractSpecification(1, 1),
    )
    assert snapshot.unrealized_pnl == pytest.approx(0.8)
    assert snapshot.equity == pytest.approx(10_000.8)


def test_execution_adapter_contract_is_structural():
    from forex_quant.paper_trading import PaperTradingAdapter
    assert hasattr(PaperTradingAdapter, "submit")
