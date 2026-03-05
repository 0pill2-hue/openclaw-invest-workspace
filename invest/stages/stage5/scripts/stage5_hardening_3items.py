import json
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd

try:
    from invest.stages.run_manifest import write_run_manifest
except ModuleNotFoundError:
    import sys
    sys.path.append(str(Path(__file__).resolve().parents[2]))
    from run_manifest import write_run_manifest

STAGE5_ROOT = Path(__file__).resolve().parents[1]
INPUTS_ROOT = STAGE5_ROOT / "inputs"

SRC_BASE = INPUTS_ROOT / "upstream_stage2_clean"
VAL_BASE = INPUTS_ROOT / "upstream_stage4_value"
MASTER_KR = INPUTS_ROOT / "upstream_stage1_master" / "kr_stock_list.csv"
OUT_MD = STAGE5_ROOT / "outputs" / "reports" / "STAGE5_HARDENING_3ITEMS_20260218.md"
OUT_JSON = STAGE5_ROOT / "outputs" / "reports" / "STAGE5_HARDENING_3ITEMS_20260218.json"


def check_continuity_for_symbol(csv_path: Path) -> dict:
    try:
        df = pd.read_csv(csv_path, usecols=["Date"])
    except Exception:
        df = pd.read_csv(csv_path)
    if "Date" not in df.columns:
        return {"symbol": csv_path.stem, "flag": "WARN", "missing_points": None, "max_gap_days": None, "reason": "missing_date_column"}

    dt = pd.to_datetime(df["Date"], errors="coerce").dropna().sort_values().drop_duplicates()
    if dt.empty:
        return {"symbol": csv_path.stem, "flag": "WARN", "missing_points": None, "max_gap_days": None, "reason": "all_date_invalid"}

    dt_dates = dt.dt.date.to_numpy()
    if len(dt_dates) >= 2:
        bday_gaps = [max(0, np.busday_count(dt_dates[i], dt_dates[i + 1]) - 1) for i in range(len(dt_dates) - 1)]
        missing_points = int(sum(bday_gaps))
        max_gap = int(max(bday_gaps) if bday_gaps else 0)
    else:
        missing_points = 0
        max_gap = 0
    miss_ratio = float(missing_points / max(len(dt), 1))
    flag = "WARN" if (miss_ratio > 0.10 or max_gap > 5) else "OK"
    return {
        "symbol": csv_path.stem,
        "flag": flag,
        "rows": int(len(dt)),
        "missing_points": missing_points,
        "missing_ratio": miss_ratio,
        "max_gap_days": max_gap,
        "reason": "excessive_missing_segment" if flag == "WARN" else "",
    }


def load_kr_metadata():
    if not MASTER_KR.exists():
        return {}
    m = pd.read_csv(MASTER_KR)
    m["Code"] = m["Code"].astype(str).str.zfill(6)
    m["Marcap"] = pd.to_numeric(m.get("Marcap"), errors="coerce")

    valid = m.dropna(subset=["Marcap"]).copy()
    if not valid.empty:
        q1, q2 = valid["Marcap"].quantile([0.33, 0.66]).values
    else:
        q1 = q2 = np.nan

    meta = {}
    for _, r in m.iterrows():
        marcap = r.get("Marcap")
        if pd.isna(marcap) or pd.isna(q1) or pd.isna(q2):
            bucket = "UNKNOWN"
        elif marcap <= q1:
            bucket = "SMALL"
        elif marcap <= q2:
            bucket = "MID"
        else:
            bucket = "LARGE"
        meta[r["Code"]] = {
            "sector": str(r.get("Dept", "UNKNOWN")) if pd.notna(r.get("Dept", np.nan)) else "UNKNOWN",
            "mcap_bucket": bucket,
        }
    return meta


def collect_value_rows(market: str, kr_meta: dict):
    rows = []
    root = VAL_BASE / market / "ohlcv"
    if not root.exists():
        return pd.DataFrame()

    for f in root.glob("*.csv"):
        try:
            df = pd.read_csv(f, usecols=["Date", "VALUE_SCORE"])
        except Exception:
            continue
        if df.empty:
            continue
        df["symbol"] = f.stem
        df["market"] = market.upper()
        if market == "kr":
            meta = kr_meta.get(f.stem, {"sector": "UNKNOWN", "mcap_bucket": "UNKNOWN"})
            df["sector"] = meta["sector"]
            df["mcap_bucket"] = meta["mcap_bucket"]
        else:
            df["sector"] = "UNKNOWN"
            df["mcap_bucket"] = "UNKNOWN"
        rows.append(df)

    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def nan_bias_report(all_rows: pd.DataFrame):
    if all_rows.empty:
        return {"overall_nan_ratio": None, "by_market": [], "by_sector": [], "by_mcap_bucket": [], "top_biased_buckets": []}

    x = all_rows.copy()
    x["is_nan"] = x["VALUE_SCORE"].isna().astype(int)

    def agg(by_cols):
        g = x.groupby(by_cols, dropna=False)["is_nan"].agg(["sum", "count"]).reset_index()
        g["nan_ratio"] = g["sum"] / g["count"].replace(0, np.nan)
        return g.sort_values("nan_ratio", ascending=False)

    by_market = agg(["market"])
    by_sector = agg(["market", "sector"])
    by_mcap = agg(["market", "mcap_bucket"])

    overall = float(x["is_nan"].mean()) if len(x) else None
    candidates = pd.concat([
        by_sector.assign(bucket_type="sector", bucket_name=lambda d: d["market"] + "/" + d["sector"].astype(str)),
        by_mcap.assign(bucket_type="mcap", bucket_name=lambda d: d["market"] + "/" + d["mcap_bucket"].astype(str)),
    ], ignore_index=True)
    candidates["lift_vs_overall"] = candidates["nan_ratio"] / (overall if overall and overall > 0 else np.nan)
    top = candidates.sort_values(["lift_vs_overall", "nan_ratio"], ascending=False).head(10)

    return {
        "overall_nan_ratio": overall,
        "by_market": by_market.to_dict("records"),
        "by_sector": by_sector.head(50).to_dict("records"),
        "by_mcap_bucket": by_mcap.to_dict("records"),
        "top_biased_buckets": top.to_dict("records"),
    }


def latest_score_distribution(market: str):
    root = VAL_BASE / market / "ohlcv"
    vals = []
    if not root.exists():
        return []
    for f in root.glob("*.csv"):
        try:
            df = pd.read_csv(f, usecols=["VALUE_SCORE"])
        except Exception:
            continue
        s = pd.to_numeric(df["VALUE_SCORE"], errors="coerce").dropna()
        if not s.empty:
            vals.append(float(s.iloc[-1]))
    return vals


def dist_metrics(vals):
    if len(vals) == 0:
        return {"n": 0, "mean": None, "std": None, "q05": None, "q25": None, "q50": None, "q75": None, "q95": None}
    s = pd.Series(vals)
    return {
        "n": int(len(s)),
        "mean": float(s.mean()),
        "std": float(s.std(ddof=1)) if len(s) > 1 else 0.0,
        "q05": float(s.quantile(0.05)),
        "q25": float(s.quantile(0.25)),
        "q50": float(s.quantile(0.50)),
        "q75": float(s.quantile(0.75)),
        "q95": float(s.quantile(0.95)),
    }


def kr_us_consistency_rule(kr: dict, us: dict):
    warns = []
    if kr["n"] == 0 or us["n"] == 0:
        warns.append("insufficient_sample")
        return {"warn": True, "reasons": warns}

    mean_diff = abs(kr["mean"] - us["mean"])
    median_diff = abs(kr["q50"] - us["q50"])
    std_ratio = (kr["std"] / us["std"]) if us["std"] not in (None, 0) else np.nan

    if mean_diff > 0.35:
        warns.append(f"mean_diff_gt_0.35({mean_diff:.3f})")
    if median_diff > 0.35:
        warns.append(f"median_diff_gt_0.35({median_diff:.3f})")
    if pd.notna(std_ratio) and (std_ratio < 0.70 or std_ratio > 1.30):
        warns.append(f"std_ratio_out_of_band({std_ratio:.3f})")

    return {
        "warn": len(warns) > 0,
        "reasons": warns,
        "mean_diff": mean_diff,
        "median_diff": median_diff,
        "std_ratio_kr_over_us": None if pd.isna(std_ratio) else float(std_ratio),
        "rule": {
            "mean_diff_max": 0.35,
            "median_diff_max": 0.35,
            "std_ratio_band": [0.70, 1.30],
        },
    }


def _json_safe(obj):
    if isinstance(obj, dict):
        return {k: _json_safe(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_json_safe(v) for v in obj]
    if isinstance(obj, float) and (np.isnan(obj) or np.isinf(obj)):
        return None
    return obj


def main():
    continuity = {}
    for market in ["kr", "us"]:
        src = SRC_BASE / market / "ohlcv"
        items = []
        if src.exists():
            for f in src.glob("*.csv"):
                items.append(check_continuity_for_symbol(f))
        continuity[market.upper()] = {
            "checked": len(items),
            "warn_count": sum(1 for x in items if x["flag"] == "WARN"),
            "warn_symbols_top20": [x for x in sorted(items, key=lambda d: (d.get("missing_points") or -1), reverse=True) if x["flag"] == "WARN"][:20],
        }

    kr_meta = load_kr_metadata()
    all_rows = pd.concat([
        collect_value_rows("kr", kr_meta),
        collect_value_rows("us", kr_meta),
    ], ignore_index=True)

    nan_bias = nan_bias_report(all_rows)

    kr_vals = latest_score_distribution("kr")
    us_vals = latest_score_distribution("us")
    kr_m = dist_metrics(kr_vals)
    us_m = dist_metrics(us_vals)
    consistency = kr_us_consistency_rule(kr_m, us_m)

    out = {
        "generated_at": datetime.now().isoformat(),
        "continuity_check": continuity,
        "nan_bias_check": nan_bias,
        "kr_us_distribution": {"KR": kr_m, "US": us_m, "consistency_warning": consistency},
        "stage5_summary_5lines": [
            f"1) 롤링 연속성: KR {continuity['KR']['warn_count']}/{continuity['KR']['checked']} WARN, US {continuity['US']['warn_count']}/{continuity['US']['checked']} WARN (제외 없이 경고 플래그).",
            f"2) VALUE_SCORE NaN 전체 비율: {nan_bias['overall_nan_ratio']:.4f}" if nan_bias["overall_nan_ratio"] is not None else "2) VALUE_SCORE NaN 전체 비율: N/A",
            f"3) NaN 편중 상위 버킷: {', '.join([str(x.get('bucket_name')) for x in nan_bias.get('top_biased_buckets', [])[:3]]) or 'N/A'}.",
            f"4) KR/US 분포: KR(mean={kr_m['mean']}, std={kr_m['std']}), US(mean={us_m['mean']}, std={us_m['std']}).",
            f"5) 혼합 랭킹 전 정합성 경고: {'WARN' if consistency['warn'] else 'OK'} / reasons={consistency['reasons']}",
        ],
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    out_safe = _json_safe(out)
    OUT_JSON.write_text(json.dumps(out_safe, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")

    md = []
    md.append("# STAGE5 HARDENING 3ITEMS (2026-02-18)\n")
    md.append("## 1) 롤링 연속성 검증 (value 계산 전)\n")
    md.append(f"- KR WARN: {continuity['KR']['warn_count']} / {continuity['KR']['checked']}\n")
    md.append(f"- US WARN: {continuity['US']['warn_count']} / {continuity['US']['checked']}\n")
    md.append("- 과도 결측 종목은 제외하지 않고 `WARN` 플래그로만 보고함.\n")

    md.append("\n## 2) NaN 지역 편중 검증\n")
    if nan_bias["overall_nan_ratio"] is not None:
        md.append(f"- VALUE_SCORE NaN 전체 비율: **{nan_bias['overall_nan_ratio']:.4%}**\n")
    md.append("- 상위 편중 버킷(top 10) 기준 lift_vs_overall 포함(JSON 참조).\n")
    md.append("- 시장/섹터/시총버킷 집계 포함(US 메타 미확보 구간은 UNKNOWN 버킷으로 집계).\n")

    md.append("\n## 3) KR/US 혼합 정합성 검증\n")
    md.append(f"- KR metrics: {json.dumps(kr_m, ensure_ascii=False)}\n")
    md.append(f"- US metrics: {json.dumps(us_m, ensure_ascii=False)}\n")
    md.append(f"- 혼합 랭킹 사전 경고: **{'WARN' if consistency['warn'] else 'OK'}** / {consistency['reasons']}\n")

    md.append("\n## Stage5 실행 보고서 반영용 5줄 요약\n")
    for line in out["stage5_summary_5lines"]:
        md.append(f"- {line}\n")

    md.append("\n## 검증\n")
    md.append("- py_compile: 별도 실행 결과 기록\n")
    md.append("- 스모크 실행: 별도 실행 결과 기록\n")
    md.append("- 실패 시 원인/롤백 계획: 별도 섹션 업데이트\n")

    OUT_MD.write_text("".join(md), encoding="utf-8")

    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    manifest_path = STAGE5_ROOT / 'outputs' / 'reports' / 'data_quality' / f'manifest_stage5_hardening_{ts}.json'
    write_run_manifest(
        run_type='stage5_hardening_3items',
        params={'checks': ['continuity', 'nan_bias', 'kr_us_distribution']},
        inputs=[str(SRC_BASE), str(VAL_BASE)],
        outputs=[str(OUT_MD), str(OUT_JSON)],
        out_path=str(manifest_path),
        workdir='invest',
    )

    print(f"WROTE {OUT_MD}")
    print(f"WROTE {OUT_JSON}")
    print(f"WROTE {manifest_path}")


if __name__ == "__main__":
    main()
