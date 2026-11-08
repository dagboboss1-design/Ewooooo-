"""Broker-neutral paper-trading adapter. Never sends orders to a broker."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from math import isfinite
from typing import Literal
from uuid import uuid4
from forex_quant.signals.risk import RiskPolicy

@dataclass(frozen=True)
class PaperOrder:
    symbol: str
    side: Literal["BUY", "SELL"]
    timeframe: str
    entry: float
    stop_loss: float
    take_profit: float
    account_balance: float
    daily_loss_fraction: float = 0.0
    weekly_loss_fraction: float = 0.0
    consecutive_losses: int = 0
    kill_switch: bool = False

@dataclass(frozen=True)
class PaperOrderResult:
    accepted: bool
    order_id: str | None
    status: str
    reason: str
    symbol: str
    side: str
    units: float
    risk_amount: float
    entry: float | None
    stop_loss: float | None
    take_profit: float | None
    source: str = "paper"
    execution_mode: str = "simulation_only"
    def to_dict(self) -> dict:
        return asdict(self)

class PaperTradingAdapter:
    """Deterministic simulated-fill adapter; no network or broker integration."""
    def __init__(self, risk_policy: RiskPolicy | None = None):
        self.risk_policy = risk_policy or RiskPolicy()

    def submit(self, order: PaperOrder) -> PaperOrderResult:
        side = str(order.side).upper()
        symbol = str(order.symbol).strip().upper()
        if side not in {"BUY", "SELL"}:
            return self._reject(order, "invalid_side")
        try:
            values = (order.entry, order.stop_loss, order.take_profit, order.account_balance)
            if not all(isfinite(float(v)) for v in values):
                return self._reject(order, "non_finite_order_value")
            if not symbol or order.account_balance <= 0 or order.entry <= 0:
                return self._reject(order, "invalid_symbol_price_or_balance")
            if side == "BUY" and not (order.stop_loss < order.entry < order.take_profit):
                return self._reject(order, "buy_requires_stop_below_entry_and_target_above")
            if side == "SELL" and not (order.take_profit < order.entry < order.stop_loss):
                return self._reject(order, "sell_requires_target_below_entry_and_stop_above")
        except (TypeError, ValueError):
            return self._reject(order, "invalid_order_value")
        decision = self.risk_policy.evaluate(
            daily_loss_fraction=order.daily_loss_fraction,
            weekly_loss_fraction=order.weekly_loss_fraction,
            consecutive_losses=order.consecutive_losses,
            kill_switch=order.kill_switch,
        )
        if not decision.approved:
            return self._reject(order, decision.reason)
        risk_amount = order.account_balance * decision.effective_risk_fraction
        price_risk = abs(order.entry - order.stop_loss)
        # Generic quantity only; not broker-ready lots or units.
        units = risk_amount / price_risk
        return PaperOrderResult(
            accepted=True, order_id=str(uuid4()), status="filled",
            reason="simulated_fill_only", symbol=symbol, side=side,
            units=round(units, 8), risk_amount=round(risk_amount, 2),
            entry=float(order.entry), stop_loss=float(order.stop_loss),
            take_profit=float(order.take_profit),
        )

    @staticmethod
    def _reject(order: PaperOrder, reason: str) -> PaperOrderResult:
        return PaperOrderResult(
            accepted=False, order_id=None, status="rejected", reason=reason,
            symbol=str(order.symbol).strip().upper(), side=str(order.side).upper(),
            units=0.0, risk_amount=0.0, entry=None, stop_loss=None, take_profit=None,
        )
