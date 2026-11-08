# Phase 5 — News Spike Terminal

## Scope
Build a separate event-risk and volatility terminal. It supplements the signal engine; it does not create a pre-release directional trade call.

## Foundation added
- Normalized event surprise using historical surprise standard deviation.
- Surprise labels: below 0.5 = no edge; above 1.5 absolute normalized surprise = large surprise; intermediate = moderate.
- A positive/negative surprise hint is not interpreted as BUY/SELL; event-specific economic meaning must be supplied separately.
- Rolling 30-tick return z-score primitive for spike detection.
- Configurable spread guard primitive.
- Explicit currency-to-watchlist impact mapping.

## Next implementation steps
1. Validate the biquote calendar response and event-history schema against real provider responses.
2. Persist event actual/forecast/previous/revised-previous values and arrival timestamps.
3. Add event-specific polarity metadata and fit pre-release XGBoost probability / magnitude models only after sufficient historical data is collected.
4. Validate the tick stream protocol and reconnect/heartbeat behavior before enabling SignalR streaming.
5. Add pair/session spread baselines and mandatory spread veto.
6. Add event-window alert routing, deduplication, latency metrics, and end-to-end tests.

## Safety and data status
- No model probability is emitted until calibrated on historical out-of-sample data.
- No directional interpretation is emitted from surprise sign alone.
- No alert is called live until the upstream provider has been validated.
- Broker execution remains OFF; this phase is alert/research only.
