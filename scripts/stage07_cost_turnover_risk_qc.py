#!/usr/bin/env python3
"""
Role: Stage09 QC
Input: --results stage07_cost_turnover_risk.json
Output: stage07_cost_turnover_risk_qc.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    p = Path(args.results)
    if not p.exists():
        print("FAIL:results_missing")
        return 2

    d = json.loads(p.read_text())
    rows = d.get("results", [])
    if not rows:
        print("FAIL:empty_results")
        return 2

    survivors = [r for r in rows if r.get("pass_stage09")]
    failures = [r for r in rows if not r.get("pass_stage09")]

    failure_reasons = []
    for r in failures:
        failure_reasons.append(
            {
                "candidate_id": r.get("candidate_id"),
                "fail_reason_codes": r.get("fail_reason_codes", []),
                "stress_cagr_350bp": r.get("stress_cagr_350bp"),
                "avg_monthly_turnover": r.get("avg_monthly_turnover"),
                "low_liquidity_entry_ratio": r.get("low_liquidity_entry_ratio"),
            }
        )

    champion_id = d.get("summary", {}).get("champion_candidate_id")
    champion_row = next((r for r in survivors if r.get("candidate_id") == champion_id), None)
    champion_positive_under_harsh = bool(champion_row and champion_row.get("stress_cagr_350bp", 0) > 0)

    qc = {
        "stage": 9,
        "qc_pass": len(survivors) >= 1,
        "input_count": len(rows),
        "survivor_count": len(survivors),
        "survivor_ids": [r.get("candidate_id") for r in survivors],
        "failed_count": len(failures),
        "failure_details": failure_reasons,
        "champion_candidate_id": champion_id,
        "champion_stress_cagr_350bp": champion_row.get("stress_cagr_350bp") if champion_row else None,
        "champion_positive_under_harsh": champion_positive_under_harsh,
    }

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(qc, ensure_ascii=False, indent=2))

    if qc["qc_pass"]:
        print(f"PASS:qc survivors={qc['survivor_count']} champion={champion_id}")
        return 0

    print("FAIL:qc_no_survivor")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
