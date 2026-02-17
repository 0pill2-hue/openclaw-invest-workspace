import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

try:
    from invest.scripts.run_manifest import write_run_manifest
except ModuleNotFoundError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parent.parent / 'invest' / 'scripts'))
    from run_manifest import write_run_manifest

try:
    from invest.features.value_stage3 import calc_value_factors
except ModuleNotFoundError:
    # script direct 실행 시(project root 미포함) 동작 동일성 유지를 위한 최소 경로 보정
    sys.path.append(str(Path(__file__).resolve().parent.parent))
    from invest.features.value_stage3 import calc_value_factors

SRC_BASE = Path("invest/data/clean/production")
DST_BASE = Path("invest/data/value/stage3")
REPORT_DIR = Path("reports/stage_updates")


def _check_date_continuity(df: pd.DataFrame) -> dict:
    x = df.copy()
    if "Date" not in x.columns:
        return {
            "rows": int(len(x)),
            "missing_date_rows": int(len(x)),
            "missing_points": 0,
            "max_gap_days": None,
            "continuity_flag": "WARN",
            "warn_reason": "missing_date_column",
        }

    dt = pd.to_datetime(x["Date"], errors="coerce").dropna().sort_values().drop_duplicates()
    if dt.empty:
        return {
            "rows": int(len(x)),
            "missing_date_rows": int(len(x)),
            "missing_points": 0,
            "max_gap_days": None,
            "continuity_flag": "WARN",
            "warn_reason": "all_date_invalid",
        }

    dt_dates = dt.dt.date.to_numpy()
    if len(dt_dates) >= 2:
        bday_gaps = [max(0, np.busday_count(dt_dates[i], dt_dates[i + 1]) - 1) for i in range(len(dt_dates) - 1)]
        missing_points = int(sum(bday_gaps))
        max_gap = int(max(bday_gaps) if bday_gaps else 0)
    else:
        missing_points = 0
        max_gap = 0

    # 과도 결측: 관측일의 10% 초과 누락 포인트 또는 단일 5영업일 초과 공백
    ratio = float(missing_points / max(len(dt), 1))
    warn = ratio > 0.10 or max_gap > 5
    return {
        "rows": int(len(x)),
        "missing_date_rows": int(len(x) - len(dt)),
        "missing_points": missing_points,
        "max_gap_days": max_gap,
        "missing_ratio": ratio,
        "continuity_flag": "WARN" if warn else "OK",
        "warn_reason": "excessive_missing_segment" if warn else "",
    }


def run_value_pipeline():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "grade": "DRAFT",
        "watermark": "TEST ONLY",
        "adoption_gate": "stage08_required",
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "markets": {},
        "continuity": {"warn_symbols": 0, "checked_symbols": 0, "examples": []},
    }

    for market in ["kr", "us"]:
        src = SRC_BASE / market / "ohlcv"
        dst = DST_BASE / market / "ohlcv"
        dst.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            summary["markets"][market] = {"processed": 0, "skipped": 0, "errors": 0, "continuity_warn": 0}
            continue

        p = s = e = cw = 0
        for f in src.glob("*.csv"):
            try:
                df = pd.read_csv(f)
                cont = _check_date_continuity(df)
                summary["continuity"]["checked_symbols"] += 1
                if cont["continuity_flag"] == "WARN":
                    cw += 1
                    summary["continuity"]["warn_symbols"] += 1
                    if len(summary["continuity"]["examples"]) < 20:
                        summary["continuity"]["examples"].append({"market": market, "symbol": f.stem, **cont})

                if len(df) < 30:
                    s += 1
                    continue
                out = calc_value_factors(df)
                cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "VAL_MOM_20", "VAL_FLOW_10", "VAL_LIQ_WIN", "VAL_RISK_10", "VALUE_SCORE_RAW", "VALUE_SCORE"] if c in out.columns]
                out[cols].to_csv(dst / f.name, index=False)
                p += 1
            except Exception:
                e += 1

        summary["markets"][market] = {"processed": p, "skipped": s, "errors": e, "continuity_warn": cw}
        summary["processed"] += p
        summary["skipped"] += s
        summary["errors"] += e

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report = REPORT_DIR / f"STAGE3_VALUE_RUN_{ts}.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest_path = Path("invest/reports/data_quality") / f"manifest_stage3_value_{ts}.json"
    write_run_manifest(
        run_type='stage3_calculate_values',
        params={'src_base': str(SRC_BASE), 'dst_base': str(DST_BASE)},
        inputs=[str(SRC_BASE)],
        outputs=[str(report), str(DST_BASE)],
        out_path=str(manifest_path),
        workdir='invest',
    )

    print(f"STAGE3_DONE report={report}")
    print(f"STAGE3_MANIFEST={manifest_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    run_value_pipeline()
