import argparse
import glob
import os
import subprocess
import sys
from datetime import datetime

import pandas as pd

DART_DIR = "invest/stages/stage1/outputs/raw/qualitative/kr/dart"
FETCH_SCRIPT = "invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py"
DEFAULT_START_YM = os.environ.get(
    "DART_BACKFILL_START_YM",
    (datetime.now().replace(day=1) - pd.DateOffset(years=10)).strftime("%Y%m"),
)
DEFAULT_BATCH_MONTHS = int(os.environ.get("DART_BACKFILL_BATCH_MONTHS", "1"))


def month_end_day(year: int, month: int) -> int:
    if month in (1, 3, 5, 7, 8, 10, 12):
        return 31
    if month in (4, 6, 9, 11):
        return 30
    leap = (year % 4 == 0 and year % 100 != 0) or (year % 400 == 0)
    return 29 if leap else 28


def ym_iter(start_ym: str, end_ym: str):
    sy, sm = int(start_ym[:4]), int(start_ym[4:6])
    ey, em = int(end_ym[:4]), int(end_ym[4:6])
    y, m = sy, sm
    while (y < ey) or (y == ey and m <= em):
        yield f"{y:04d}{m:02d}"
        m += 1
        if m > 12:
            m = 1
            y += 1


def collected_months() -> set[str]:
    files = glob.glob(os.path.join(DART_DIR, "dart_list_*.csv"))
    months: set[str] = set()
    for fp in files:
        try:
            df = pd.read_csv(fp, usecols=["rcept_dt"])
            vals = df["rcept_dt"].astype(str).str[:6]
            months.update(v for v in vals if len(v) == 6 and v.isdigit())
        except Exception:
            continue
    return months


def fetch_month(target_ym: str) -> int:
    y, m = int(target_ym[:4]), int(target_ym[4:6])
    bgn = f"{y:04d}{m:02d}01"
    end = f"{y:04d}{m:02d}{month_end_day(y, m):02d}"

    env = os.environ.copy()
    env["DART_BGN_DE"] = bgn
    env["DART_END_DE"] = end

    print(f"DART_BACKFILL_INCREMENTAL: FETCH {bgn}~{end}")
    rc = subprocess.call([sys.executable, FETCH_SCRIPT], env=env)
    if rc != 0:
        print(f"DART_BACKFILL_INCREMENTAL: FAILED {target_ym} rc={rc}")
        return rc
    print(f"DART_BACKFILL_INCREMENTAL: OK fetched {target_ym}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-ym", default=DEFAULT_START_YM)
    parser.add_argument("--batch-months", type=int, default=DEFAULT_BATCH_MONTHS)
    args = parser.parse_args()

    start_ym = str(args.start_ym)
    batch_months = max(1, int(args.batch_months))

    now = datetime.now()
    end_ym = now.strftime("%Y%m")

    have = collected_months()
    missing = [ym for ym in ym_iter(start_ym, end_ym) if ym not in have]

    if not missing:
        print("DART_BACKFILL_INCREMENTAL: HEALTHY (no missing month)")
        return 0

    targets = missing[:batch_months]
    print(
        f"DART_BACKFILL_INCREMENTAL: missing={len(missing)} batch={len(targets)} "
        f"range={targets[0]}~{targets[-1]}"
    )

    for ym in targets:
        rc = fetch_month(ym)
        if rc != 0:
            return rc

    remaining = [ym for ym in ym_iter(start_ym, end_ym) if ym not in collected_months()]
    print(f"DART_BACKFILL_INCREMENTAL: DONE fetched={len(targets)} remaining_missing={len(remaining)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
