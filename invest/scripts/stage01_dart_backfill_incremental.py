import glob
import os
import subprocess
import sys
from datetime import datetime

import pandas as pd

DART_DIR = "invest/data/raw/kr/dart"
FETCH_SCRIPT = "invest/scripts/stage01_fetch_dart_disclosures.py"
START_YM = "201601"


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


def main() -> int:
    now = datetime.now()
    end_ym = now.strftime("%Y%m")

    have = collected_months()
    missing = [ym for ym in ym_iter(START_YM, end_ym) if ym not in have]

    if not missing:
        print("DART_BACKFILL_INCREMENTAL: HEALTHY (no missing month)")
        return 0

    target = missing[0]  # oldest missing first
    y, m = int(target[:4]), int(target[4:6])
    bgn = f"{y:04d}{m:02d}01"
    end = f"{y:04d}{m:02d}{month_end_day(y, m):02d}"

    env = os.environ.copy()
    env["DART_BGN_DE"] = bgn
    env["DART_END_DE"] = end

    print(f"DART_BACKFILL_INCREMENTAL: FETCH {bgn}~{end}")
    rc = subprocess.call([sys.executable, FETCH_SCRIPT], env=env)
    if rc != 0:
        print(f"DART_BACKFILL_INCREMENTAL: FAILED rc={rc}")
        return rc

    print(f"DART_BACKFILL_INCREMENTAL: OK fetched {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
