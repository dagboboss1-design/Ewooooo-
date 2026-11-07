# Phase 1 Notes

## Implemented
- Async OANDA v20 candle client with explicit practice/live base URLs.
- Dukascopy hourly `.bi5` downloader and decoder for standard 20-byte tick records.
- biquote calendar and GDELT news adapters.
- UTC normalization, duplicate detection, gap reporting, and OHLC sanity checks.
- Immutable Parquet snapshot writer with SHA-256 manifest.
- SQLAlchemy metadata table for snapshot indexing.
- Unit tests for normalization, duplicate detection, gap detection, and snapshot reproducibility metadata.

## Decisions
- OANDA live selection is market-data-only. No order client is included.
- GDELT is selected as the initial open news source; it does not provide verified economic actual/forecast values.
- biquote is used as the calendar adapter because it was specified in the original News Spike Terminal design.
- Provider failures are explicit exceptions; missing data is never replaced with zero.

## Limitations requiring verification
- Confirm biquote endpoint availability and exact JSON schema with a live response.
- Dukascopy public archive availability can vary. The decoder assumes standard 20-byte records:
  milliseconds-from-hour, ask integer, bid integer, ask volume float, bid volume float.
- OANDA account entitlements, instrument availability, and rate limits depend on the account.
- This is Phase 1 only. Strategy, risk sizing, signal generation, and order routing are not implemented.
