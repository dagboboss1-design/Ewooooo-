# Phase 2 Notes — Signal Engine

## Delivered
- Causal RSI, ATR, Bollinger Bands and MACD histogram indicators.
- Deterministic closed-bar Bollinger + RSI + MACD mean-reversion candidate.
- Volatility/trend regime filter; baseline emits only in ranging regime.
- Complete signal schema: side, entry, stop, target, units, risk, confluence score, regime and invalidation.
- Separate risk policy: 0.5% initial trade risk, 2% daily loss limit, 5% weekly loss limit, three-loss pause and kill switch.
- Unit tests and CI integration.

## Limitations
- Confidence is a rule-confluence score, not calibrated probability.
- Sizing requires a valid quote-to-account conversion rate; default 1.0 is only correct when quote and account currencies match.
- Spread, commission, slippage, swap, margin, broker minimum size and lot-step checks are not yet included.
- No order routing is included. No live orders can be placed.
- Strategy requires pair-specific walk-forward and out-of-sample validation; no profitability is claimed.
