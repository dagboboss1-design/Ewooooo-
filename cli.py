import argparse, asyncio
from datetime import date
from .config import Settings
from .ingest import ingest_candles, ingest_dukascopy, ingest_calendar, ingest_news

def main():
    parser = argparse.ArgumentParser("forex-quant-phase1")
    sub = parser.add_subparsers(dest="command", required=True)
    c = sub.add_parser("candles"); c.add_argument("--instrument", required=True); c.add_argument("--granularity", default="H1"); c.add_argument("--count", type=int, default=500)
    d = sub.add_parser("dukascopy"); d.add_argument("--instrument", required=True); d.add_argument("--date", required=True); d.add_argument("--hour", type=int, required=True)
    sub.add_parser("calendar"); sub.add_parser("news")
    args = parser.parse_args(); settings = Settings()
    if args.command == "candles":
        result = asyncio.run(ingest_candles(settings, args.instrument, args.granularity, args.count))
    elif args.command == "dukascopy":
        result = asyncio.run(ingest_dukascopy(settings, args.instrument, date.fromisoformat(args.date), args.hour))
    elif args.command == "calendar":
        result = asyncio.run(ingest_calendar(settings))
    else:
        result = asyncio.run(ingest_news(settings))
    print(result)

if __name__ == "__main__":
    main()
