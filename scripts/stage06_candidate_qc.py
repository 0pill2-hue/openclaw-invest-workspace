#!/usr/bin/env python3
"""
Role: Stage06 후보군 품질게이트 점검 및 승급
Input: --input stage06_candidates.json [--promote]
Output: PASS/FAIL 콘솔 출력
Side effect: --promote 시 grade VALIDATED 승급 + watermark 제거
Author: 조비스
Updated: 2026-02-18
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ALLOWED_TRACKS = {"text", "quant", "hybrid"}
GATE_02_MDD_MIN = -0.15
GATE_03_SHARPE_MIN = -0.20
GATE_04_ALPHA_MIN = -0.18
TURNOVER_MAX = 0.55
COST_BPS_MAX = 500


def fail(msg: str) -> int:
    print(f"FAIL:{msg}")
    return 2


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--promote", action="store_true")
    args = ap.parse_args()

    p = Path(args.input)
    if not p.exists():
        return fail("input_missing")

    data = json.loads(p.read_text())
    grade = data.get("grade")
    if grade not in {"DRAFT", "VALIDATED"}:
        return fail(f"invalid_grade:{grade}")

    if "lineage_hash" not in data:
        return fail("missing_lineage_hash")

    cands = data.get("candidates", [])
    if not cands:
        return fail("no_candidates")

    seen = set()
    for c in cands:
        cid = c.get("candidate_id")
        if not cid:
            return fail("missing_candidate_id")
        if cid in seen:
            return fail(f"duplicate_candidate_id:{cid}")
        seen.add(cid)

        req = ["track", "regime_filter", "portfolio_stop", "turnover_cap", "cost_penalty_bps", "metrics", "governance_pass"]
        for k in req:
            if k not in c:
                return fail(f"missing_field:{cid}:{k}")

        if c["track"] not in ALLOWED_TRACKS:
            return fail(f"invalid_track:{cid}:{c['track']}")
        if not c["regime_filter"]:
            return fail(f"regime_filter_off:{cid}")
        if c["portfolio_stop"] > 0.07:
            return fail(f"portfolio_stop_exceed:{cid}")
        if c["turnover_cap"] > TURNOVER_MAX:
            return fail(f"turnover_exceed:{cid}")
        if c["cost_penalty_bps"] > COST_BPS_MAX:
            return fail(f"cost_bps_exceed:{cid}")
        if c["governance_pass"] is not True:
            return fail(f"governance_fail:{cid}")

        m = c["metrics"]
        for mk in ["CAGR", "MDD", "Sharpe", "rolling_sharpe_min_3m", "rolling_alpha_min_3m"]:
            if mk not in m:
                return fail(f"missing_metric:{cid}:{mk}")

        if m["MDD"] < GATE_02_MDD_MIN:
            return fail(f"gate_02_mdd:{cid}:{m['MDD']}")
        if m["rolling_sharpe_min_3m"] <= GATE_03_SHARPE_MIN:
            return fail(f"gate_03_sharpe:{cid}:{m['rolling_sharpe_min_3m']}")
        if m["rolling_alpha_min_3m"] <= GATE_04_ALPHA_MIN:
            return fail(f"gate_04_alpha:{cid}:{m['rolling_alpha_min_3m']}")

    if args.promote and grade == "DRAFT":
        data["grade"] = "VALIDATED"
        data.pop("watermark", None)
        p.write_text(json.dumps(data, ensure_ascii=False, indent=2))
        print(f"PASS:validated:candidates={len(cands)}")
        return 0

    print(f"PASS:candidates={len(cands)}:grade={grade}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
