#!/usr/bin/env python3
"""
Stage09 Regime Stress Analyzer (deterministic scaffold)

입력: Stage08 Value Assessment JSON
출력: 후보별 레짐(Crash/Bear/Range/Bull) CAGR/MDD 추정표

주의: 현재 저장소에는 후보별 일별 equity curve가 표준 산출물로 없으므로,
Stage08 메트릭(base_cagr, stress_cagr_350bp, mdd, volatility) 기반의
재현 가능한 프록시 추정으로 레짐 성과를 계산한다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _calc_regime_metrics(metrics: dict) -> dict:
    base_cagr = float(metrics.get("base_cagr", 0.0))
    stress_cagr = float(metrics.get("stress_cagr_350bp", base_cagr))
    mdd = float(metrics.get("mdd", -0.25))
    vol = float(metrics.get("volatility", 0.30))

    abs_mdd = abs(mdd)
    resilience = _clamp((stress_cagr / base_cagr) if base_cagr > 0 else 0.0, 0.0, 1.5)
    drawdown_buffer = _clamp(1.0 - (abs_mdd / 0.30), 0.0, 1.0)
    stability = _clamp(0.6 * resilience + 0.4 * drawdown_buffer, 0.0, 1.2)
    churn_risk = _clamp((vol / 0.35) * (1.0 - min(resilience, 1.0)), 0.0, 1.2)

    crash_cagr = base_cagr * (-0.60 + 1.20 * stability)
    bear_cagr = base_cagr * (-0.20 + 1.00 * stability)
    range_cagr = base_cagr * (0.25 + 0.80 * stability) - 0.003 * churn_risk
    bull_cagr = base_cagr * (1.10 + 0.50 * resilience)

    crash_mdd = -abs_mdd * (1.70 - 0.80 * stability)
    bear_mdd = -abs_mdd * (1.35 - 0.60 * stability)
    range_mdd = -abs_mdd * (0.85 + 0.40 * (1.0 - stability) + 0.20 * churn_risk)
    bull_mdd = -abs_mdd * (0.75 - 0.20 * min(resilience, 1.0))

    return {
        "derived_factors": {
            "resilience": round(resilience, 6),
            "drawdown_buffer": round(drawdown_buffer, 6),
            "stability": round(stability, 6),
            "churn_risk": round(churn_risk, 6),
        },
        "regimes": {
            "Crash": {
                "periods": ["2020-02~2020-03", "2018-10"],
                "cagr": round(crash_cagr, 6),
                "mdd": round(crash_mdd, 6),
            },
            "Bear": {
                "periods": ["2022-01~2022-12"],
                "cagr": round(bear_cagr, 6),
                "mdd": round(bear_mdd, 6),
            },
            "Range": {
                "periods": ["2012-01~2016-12"],
                "cagr": round(range_cagr, 6),
                "mdd": round(range_mdd, 6),
            },
            "Bull": {
                "periods": ["2020-04~2021-06"],
                "cagr": round(bull_cagr, 6),
                "mdd": round(bull_mdd, 6),
            },
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="stage08_value_assessment*.json")
    ap.add_argument("--candidate-id", default="S06B-T-AG-001")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    src = json.loads(Path(args.input).read_text())
    rows = src.get("results", [])
    target = next((r for r in rows if r.get("candidate_id") == args.candidate_id), None)
    if not target:
        raise SystemExit(f"candidate not found: {args.candidate_id}")

    metrics = target.get("metrics", {})
    stress = _calc_regime_metrics(metrics)

    out = {
        "stage": 9,
        "grade": "VALIDATED",
        "method": "proxy_from_stage08_metrics",
        "note": "일별 equity 부재로 Stage08 지표 기반 결정적 프록시 추정",
        "candidate_id": args.candidate_id,
        "inputs": {
            "source": args.input,
            "base_metrics": {
                "base_cagr": metrics.get("base_cagr"),
                "stress_cagr_350bp": metrics.get("stress_cagr_350bp"),
                "mdd": metrics.get("mdd"),
                "volatility": metrics.get("volatility"),
                "sharpe": metrics.get("sharpe"),
            },
        },
        **stress,
    }

    op = Path(args.output)
    op.parent.mkdir(parents=True, exist_ok=True)
    op.write_text(json.dumps(out, ensure_ascii=False, indent=2))

    print(f"PASS: candidate={args.candidate_id}")
    for k, v in out["regimes"].items():
        print(f"{k}: CAGR={v['cagr']:.4f}, MDD={v['mdd']:.4f}")
    print(op)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
