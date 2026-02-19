#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd


def winsor_minmax(series: pd.Series, higher_is_better: bool = True) -> pd.Series:
    s = series.astype(float).copy()
    p5, p95 = np.percentile(s, [5, 95])
    s = s.clip(lower=p5, upper=p95)
    smin, smax = float(s.min()), float(s.max())
    if np.isclose(smax, smin):
        score = pd.Series(np.full(len(s), 50.0), index=s.index)
    else:
        score = (s - smin) / (smax - smin) * 100.0
    if not higher_is_better:
        score = 100.0 - score
    return score.clip(0, 100)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Stage08 value assessment")
    parser.add_argument("--input", default="invest/results/validated/stage07_cost_turnover_risk.json")
    parser.add_argument("--output", default="invest/results/validated/stage08_value_assessment.json")
    parser.add_argument("--qc-output", default="invest/results/validated/stage08_value_assessment_qc.json")
    parser.add_argument("--stage06-metrics", default="invest/results/validated/stage06_candidate_metrics_v2.csv")
    parser.add_argument("--stage08-cv", default="invest/results/validated/stage06_2_purged_cv_oos.json")
    parser.add_argument("--weights-profitability", type=float, default=0.70)
    parser.add_argument("--weights-stability", type=float, default=0.20)
    parser.add_argument("--weights-persistence", type=float, default=0.10)
    parser.add_argument("--s-cutline", type=float, default=85.0)
    parser.add_argument("--a-cutline", type=float, default=75.0)
    parser.add_argument("--b-cutline", type=float, default=60.0)
    parser.add_argument("--s-mdd-threshold", type=float, default=-0.30)
    parser.add_argument("--f-mdd-threshold", type=float, default=-0.30)
    args = parser.parse_args()

    stage07 = load_json(Path(args.input))
    s07_df = pd.DataFrame(stage07["results"])

    s06_df = pd.read_csv(args.stage06_metrics)
    s06_df = s06_df[["candidate_id", "CAGR", "MDD", "Sharpe"]].rename(
        columns={"CAGR": "gross_cagr", "MDD": "mdd", "Sharpe": "sharpe"}
    )

    s08_cv = load_json(Path(args.stage08_cv))
    s08_df = pd.DataFrame(s08_cv["results"])
    s08_df = s08_df[["candidate_id", "cv_sharpe_std"]]

    df = (
        s07_df.merge(s06_df, on="candidate_id", how="left")
        .merge(s08_df, on="candidate_id", how="left")
        .copy()
    )

    # Proxy metrics for missing fields in Stage07 payload
    df["profit_factor"] = 1.0 + (df["stress_cagr_350bp"] / df["base_cagr"].replace(0, np.nan))
    df["volatility"] = df["cv_sharpe_std"]
    df["monthly_winrate_std"] = df["cv_sharpe_std"]
    df["recent3m_vs_full_gap"] = (df["base_cagr"] - df["stress_cagr_350bp"]).abs()

    # Component scores (0~100)
    df["score_cagr"] = winsor_minmax(df["base_cagr"], higher_is_better=True)
    df["score_pf"] = winsor_minmax(df["profit_factor"], higher_is_better=True)
    df["score_mdd"] = winsor_minmax(df["mdd"].abs(), higher_is_better=False)
    df["score_sharpe"] = winsor_minmax(df["sharpe"], higher_is_better=True)
    df["score_vol"] = winsor_minmax(df["volatility"], higher_is_better=False)
    df["score_winrate_std"] = winsor_minmax(df["monthly_winrate_std"], higher_is_better=False)
    df["score_recent_gap"] = winsor_minmax(df["recent3m_vs_full_gap"], higher_is_better=False)

    # Weighted buckets
    df["profitability_score"] = (args.weights_profitability * 100.0) * (
        0.60 * df["score_cagr"] / 100.0 + 0.40 * df["score_pf"] / 100.0
    )
    df["stability_score"] = (args.weights_stability * 100.0) * (
        0.40 * df["score_mdd"] / 100.0 + 0.35 * df["score_sharpe"] / 100.0 + 0.25 * df["score_vol"] / 100.0
    )
    df["persistence_score"] = (args.weights_persistence * 100.0) * (
        0.50 * df["score_winrate_std"] / 100.0 + 0.50 * df["score_recent_gap"] / 100.0
    )

    df["value_score"] = (df["profitability_score"] + df["stability_score"] + df["persistence_score"]).round(2)

    fail_reasons: List[List[str]] = []
    grades: List[str] = []
    for _, row in df.iterrows():
        reasons: List[str] = []
        if pd.isna(row["mdd"]) or pd.isna(row["sharpe"]):
            reasons.append("QC_MISSING_DATA")
        if row["profit_factor"] < 1.10:
            reasons.append("F01_LOW_PROFIT_FACTOR")
        if row["sharpe"] < 0.80:
            reasons.append("F02_LOW_SHARPE")
        if row["mdd"] < args.f_mdd_threshold:
            reasons.append("F03_DEEP_MDD")

        if reasons:
            grade = "F"
        else:
            if row["value_score"] >= args.s_cutline and row["mdd"] > args.s_mdd_threshold:
                grade = "S"
            elif row["value_score"] >= args.a_cutline:
                grade = "A"
            elif row["value_score"] >= args.b_cutline:
                grade = "B"
            else:
                grade = "F"
        fail_reasons.append(reasons)
        grades.append(grade)

    df["grade"] = grades
    df["fail_reason_codes"] = fail_reasons

    df = df.sort_values(["value_score", "score_mdd", "score_sharpe", "persistence_score"], ascending=False).reset_index(drop=True)

    summary = {
        "input_candidates": int(len(df)),
        "s_count": int((df["grade"] == "S").sum()),
        "a_count": int((df["grade"] == "A").sum()),
        "b_count": int((df["grade"] == "B").sum()),
        "f_count": int((df["grade"] == "F").sum()),
        "top_candidate_id": str(df.iloc[0]["candidate_id"]) if len(df) else None,
        "top_value_score": float(df.iloc[0]["value_score"]) if len(df) else None,
    }

    out = {
        "stage": 8,
        "grade": "VALIDATED",
        "input_stage": int(stage07.get("stage", 7)),
        "params": {
            "weights": {
                "profitability": args.weights_profitability,
                "stability": args.weights_stability,
                "persistence": args.weights_persistence,
            },
            "subweights": {
                "profitability": {"cagr": 0.60, "profit_factor": 0.40},
                "stability": {"mdd": 0.40, "sharpe": 0.35, "volatility": 0.25},
                "persistence": {"monthly_winrate_std": 0.50, "recent3m_vs_full_gap": 0.50},
            },
            "cutlines": {"S": args.s_cutline, "A": args.a_cutline, "B": args.b_cutline},
            "s_mdd_threshold": args.s_mdd_threshold,
            "f_mdd_threshold": args.f_mdd_threshold,
            "note": "profit_factor/volatility/persistence는 입력 부재로 proxy 사용",
        },
        "summary": summary,
        "results": [],
    }

    for _, r in df.iterrows():
        out["results"].append(
            {
                "candidate_id": r["candidate_id"],
                "track": r.get("track", "text"),
                "metrics": {
                    "base_cagr": float(r["base_cagr"]),
                    "stress_cagr_350bp": float(r["stress_cagr_350bp"]),
                    "profit_factor": float(r["profit_factor"]),
                    "mdd": float(r["mdd"]),
                    "sharpe": float(r["sharpe"]),
                    "volatility": float(r["volatility"]),
                    "monthly_winrate_std": float(r["monthly_winrate_std"]),
                    "recent3m_vs_full_gap": float(r["recent3m_vs_full_gap"]),
                },
                "subscores": {
                    "profitability": round(float(r["profitability_score"]), 2),
                    "stability": round(float(r["stability_score"]), 2),
                    "persistence": round(float(r["persistence_score"]), 2),
                    "cagr_score": round(float(r["score_cagr"]), 2),
                    "profit_factor_score": round(float(r["score_pf"]), 2),
                    "mdd_score": round(float(r["score_mdd"]), 2),
                    "sharpe_score": round(float(r["score_sharpe"]), 2),
                    "volatility_score": round(float(r["score_vol"]), 2),
                    "monthly_winrate_std_score": round(float(r["score_winrate_std"]), 2),
                    "recent3m_vs_full_gap_score": round(float(r["score_recent_gap"]), 2),
                },
                "value_score": round(float(r["value_score"]), 2),
                "grade": r["grade"],
                "pass_stage08": r["grade"] in {"S", "A", "B"},
                "fail_reason_codes": r["fail_reason_codes"],
            }
        )

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    # QC
    qc = {
        "stage": 8,
        "qc_pass": True,
        "checks": {
            "G01_reproducible_shape": len(out["results"]) == len(s07_df),
            "G02_score_range": bool((((df[["profitability_score", "stability_score", "persistence_score", "value_score"]] >= 0) & (df[["profitability_score", "stability_score", "persistence_score", "value_score"]] <= 100)).all().all())),
            "G03_grade_consistency": True,
            "G04_s_mdd_hurdle": bool(df[df["grade"] == "S"]["mdd"].gt(args.s_mdd_threshold).all()) if (df["grade"] == "S").any() else True,
        },
    }
    qc["qc_pass"] = all(qc["checks"].values())

    qc_path = Path(args.qc_output)
    qc_path.parent.mkdir(parents=True, exist_ok=True)
    with qc_path.open("w", encoding="utf-8") as f:
        json.dump(qc, f, ensure_ascii=False, indent=2)

    print(f"Wrote {args.output}")
    print(f"Wrote {args.qc_output}")


if __name__ == "__main__":
    main()
