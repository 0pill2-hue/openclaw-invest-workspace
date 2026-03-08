#!/usr/bin/env python3
"""
Telegram undated 파일 보정
- Date: YYYY-MM-DD 라인이 없는 .md 파일에 자동 보정 헤더 주입
- 파일별 날짜 인덱스(runtime JSON) 생성
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
STAGE1_DIR = ROOT / "invest/stages/stage1"
TG_DIR = STAGE1_DIR / "outputs/raw/qualitative/text/telegram"
RUNTIME_PATH = STAGE1_DIR / "outputs/runtime/telegram_date_index.json"

DATE_RE = re.compile(r"Date:\s*(\d{4}-\d{2}-\d{2})")
MONTH_DAY_RE = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})\b",
    re.IGNORECASE,
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
}


def infer_date_from_monthday(text: str, mtime_dt: datetime) -> str | None:
    m = MONTH_DAY_RE.search(text)
    if not m:
        return None

    month_name = m.group(1).lower()
    day = int(m.group(2))
    month = MONTHS.get(month_name)
    if not month:
        return None

    year = mtime_dt.year
    # 연초에 전년도 월(예: December)이 나오는 경우 보정
    if month > mtime_dt.month + 1:
        year -= 1

    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except Exception:
        return None


def main() -> int:
    TG_DIR.mkdir(parents=True, exist_ok=True)
    tg_dir = TG_DIR
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    undated_before = 0
    undated_after = 0
    fixed_count = 0

    for fp in sorted(tg_dir.glob("*.md")):
        text = fp.read_text(encoding="utf-8", errors="ignore") if fp.exists() else ""
        mtime_dt = datetime.fromtimestamp(fp.stat().st_mtime)

        explicit_dates = DATE_RE.findall(text)
        has_explicit = len(explicit_dates) > 0

        auto_marked = "AUTO_DATED_FIX" in text[:400]
        inferred_date = None
        source = "explicit"

        if has_explicit:
            inferred_date = explicit_dates[0]
            source = "explicit"
        else:
            undated_before += 1
            inferred_date = infer_date_from_monthday(text, mtime_dt)
            if inferred_date:
                source = "monthday_inferred"
            else:
                inferred_date = mtime_dt.strftime("%Y-%m-%d")
                source = "file_mtime_fallback" if text.strip() else "empty_file_fallback"

            if not auto_marked:
                header = (
                    f"<!-- AUTO_DATED_FIX source={source} generated_at={datetime.now().isoformat(timespec='seconds')} -->\n"
                    f"Date: {inferred_date} 00:00:00\n\n"
                )
                fp.write_text(header + text, encoding="utf-8")
                fixed_count += 1

        if not inferred_date:
            undated_after += 1

        rows.append(
            {
                "file": fp.name,
                "size": fp.stat().st_size,
                "mtime": mtime_dt.isoformat(timespec="seconds"),
                "has_explicit_date": has_explicit,
                "inferred_date": inferred_date,
                "source": source,
                "auto_marked": auto_marked,
            }
        )

    status = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "files_scanned": len(rows),
        "undated_before": undated_before,
        "undated_after": undated_after,
        "auto_fixed_count": fixed_count,
        "files": rows,
        "ok": undated_after == 0,
    }

    RUNTIME_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: status[k] for k in ["timestamp", "files_scanned", "undated_before", "undated_after", "auto_fixed_count", "ok"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
