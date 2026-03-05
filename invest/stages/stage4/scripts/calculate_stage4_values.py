import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np

try:
    from invest.stages.run_manifest import write_run_manifest
except ModuleNotFoundError:
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from run_manifest import write_run_manifest

try:
    from invest.stages.stage4.scripts.value_stage4 import calc_value_factors
except ModuleNotFoundError:
    # script direct 실행 시(project root 미포함) 동작 동일성 유지를 위한 최소 경로 보정
    sys.path.append(str(Path(__file__).resolve().parents[4]))
    from invest.stages.stage4.scripts.value_stage4 import calc_value_factors

STAGE4_ROOT = Path(__file__).resolve().parents[1]
INPUTS_ROOT = STAGE4_ROOT / "inputs"

SRC_BASE = INPUTS_ROOT / "upstream_stage2_clean"
DST_BASE = STAGE4_ROOT / "outputs" / "value"
REPORT_DIR = STAGE4_ROOT / "outputs" / "reports"
MASTER_LIST_PATH = INPUTS_ROOT / "upstream_stage1_master" / "kr_stock_list.csv"
STAGE3_FEATURES_PATH = INPUTS_ROOT / "upstream_stage3_outputs" / "features/stage3_qualitative_axes_features.csv"
INCLUDED_MARKETS = {"KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"}
INCLUDED_MARKET_IDS = {"STK", "KSQ"}


def _load_kr_universe_codes() -> list[str]:
    if not MASTER_LIST_PATH.exists():
        raise FileNotFoundError(f"master list not found: {MASTER_LIST_PATH}")

    df = pd.read_csv(MASTER_LIST_PATH)
    if "Code" not in df.columns:
        raise ValueError("master list missing required column: Code")

    x = df.copy()
    x["Code"] = x["Code"].astype(str).str.zfill(6)

    if "Market" in x.columns:
        x["Market"] = x["Market"].astype(str).str.upper().str.strip()
        x = x[x["Market"].isin(INCLUDED_MARKETS)]
    elif "MarketId" in x.columns:
        x["MarketId"] = x["MarketId"].astype(str).str.upper().str.strip()
        x = x[x["MarketId"].isin(INCLUDED_MARKET_IDS)]

    return sorted(x["Code"].dropna().unique().tolist())


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


def _normalize_symbol(symbol: str) -> str:
    s = str(symbol or "").strip().upper()
    if s.isdigit() and len(s) <= 6:
        return s.zfill(6)
    return s


def _load_stage3_features() -> dict[tuple[str, str], dict]:
    if not STAGE3_FEATURES_PATH.exists():
        return {}

    feat = pd.read_csv(STAGE3_FEATURES_PATH)
    required = {"date", "symbol", "qualitative_signal"}
    if not required.issubset(feat.columns):
        return {}

    x = feat.copy()
    x["date"] = pd.to_datetime(x["date"], errors="coerce").dt.date.astype(str)
    x["symbol"] = x["symbol"].apply(_normalize_symbol)
    x["qualitative_signal"] = pd.to_numeric(x["qualitative_signal"], errors="coerce").fillna(0.0).clip(-1.0, 1.0)

    out: dict[tuple[str, str], dict] = {}
    for _, r in x[["date", "symbol", "qualitative_signal"]].iterrows():
        key = (str(r["date"]), str(r["symbol"]))
        out[key] = {
            "qualitative_signal": float(r["qualitative_signal"]),
        }
    return out


def _apply_stage3_integration(out: pd.DataFrame, symbol: str, features: dict[tuple[str, str], dict]) -> tuple[pd.DataFrame, int]:
    x = out.copy()
    norm_symbol = _normalize_symbol(symbol)

    dates = pd.to_datetime(x["Date"], errors="coerce").dt.date.astype(str)
    rows = [features.get((d, norm_symbol)) for d in dates]

    qsig = [float(r["qualitative_signal"]) if r is not None else 0.0 for r in rows]
    miss = [1 if r is None else 0 for r in rows]

    x["QUALITATIVE_SIGNAL"] = qsig
    x["STAGE3_MISSING"] = miss

    matched_rows = int((x["STAGE3_MISSING"] == 0).sum())
    return x, matched_rows


def run_value_pipeline():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stage3_features = _load_stage3_features()
    summary = {
        "grade": "DRAFT",
        "watermark": "TEST ONLY",
        "adoption_gate": "stage09_required",
        "universe_policy": {
            "kr_include_markets": sorted(INCLUDED_MARKETS),
            "kr_exclude_markets": "others (e.g., KONEX)",
        },
        "stage3_integration": {
            "features_path": str(STAGE3_FEATURES_PATH),
            "features_loaded": int(len(stage3_features)),
            "matched_rows": 0,
            "missing_rows": 0,
        },
        "processed": 0,
        "skipped": 0,
        "errors": 0,
        "markets": {},
        "continuity": {"warn_symbols": 0, "checked_symbols": 0, "examples": []},
        "error_examples": [],
    }

    for market in ["kr", "us"]:
        src = SRC_BASE / market / "ohlcv"
        dst = DST_BASE / market / "ohlcv"
        dst.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            summary["markets"][market] = {
                "processed": 0,
                "skipped": 0,
                "errors": 0,
                "continuity_warn": 0,
                "note": f"src_not_found:{src}",
            }
            continue

        p = s = e = cw = 0
        skip_missing_input = 0
        skip_too_short = 0

        if market == "kr":
            codes = _load_kr_universe_codes()
            candidates = [(code, src / f"{code}.csv") for code in codes]
            universe_total = len(codes)
        else:
            files = sorted(src.glob("*.csv"))
            candidates = [(f.stem, f) for f in files]
            universe_total = len(candidates)

        for symbol, f in candidates:
            if not f.exists():
                s += 1
                skip_missing_input += 1
                continue

            try:
                df = pd.read_csv(f)
                cont = _check_date_continuity(df)
                summary["continuity"]["checked_symbols"] += 1
                if cont["continuity_flag"] == "WARN":
                    cw += 1
                    summary["continuity"]["warn_symbols"] += 1
                    if len(summary["continuity"]["examples"]) < 20:
                        summary["continuity"]["examples"].append({"market": market, "symbol": symbol, **cont})

                if len(df) < 30:
                    s += 1
                    skip_too_short += 1
                    continue

                out = calc_value_factors(df)
                out, matched_rows = _apply_stage3_integration(out, symbol, stage3_features)
                summary["stage3_integration"]["matched_rows"] += matched_rows
                summary["stage3_integration"]["missing_rows"] += int(len(out) - matched_rows)

                cols = [
                    c
                    for c in [
                        "Date",
                        "Open",
                        "High",
                        "Low",
                        "Close",
                        "Volume",
                        "VAL_MOM_20",
                        "VAL_FLOW_10",
                        "VAL_LIQ_WIN",
                        "VAL_RISK_10",
                        "VALUE_SCORE_RAW",
                        "VALUE_SCORE",
                        "QUALITATIVE_SIGNAL",
                        "STAGE3_MISSING",
                    ]
                    if c in out.columns
                ]
                out[cols].to_csv(dst / f"{symbol}.csv", index=False)
                p += 1
            except Exception as ex:
                e += 1
                if len(summary["error_examples"]) < 30:
                    summary["error_examples"].append(
                        {
                            "market": market,
                            "symbol": symbol,
                            "error_type": type(ex).__name__,
                            "error": str(ex),
                        }
                    )

        summary["markets"][market] = {
            "universe_total": universe_total,
            "processed": p,
            "skipped": s,
            "errors": e,
            "continuity_warn": cw,
            "skip_missing_input": skip_missing_input,
            "skip_too_short": skip_too_short,
        }
        summary["processed"] += p
        summary["skipped"] += s
        summary["errors"] += e

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report = REPORT_DIR / f"STAGE4_VALUE_RUN_{ts}.json"

    manifest_path = STAGE4_ROOT / "outputs" / f"manifest_stage4_value_{ts}.json"
    write_run_manifest(
        run_type='stage4_calculate_values',
        params={
            'src_base': str(SRC_BASE),
            'dst_base': str(DST_BASE),
            'master_list': str(MASTER_LIST_PATH),
            'stage3_features': str(STAGE3_FEATURES_PATH),
        },
        inputs=[str(SRC_BASE), str(MASTER_LIST_PATH), str(STAGE3_FEATURES_PATH)],
        outputs=[str(report), str(DST_BASE)],
        out_path=str(manifest_path),
        workdir='.',
    )

    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"STAGE4_DONE report={report}")
    print(f"STAGE4_MANIFEST={manifest_path}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    run_value_pipeline()
