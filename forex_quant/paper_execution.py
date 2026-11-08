"""Broker-neutral paper execution accounting primitives.

All costs and P&L are simulated. Account-currency P&L is calculated only
when explicit contract-size and quote-to-account conversion specifications
are supplied; no instrument defaults are guessed.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Protocol, runtime_checkable


@runtime_checkable
class ExecutionAdapter(Protocol):
    """Minimal broker-neutral execution contract."""

    def submit(self, order): ...
    def close(self, position_id: str, quantity: float, price: float): ...


@dataclass(frozen=True)
class CostModel:
    spread: float = 0.0
    slippage: float = 0.0
    commission_per_unit: float = 0.0

    def __post_init__(self):
        values = (self.spread, self.slippage, self.commission_per_unit)
        if any(not isfinite(float(v)) or v < 0 for v in values):
            raise ValueError("cost inputs must be finite and non-negative")

    def entry_fill(self, side: str, mid_price: float) -> float:
        _positive(mid_price, "mid_price")
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        half_spread = self.spread / 2
        return mid_price + half_spread + self.slippage if side == "BUY" else mid_price - half_spread - self.slippage

    def exit_fill(self, side: str, mid_price: float) -> float:
        _positive(mid_price, "mid_price")
        side = side.upper()
        if side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        half_spread = self.spread / 2
        return mid_price - half_spread - self.slippage if side == "BUY" else mid_price + half_spread + self.slippage


@dataclass(frozen=True)
class ContractSpecification:
    contract_size: float
    quote_to_account_rate: float

    def __post_init__(self):
        _positive(self.contract_size, "contract_size")
        _positive(self.quote_to_account_rate, "quote_to_account_rate")


@dataclass
class PaperPosition:
    position_id: str
    symbol: str
    side: str
    entry_price: float
    original_quantity: float
    remaining_quantity: float
    realized_pnl_account: float = 0.0
    fees_account: float = 0.0
    status: str = "open"

    def __post_init__(self):
        self.side = self.side.upper()
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("side must be BUY or SELL")
        _positive(self.entry_price, "entry_price")
        _positive(self.original_quantity, "original_quantity")
        _positive(self.remaining_quantity, "remaining_quantity")
        if self.remaining_quantity > self.original_quantity:
            raise ValueError("remaining quantity cannot exceed original quantity")


@dataclass(frozen=True)
class CloseResult:
    closed_quantity: float
    remaining_quantity: float
    gross_pnl_account: float
    commission_account: float
    realized_pnl_account: float
    status: str


def close_partial(
    position: PaperPosition,
    quantity: float,
    exit_mid_price: float,
    costs: CostModel,
    contract: ContractSpecification,
) -> CloseResult:
    """Close part/all of a position; P&L is account-currency only with explicit specs."""
    if position.status != "open":
        raise ValueError("position is not open")
    _positive(quantity, "quantity")
    _positive(exit_mid_price, "exit_mid_price")
    if quantity > position.remaining_quantity + 1e-12:
        raise ValueError("close quantity exceeds remaining quantity")
    quantity = min(quantity, position.remaining_quantity)
    exit_fill = costs.exit_fill(position.side, exit_mid_price)
    direction = 1.0 if position.side == "BUY" else -1.0
    gross = (exit_fill - position.entry_price) * direction * quantity * contract.contract_size
    commission = quantity * costs.commission_per_unit * contract.quote_to_account_rate
    gross_account = gross * contract.quote_to_account_rate
    net = gross_account - commission
    position.remaining_quantity = max(0.0, position.remaining_quantity - quantity)
    position.realized_pnl_account += net
    position.fees_account += commission
    if position.remaining_quantity <= 1e-12:
        position.remaining_quantity = 0.0
        position.status = "closed"
    return CloseResult(
        closed_quantity=quantity,
        remaining_quantity=position.remaining_quantity,
        gross_pnl_account=round(gross_account, 8),
        commission_account=round(commission, 8),
        realized_pnl_account=round(net, 8),
        status=position.status,
    )


@dataclass(frozen=True)
class PaperAccountSnapshot:
    starting_balance: float
    realized_pnl: float
    unrealized_pnl: float
    fees: float
    equity: float


def account_snapshot(
    starting_balance: float,
    positions: list[PaperPosition],
    marks: dict[str, float],
    costs: CostModel,
    contract: ContractSpecification,
) -> PaperAccountSnapshot:
    """Mark open positions using supplied mid prices; missing marks are rejected."""
    _positive(starting_balance, "starting_balance")
    realized = sum(p.realized_pnl_account for p in positions)
    fees = sum(p.fees_account for p in positions)
    unrealized = 0.0
    for p in positions:
        if p.status != "open":
            continue
        if p.position_id not in marks:
            raise ValueError(f"missing mark for position {p.position_id}")
        mark = costs.exit_fill(p.side, marks[p.position_id])
        direction = 1.0 if p.side == "BUY" else -1.0
        unrealized += (mark - p.entry_price) * direction * p.remaining_quantity * contract.contract_size * contract.quote_to_account_rate
    equity = starting_balance + realized + unrealized
    return PaperAccountSnapshot(
        starting_balance=round(starting_balance, 2),
        realized_pnl=round(realized, 2),
        unrealized_pnl=round(unrealized, 2),
        fees=round(fees, 2),
        equity=round(equity, 2),
    )


def _positive(value: float, name: str) -> None:
    if not isfinite(float(value)) or value <= 0:
        raise ValueError(f"{name} must be finite and positive")
