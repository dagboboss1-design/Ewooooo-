# Phase 6 — Broker-neutral paper execution

## Implemented on the development branch

- Broker-neutral paper adapter and deterministic simulated order fills.
- Existing risk gates remain in force: 0.5% initial trade risk, 2% daily loss limit, 5% weekly loss limit, three-consecutive-loss pause and kill switch.
- Persistent paper-account configuration stored in the application's database.
- Dashboard settings for starting balance, account currency, spread, slippage, commission and explicit per-symbol contract specifications.
- Paper position listing and partial/full simulated close controls.
- Simulated entry fills apply configured spread/slippage; entry and exit commissions are accounted for on both sides when the symbol conversion is configured.
- Partial-close history, remaining quantity, cumulative realized account-currency P&L and fees are persisted with the paper journal record.
- Account snapshot endpoint calculates realized P&L, unrealized P&L and equity from supplied mark prices and explicit contract specifications.
- Internal reconciliation endpoint checks paper journal quantity/status consistency and reports discrepancies.
- Account-currency P&L is never estimated when contract size or quote-to-account conversion is missing.
- Dashboard and API responses explicitly identify simulation mode and keep `execution_enabled: false`.

## Setup required before accounting

Open Settings → Paper account. Enter the starting paper balance and account currency, then supply contract specifications for each symbol you will paper trade. Contract specifications require both:

- `contract_size`: the number of underlying units represented by one generic simulation quantity.
- `quote_to_account_rate`: account-currency units per one quote-currency unit.

Spread, slippage and commission are user-configurable and default to zero only as an explicit input shown in the form; they are not live broker cost estimates. Do not copy a broker's lot size into contract_size without checking its instrument contract definition.

The paper-account snapshot endpoint requires mark prices keyed by paper trade ID. Prices must be supplied from a verified market-data source; the server does not invent them.

## Important limits

- Paper quantities are generic simulation units, not broker-ready lots.
- No broker adapter is connected and no credentials are stored.
- No real orders, account reads, deposits, withdrawals or broker-side position management occur.
- The legacy journal manual-close route is journal-only; use the paper position close controls for simulated execution-cost and account-currency accounting.
- The account settings do not automatically turn on live trading.

## Safety state

Live broker execution is disabled. This phase is paper-only. Keep `execution_enabled: false` until a separate, explicitly authorized live-trading phase has been designed, reviewed, tested and configured.
