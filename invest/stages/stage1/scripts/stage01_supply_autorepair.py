#!/usr/bin/env python3
"""
KR supply 자동복구 루틴
- master 종목 리스트 대비 raw supply 파일 누락 종목 탐지
- 누락(또는 빈 파일) 종목만 pykrx로 재수집 시도
- 결과를 runtime status JSON으로 저장
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
from pykrx import stock

from stage01_fetch_supply import _sanitize_supply

ROOT = Path("/Users/jobiseu/.openclaw/workspace")
STOCK_LIST_PATH = ROOT / "invest/stages/stage1/outputs/master/kr_stock_list.csv"
SUPPLY_DIR = ROOT / "invest/stages/stage1/outputs/raw/signal/kr/supply"
RUNTIME_DIR = ROOT / "invest/stages/stage1/outputs/runtime"
STATUS_PATH = RUNTIME_DIR / "supply_autorepair_status.json"


def _now_kst_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _load_expected_codes() -> list[str]:
    if not STOCK_LIST_PATH.exists():
        return []
    df = pd.read_csv(STOCK_LIST_PATH)
    if "Code" not in df.columns:
        return []

    # pykrx 수급 수집 대상은 6자리 숫자 종목만 제한
    codes = df["Code"].astype(str).str.zfill(6)
    codes = codes[codes.str.match(r"^\d{6}$", na=False)]
    return sorted(codes.unique().tolist())


def _existing_supply_files() -> dict[str, Path]:
    out: dict[str, Path] = {}
    SUPPLY_DIR.mkdir(parents=True, exist_ok=True)
    for fp in SUPPLY_DIR.glob("*_supply.csv"):
        code = fp.name.split("_", 1)[0]
        if len(code) == 6 and code.isdigit():
            out[code] = fp
    return out


def _is_empty_or_broken(fp: Path) -> bool:
    if not fp.exists() or fp.stat().st_size < 20:
        return True
    try:
        df = pd.read_csv(fp, nrows=3)
        return df.empty
    except Exception:
        return True


def _fetch_single_supply(code: str, lookback_years: int, dry_run: bool) -> tuple[bool, str]:
    end_date = datetime.now().strftime("%Y%m%d")
    start_date = (datetime.now() - timedelta(days=365 * max(1, lookback_years))).strftime("%Y%m%d")

    if dry_run:
        return True, f"dry-run fetch {code} {start_date}~{end_date}"

    try:
        raw = stock.get_market_trading_value_by_date(start_date, end_date, code, on="순매수")
        if raw is None or raw.empty:
            return False, "empty_response"

        clean_df, _ = _sanitize_supply(code, raw)
        if clean_df is None or clean_df.empty:
            return False, "sanitize_empty"

        out_path = SUPPLY_DIR / f"{code}_supply.csv"

        # 새로 수집한 full window 기준으로 완전 교체(중복 누적 방지)
        clean_df = clean_df.reset_index().drop_duplicates(subset=["Date"]).sort_values("Date")
        clean_df = clean_df.set_index("Date")
        clean_df.to_csv(out_path)
        return True, f"saved_rows={len(clean_df)}"
    except Exception as e:
        return False, str(e)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--lookback-years", type=int, default=10)
    parser.add_argument("--max-repair", type=int, default=3)
    args = parser.parse_args()

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)

    expected = _load_expected_codes()
    existing = _existing_supply_files()

    missing = [c for c in expected if c not in existing]
    broken = [c for c, fp in existing.items() if _is_empty_or_broken(fp)]

    targets = (missing + broken)[: max(0, args.max_repair)]
    repaired: list[dict] = []

    for code in targets:
        ok, detail = _fetch_single_supply(code, args.lookback_years, args.dry_run)
        repaired.append({"code": code, "ok": ok, "detail": detail})

    # 재평가
    existing_after = _existing_supply_files()
    remaining_missing = [c for c in expected if c not in existing_after]
    remaining_broken = [c for c, fp in existing_after.items() if _is_empty_or_broken(fp)]

    payload = {
        "timestamp": _now_kst_iso(),
        "dry_run": bool(args.dry_run),
        "expected_count": len(expected),
        "existing_count_before": len(existing),
        "missing_before": missing,
        "broken_before": broken,
        "repair_attempted": repaired,
        "existing_count_after": len(existing_after),
        "missing_after": remaining_missing,
        "broken_after": remaining_broken,
        "ok": len(remaining_missing) == 0 and len(remaining_broken) == 0,
    }
    STATUS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(payload, ensure_ascii=False))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
