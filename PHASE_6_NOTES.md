# Phase 6 — Broker-neutral execution foundation

## Current scope: paper trading only

- Added a broker-neutral PaperTradingAdapter with deterministic simulated fills.
- Standardized paper order fields: symbol, side, timeframe, entry, stop, target and account balance.
- Validates BUY/SELL stop-loss and take-profit geometry and rejects non-finite values.
- Applies existing risk policy: 0.5% initial trade risk, 2% daily loss limit, 5% weekly loss limit, three-loss pause and kill switch.
- Every accepted result is marked source=paper and execution_mode=simulation_only.
- No broker network calls, credentials, live order endpoints, or real-money execution are present.

## Important sizing limitation

The adapter calculates generic units from account-currency risk divided by price distance. This is a simulation quantity only, not a broker-ready lot size. Pip value conversion, contract size, account-currency conversion, commissions, spread, margin, minimum/step size and partial fills must be supplied by a broker-specific adapter before any future live use.

## Next Phase 6 work

1. Persist paper orders and simulated positions across restarts.
2. Add simulated close/partial-close, realized P&L and fees.
3. Reconcile paper executions with the existing trade journal.
4. Add account/equity and open-position views.
5. Define a broker adapter contract and conformance tests.

Live trading remains disabled and is outside this implementation.
