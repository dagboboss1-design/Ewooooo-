# Phase 2 — Signal Engine

The Phase 2 module provides deterministic closed-bar research signals.

```python
from forex_quant.signals import generate_signal, RiskPolicy
signal = generate_signal(hourly_candles, 'EUR_USD', equity=10000, quote_to_account_rate=1.0)
if signal is not None and RiskPolicy().evaluate().approved:
    print(signal.to_dict())
```

Supply a correct live quote-to-account conversion rate. The example does not place an order.
