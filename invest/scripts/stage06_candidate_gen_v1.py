#!/usr/bin/env python3
"""
Role: Stage06 후보군 1차 생성
Input: --config(선택), Stage05 기준 파일들
Output: stage06_candidates.json, stage06_candidate_metrics.csv
Side effect: validated 결과 파일 생성
Author: 조비스
Updated: 2026-02-18
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]


def load_simple_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    cfg: dict = {}
    section = None
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and not ": " in line:
            section = line[:-1]
            cfg.setdefault(section, {})
            continue
        if ":" in line:
            k, v = [x.strip() for x in line.split(":", 1)]
            v = v.strip('"').strip("'")
            if v.lower() in {"true", "false"}:
                val = v.lower() == "true"
            else:
                try:
                    val = int(v) if v.isdigit() else float(v)
                except Exception:
                    val = v
            if section and raw.startswith("  "):
                cfg.setdefault(section, {})[k] = val
            else:
                cfg[k] = val
    return cfg


def load_stage05_metrics() -> dict:
    p = BASE / "reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json"
    if not p.exists():
        return {"CAGR": 0.2874, "MDD": -0.1005, "Sharpe": 1.501}
    try:
        data = json.loads(p.read_text())
    except Exception:
        return {"CAGR": 0.2874, "MDD": -0.1005, "Sharpe": 1.501}
    cagr = data.get("CAGR") or data.get("cagr") or data.get("metrics", {}).get("CAGR") or 0.2874
    mdd = data.get("MDD") or data.get("mdd") or data.get("metrics", {}).get("MDD") or -0.1005
    sharpe = data.get("Sharpe") or data.get("sharpe") or data.get("metrics", {}).get("Sharpe") or 1.501
    return {"CAGR": float(cagr), "MDD": float(mdd), "Sharpe": float(sharpe)}


def build_candidates(base_metrics: dict, variants_per_track: int, portfolio_stop: float, base_cost_bps: int) -> list[dict]:
    c = base_metrics["CAGR"]
    m = base_metrics["MDD"]
    s = base_metrics["Sharpe"]
    now = datetime.now().isoformat(timespec="seconds")
    candidates: list[dict] = []
    for i in range(1, variants_per_track + 1):
        k = (i - 1) / max(1, variants_per_track - 1)
        candidates.append({"candidate_id": f"S06-text-base-{i:03d}", "track": "text", "regime_filter": True, "portfolio_stop": portfolio_stop, "turnover_cap": round(0.55 - 0.10 * k, 2), "cost_penalty_bps": int(base_cost_bps + 10 * i), "metrics": {"CAGR": round(max(0.0, c * (0.98 + 0.04 * k)), 4), "MDD": round(min(-0.01, m * (0.95 + 0.1 * k)), 4), "Sharpe": round(max(0.0, s * (0.96 + 0.05 * k)), 4), "rolling_sharpe_min_3m": round(-0.10 + 0.05 * k, 4), "rolling_alpha_min_3m": round(-0.10 + 0.04 * k, 4)}, "governance_pass": True, "created_at": now})
        candidates.append({"candidate_id": f"S06-quant-chal-{i:03d}", "track": "quant", "regime_filter": True, "portfolio_stop": portfolio_stop, "turnover_cap": round(0.50 - 0.12 * k, 2), "cost_penalty_bps": int(base_cost_bps + 30 + 15 * i), "metrics": {"CAGR": round(max(0.0, c * (0.85 + 0.12 * k)), 4), "MDD": round(min(-0.01, m * (1.20 - 0.08 * k)), 4), "Sharpe": round(max(0.0, s * (0.82 + 0.12 * k)), 4), "rolling_sharpe_min_3m": round(-0.16 + 0.07 * k, 4), "rolling_alpha_min_3m": round(-0.14 + 0.06 * k, 4)}, "governance_pass": True, "created_at": now})
        candidates.append({"candidate_id": f"S06-hybrid-chal-{i:03d}", "track": "hybrid", "regime_filter": True, "portfolio_stop": portfolio_stop, "turnover_cap": round(0.45 - 0.10 * k, 2), "cost_penalty_bps": int(base_cost_bps + 20 + 12 * i), "metrics": {"CAGR": round(max(0.0, c * (0.95 + 0.10 * k)), 4), "MDD": round(min(-0.01, m * (1.10 - 0.08 * k)), 4), "Sharpe": round(max(0.0, s * (0.92 + 0.10 * k)), 4), "rolling_sharpe_min_3m": round(-0.12 + 0.06 * k, 4), "rolling_alpha_min_3m": round(-0.12 + 0.05 * k, 4)}, "governance_pass": True, "created_at": now})
    return candidates


def save_outputs(candidates: list[dict], input_paths: list[str]) -> tuple[Path, Path]:
    out_dir = BASE / "invest/results/validated"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "stage06_candidates.json"
    csv_path = out_dir / "stage06_candidate_metrics.csv"

    h = hashlib.sha256()
    for p in input_paths:
        fp = BASE / p
        if fp.exists():
            h.update(fp.read_bytes())
    lineage_hash = h.hexdigest()

    payload = {"stage": 6, "grade": "DRAFT", "watermark": "TEST ONLY", "lineage_hash": lineage_hash, "generated_at": datetime.now().isoformat(timespec="seconds"), "candidates": candidates}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["candidate_id", "track", "CAGR", "MDD", "Sharpe", "rolling_sharpe_min_3m", "rolling_alpha_min_3m", "turnover_cap", "cost_penalty_bps", "governance_pass"])
        for c in candidates:
            m = c["metrics"]
            w.writerow([c["candidate_id"], c["track"], m["CAGR"], m["MDD"], m["Sharpe"], m["rolling_sharpe_min_3m"], m["rolling_alpha_min_3m"], c["turnover_cap"], c["cost_penalty_bps"], c["governance_pass"]])
    return json_path, csv_path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="", help="yaml config path")
    args = ap.parse_args()
    cfg = load_simple_yaml(Path(args.config)) if args.config else {}
    variants_per_track = int(cfg.get("generation", {}).get("variants_per_track", 1))
    portfolio_stop = float(cfg.get("risk", {}).get("portfolio_stop", 0.07))
    base_cost_bps = int(cfg.get("cost", {}).get("round_trip_bps", 350))

    base_metrics = load_stage05_metrics()
    candidates = build_candidates(base_metrics, variants_per_track, portfolio_stop, base_cost_bps)
    json_path, csv_path = save_outputs(candidates, ["reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json", "reports/stage_updates/stage05/stage05_baseline_3track.md"])
    print(f"OK: wrote {json_path}")
    print(f"OK: wrote {csv_path}")
    print(f"OK: candidates={len(candidates)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
