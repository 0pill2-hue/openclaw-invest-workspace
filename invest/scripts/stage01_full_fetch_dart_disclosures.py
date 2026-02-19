import os
import subprocess
import sys
import calendar
from datetime import datetime, timedelta

# DART list API rule: without corp_code, max 3 months per request.
# Run latest -> oldest (monthly chunks) to satisfy "latest-first" collection.
START = datetime(2016, 1, 1)
END = datetime.now()
STEP_MONTHS = 1


def month_start(dt: datetime) -> datetime:
    """
    Role: month_start 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    return datetime(dt.year, dt.month, 1)


def month_end(dt: datetime) -> datetime:
    """
    Role: month_end 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    last = calendar.monthrange(dt.year, dt.month)[1]
    return datetime(dt.year, dt.month, last)


def add_months(dt: datetime, months: int) -> datetime:
    """
    Role: add_months 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    y = dt.year + (dt.month - 1 + months) // 12
    m = (dt.month - 1 + months) % 12 + 1
    d = min(dt.day, calendar.monthrange(y, m)[1])
    return datetime(y, m, d)


# Build month windows first, then execute in reverse (latest first)
windows = []
cur = month_start(START)
while cur <= END:
    bgn = cur
    nxt = add_months(cur, STEP_MONTHS)
    end = month_end(add_months(nxt, -1))
    if end > END:
        end = END
    windows.append((bgn, end))
    cur = nxt

for bgn, end in reversed(windows):
    os.environ['DART_BGN_DE'] = bgn.strftime('%Y%m%d')
    os.environ['DART_END_DE'] = end.strftime('%Y%m%d')
    print(f"DART chunk(latest-first): {os.environ['DART_BGN_DE']} ~ {os.environ['DART_END_DE']}", flush=True)

    rc = subprocess.call([sys.executable, 'invest/scripts/fetch_dart_disclosures.py'])
    if rc != 0:
        sys.exit(rc)

print('DART full chunk collection done (latest-first)', flush=True)
