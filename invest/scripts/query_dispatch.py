import argparse
import json
from datetime import datetime, timedelta

from query_helper import run_query


def main():
    p = argparse.ArgumentParser(description="Dispatch quick investment data queries")
    p.add_argument("--start", help="YYYY-MM-DD", default=None)
    p.add_argument("--end", help="YYYY-MM-DD", default=None)
    p.add_argument("--days", type=int, default=30, help="lookback days when start/end omitted")
    p.add_argument("--top", type=int, default=10)
    p.add_argument("--min-turnover", type=float, default=None)
    args = p.parse_args()

    if args.end is None:
        end = datetime.now().strftime("%Y-%m-%d")
    else:
        end = args.end

    if args.start is None:
        start = (datetime.now() - timedelta(days=args.days)).strftime("%Y-%m-%d")
    else:
        start = args.start

    out = run_query(start, end, top_n=args.top, min_turnover=args.min_turnover)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
