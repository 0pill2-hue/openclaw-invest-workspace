import calendar
import os
import subprocess
import sys
from datetime import datetime, timedelta

# DART list API rule: without corp_code, max 3 months per request.
# Run latest -> oldest (monthly chunks) to satisfy "latest-first" collection.


def month_start(dt: datetime) -> datetime:
    return datetime(dt.year, dt.month, 1)


def month_end(dt: datetime) -> datetime:
    last = calendar.monthrange(dt.year, dt.month)[1]
    return datetime(dt.year, dt.month, last)


def add_months(dt: datetime, months: int) -> datetime:
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return datetime(y, m, d)


def _parse_date(raw: str) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    for cand in (s, s.replace("/", "-")):
        try:
            return datetime.fromisoformat(cand)
        except Exception:
            pass
    try:
        return datetime.strptime(s, "%Y%m%d")
    except Exception:
        return None


def _resolve_range() -> tuple[datetime, datetime, int, int]:
    target_years = max(1, int(os.environ.get("DART_FULL_TARGET_YEARS", "10")))
    default_start = datetime.now() - timedelta(days=365 * target_years)
    default_end = datetime.now()

    start = _parse_date(os.environ.get("DART_FULL_START_DATE", "")) or default_start
    end = _parse_date(os.environ.get("DART_FULL_END_DATE", "")) or default_end
    if start > end:
        start, end = end, start

    step_months = max(1, int(os.environ.get("DART_FULL_STEP_MONTHS", "1")))
    max_chunks = max(0, int(os.environ.get("DART_FULL_MAX_CHUNKS", "0")))
    return month_start(start), end, step_months, max_chunks


def main() -> int:
    start, end, step_months, max_chunks = _resolve_range()

    windows = []
    cur = month_start(start)
    while cur <= end:
        bgn = cur
        nxt = add_months(cur, step_months)
        chunk_end = month_end(add_months(nxt, -1))
        if chunk_end > end:
            chunk_end = end
        windows.append((bgn, chunk_end))
        cur = nxt

    if max_chunks > 0:
        windows = windows[-max_chunks:]

    if not windows:
        print("DART full chunk collection skipped: no windows", flush=True)
        return 0

    print(
        f"DART full backfill range: {start.date().isoformat()} ~ {end.date().isoformat()} "
        f"step_months={step_months} chunks={len(windows)}",
        flush=True,
    )

    for bgn, chunk_end in reversed(windows):
        env = os.environ.copy()
        env["DART_BGN_DE"] = bgn.strftime("%Y%m%d")
        env["DART_END_DE"] = chunk_end.strftime("%Y%m%d")
        print(f"DART chunk(latest-first): {env['DART_BGN_DE']} ~ {env['DART_END_DE']}", flush=True)

        rc = subprocess.call([sys.executable, "invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py"], env=env)
        if rc != 0:
            return rc

    print("DART full chunk collection done (latest-first)", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
