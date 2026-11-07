# Phase 4 Trade Journal

- Added SQLAlchemy-backed persistent paper journal using configured DATABASE_URL.
- AI responses have a Mark as taken button that stores the complete assistant setup text, selected chart instrument/timeframe, side and timestamp.
- Journal supports viewing open/closed records and recording actual exit price and P/L.
- Marking a trade as taken never places a broker order. This is paper journaling only.
- Configure a persistent database volume or managed PostgreSQL DATABASE_URL for hosted deployments; ephemeral SQLite storage can be lost.
- Structured entry, stop and target extraction is a follow-up; raw AI setup text is preserved to avoid guessing numeric levels.
