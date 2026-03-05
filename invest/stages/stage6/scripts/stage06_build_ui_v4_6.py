#!/usr/bin/env python3
from __future__ import annotations
import json
import re
import shutil
from pathlib import Path
import pandas as pd

from stage06_v4_6_winner_formula import rank_candidates_v4_6


SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_workspace_root(start: Path) -> Path:
    for p in [start] + list(start.parents):
        if p.name == "invest" and (p / "stages" / "stage6").exists():
            return p.parent
        if (p / "invest" / "stages" / "stage6").exists():
            return p
    raise RuntimeError("FAIL: cannot resolve workspace root")


BASE = _resolve_workspace_root(SCRIPT_DIR)
SINGLE_SOURCE_JSON = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_single_source_v4_6_kr.json"
VALIDATED_JSON = BASE / "invest/stages/stage6/outputs/results/validated/stage06_baselines_v4_6_kr.json"
SUMMARY_JSON = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/summary.json"
BASELINE_INHERIT_MANIFEST = BASE / "invest/stages/stage6/outputs/results/validated/stage6_baseline_inheritance/manifest.json"
BASELINE_INHERIT_MODEL = BASE / "invest/stages/stage6/outputs/results/validated/stage6_baseline_inheritance/baseline_model.json"
OUT = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/ui/index.html"
DATA_OUT = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/ui/ui_data_v4_6.json"
DATA_JS_OUT = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/ui/ui_data_v4_6.js"
CHART_CONT = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/charts/stage06_v4_6_yearly_continuous_2021plus.png"
CHART_RESET = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/charts/stage06_v4_6_yearly_reset_2021plus.png"
CHART_SOURCE_JSON = BASE / "invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_chart_inputs_v4_6_kr.json"
SIMULATED_LABEL = "SIMULATED"
LIVE_LABEL = "LIVE"


def _chart_rel_src(name: str) -> str:
    return f"charts/{name}"


def _parse_snapshot(text: str) -> list[tuple[str, float]]:
    if not text or str(text).strip() in {"", "-", "nan", "NaN", "None"}:
        return []
    rows: list[tuple[str, float]] = []
    for chunk in str(text).split(";"):
        part = chunk.strip()
        if not part:
            continue
        # 예: "SK하이닉스(000660) 41.4%, 20d" 또는 "... 41.4%"
        m = re.match(r"^(.*?)\s([0-9.]+)%(?:,\s*\d+d)?$", part)
        if not m:
            continue
        rows.append((m.group(1).strip(), float(m.group(2))))
    return rows


def _weight_change_text(prev_snapshot: str, cur_snapshot: str) -> str:
    prev_rows = _parse_snapshot(prev_snapshot)
    cur_rows = _parse_snapshot(cur_snapshot)
    if not prev_rows:
        return "-"

    prev_map = {k: v for k, v in prev_rows}
    cur_map = {k: v for k, v in cur_rows}

    changes: list[str] = []
    for name, cur_w in cur_rows:
        if name not in prev_map:
            changes.append(f"신규 {name} {cur_w:.1f}%")
        else:
            diff = cur_w - prev_map[name]
            if abs(diff) >= 0.05:
                sign = "+" if diff > 0 else "-"
                changes.append(f"{sign}{name} {abs(diff):.1f}pt")

    for name, prev_w in prev_rows:
        if name not in cur_map:
            changes.append(f"제외 {name} {prev_w:.1f}%")

    return ", ".join(changes) if changes else "-"


def _fmt_pct(v: float) -> str:
    return f"{(v or 0.0) * 100:.2f}%"


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _build_ranking_row(
    *,
    row_key: str,
    rank_label: str,
    model_id: str,
    note: str,
    ret: float | None,
    cagr: float | None,
    mdd: float | None,
) -> dict:
    has_value = model_id != "-" and ret is not None and cagr is not None and mdd is not None
    ret_v = _safe_float(ret, 0.0) if has_value else None
    cagr_v = _safe_float(cagr, 0.0) if has_value else None
    mdd_v = _safe_float(mdd, 0.0) if has_value else None
    return {
        "row_key": row_key,
        "rank_label": rank_label,
        "model_id": model_id,
        "period": "2021-01-01 ~ 최신",
        "return_2021_plus": ret_v,
        "cagr_2021_plus": cagr_v,
        "mdd_2021_plus": mdd_v,
        "return": ret_v,
        "cagr": cagr_v,
        "mdd": mdd_v,
        "return_display": _fmt_pct(ret_v) if has_value else "-",
        "cagr_display": _fmt_pct(cagr_v) if has_value else "-",
        "mdd_display": _fmt_pct(mdd_v) if has_value else "-",
        "note": note,
    }


def _load_baseline_from_inheritance() -> dict:
    baseline = {
        "model_id": "qual_q09_governance_score_v4_0",
        "return": 0.0,
        "cagr": 0.0,
        "mdd": 0.0,
        "note": "comparison_reference_default",
        "source": "comparison_reference_default",
    }

    model_path = BASELINE_INHERIT_MODEL
    if BASELINE_INHERIT_MANIFEST.exists():
        try:
            manifest = json.loads(BASELINE_INHERIT_MANIFEST.read_text(encoding="utf-8"))
            p = manifest.get("promoted_baseline_file")
            if p:
                mp = Path(str(p))
                if not mp.is_absolute():
                    mp = (BASE / mp).resolve()
                if mp.exists():
                    model_path = mp
        except Exception:
            pass

    if model_path.exists():
        try:
            raw = json.loads(model_path.read_text(encoding="utf-8"))
            w = raw.get("winner", {}) or {}
            s = w.get("stats", {}) or {}
            return {
                "model_id": f"{w.get('model_id', 'baseline')}_inherit",
                "return": _safe_float(s.get("return_2021_plus"), 0.0),
                "cagr": _safe_float(s.get("cagr_2021_plus", s.get("cagr", 0.0)), 0.0),
                "mdd": _safe_float(s.get("mdd_2021_plus", s.get("mdd_full", 0.0)), 0.0),
                "note": "inheritance",
                "source": str(model_path),
            }
        except Exception:
            pass

    return baseline


def _rank_candidates_v4_6(candidates: list[dict]) -> list[dict]:
    # winner 표시용 랭킹도 recompute와 동일한 단일 공식 argmax 경로를 사용한다.
    return rank_candidates_v4_6(candidates)


def _load_top3() -> tuple[list[dict], str, dict, dict]:
    if not VALIDATED_JSON.exists():
        raise RuntimeError(f"FAIL: missing validated file: {VALIDATED_JSON}")

    raw = json.loads(VALIDATED_JSON.read_text(encoding="utf-8"))
    actual_winner = str(raw.get("winner", {}).get("model_id", "-") or "-")
    all_results = raw.get("all_results", {})

    candidates = []
    for model_id, info in all_results.items():
        stats = info.get("stats", {}) or {}
        candidates.append({
            "model_id": model_id,
            "track": info.get("track", ""),
            "stats": stats,
        })

    ranked = _rank_candidates_v4_6(candidates)
    top3 = []
    for row in ranked[:3]:
        stats = row.get("stats", {}) or {}
        top3.append(
            {
                "model_id": row["model_id"],
                "return": _safe_float(stats.get("return_2021_plus", stats.get("total_return", 0.0)), 0.0),
                "cagr": _safe_float(stats.get("cagr_2021_plus", stats.get("cagr", 0.0)), 0.0),
                "mdd": _safe_float(stats.get("mdd_2021_plus", stats.get("mdd_full", 0.0)), 0.0),
            }
        )

    winner_row = next((
        {
            "model_id": r["model_id"],
            "return": _safe_float((r.get("stats", {}) or {}).get("return_2021_plus", (r.get("stats", {}) or {}).get("total_return", 0.0)), 0.0),
            "cagr": _safe_float((r.get("stats", {}) or {}).get("cagr_2021_plus", (r.get("stats", {}) or {}).get("cagr", 0.0)), 0.0),
            "mdd": _safe_float((r.get("stats", {}) or {}).get("mdd_2021_plus", (r.get("stats", {}) or {}).get("mdd_full", 0.0)), 0.0),
        }
        for r in ranked if r["model_id"] == actual_winner
    ), None)

    if winner_row is None and ranked:
        top = ranked[0]
        top_stats = top.get("stats", {}) or {}
        winner_row = {
            "model_id": str(top.get("model_id", "-")),
            "return": _safe_float(top_stats.get("return_2021_plus", top_stats.get("total_return", 0.0)), 0.0),
            "cagr": _safe_float(top_stats.get("cagr_2021_plus", top_stats.get("cagr", 0.0)), 0.0),
            "mdd": _safe_float(top_stats.get("mdd_2021_plus", top_stats.get("mdd_full", 0.0)), 0.0),
        }
    elif winner_row is None:
        wstats = (raw.get("winner", {}) or {}).get("stats", {})
        winner_row = {
            "model_id": actual_winner,
            "return": _safe_float(wstats.get("return_2021_plus", wstats.get("total_return", 0.0)), 0.0),
            "cagr": _safe_float(wstats.get("cagr_2021_plus", wstats.get("cagr", 0.0)), 0.0),
            "mdd": _safe_float(wstats.get("mdd_2021_plus", wstats.get("mdd_full", 0.0)), 0.0),
        }

    baseline_row = _load_baseline_from_inheritance()

    return top3, actual_winner, winner_row, baseline_row


def _load_single_source() -> dict:
    if not SINGLE_SOURCE_JSON.exists():
        raise RuntimeError(f"FAIL: missing single source file: {SINGLE_SOURCE_JSON}")
    return json.loads(SINGLE_SOURCE_JSON.read_text(encoding="utf-8"))


def _load_chart_source() -> dict:
    if not CHART_SOURCE_JSON.exists():
        return {}
    try:
        return json.loads(CHART_SOURCE_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    single_source = _load_single_source()
    weight_rows = single_source.get("weights", []) or []
    timeline_rows = single_source.get("timeline", []) or []
    derived = single_source.get("derived", {}) or {}
    kpi = single_source.get("kpi", {}) or {}
    chart_source = _load_chart_source()

    if not weight_rows or not timeline_rows:
        raise RuntimeError(
            "FAIL: single source payload missing weights/timeline rows; "
            f"weights={len(weight_rows)}, timeline={len(timeline_rows)}"
        )
    wdf = pd.DataFrame(weight_rows)
    tdf = pd.DataFrame(timeline_rows)

    if "stock_code" not in wdf.columns:
        wdf["stock_code"] = ""

    wdf["date"] = wdf["date"].astype(str)
    wdf["weight_pct"] = pd.to_numeric(wdf["weight_pct"], errors="coerce").fillna(0.0)
    wdf["holding_days"] = pd.to_numeric(wdf["holding_days"], errors="coerce").fillna(0).astype(int)

    by_date = {}
    hhi_series = []
    top1_series = []
    for d, g in wdf.groupby("date"):
        g = g.sort_values("weight_pct", ascending=False)
        items = [
            {
                "stock_name": str(r.stock_name),
                "stock_code": str(r.stock_code),
                "weight_pct": round(float(r.weight_pct), 2),
                "holding_days": int(r.holding_days),
            }
            for r in g.itertuples()
        ]
        by_date[d] = items
        ws = [x["weight_pct"] / 100.0 for x in items]
        hhi = float(sum(v * v for v in ws)) if ws else 0.0
        top1 = float(items[0]["weight_pct"]) if items else 0.0
        hhi_series.append({"date": d, "hhi": round(hhi, 4)})
        top1_series.append({"date": d, "top1": round(top1, 2)})

    dates = sorted(by_date.keys())
    latest = dates[-1] if dates else ""

    timeline_ref = []
    prev_snapshot = None
    for r in tdf.fillna("-").itertuples():
        cur_snapshot = str(getattr(r, "weights_snapshot", "-"))
        timeline_ref.append(
            {
                "date": str(r.rebalance_date),
                "added": str(r.added_codes),
                "removed": str(r.removed_codes),
                "reason": str(r.replacement_basis),
                "current": cur_snapshot,
                "weight_change": _weight_change_text(prev_snapshot or "-", cur_snapshot),
            }
        )
        prev_snapshot = cur_snapshot

    top3, winner_name, winner_row, baseline_row = _load_top3()
    if SUMMARY_JSON.exists():
        try:
            summary_payload = json.loads(SUMMARY_JSON.read_text(encoding="utf-8"))
        except Exception:
            summary_payload = {}
    else:
        summary_payload = {}
    summary_data_mode = str(summary_payload.get("data_mode", SIMULATED_LABEL) or SIMULATED_LABEL).upper()
    summary_real_ledger = bool(summary_payload.get("real_execution_ledger_used", False))
    if summary_data_mode == LIVE_LABEL and not summary_real_ledger:
        summary_data_mode = SIMULATED_LABEL
    operation_policy = summary_payload.get("operational_aggregation_policy", {}) or {}

    summary_baseline = summary_payload.get("baseline_reference", {}) or {}
    if summary_baseline:
        baseline_row = {
            "model_id": str(summary_baseline.get("label") or summary_baseline.get("model_id") or baseline_row.get("model_id", "baseline")),
            "return": _safe_float(summary_baseline.get("return_2021_plus"), baseline_row.get("return", 0.0)),
            "cagr": _safe_float(summary_baseline.get("cagr_2021_plus"), baseline_row.get("cagr", 0.0)),
            "mdd": _safe_float(summary_baseline.get("mdd_2021_plus"), baseline_row.get("mdd", 0.0)),
            "note": "summary_baseline_reference",
            "source": str(summary_baseline.get("source", baseline_row.get("source", "-"))),
        }

    winner_row = {
        "model_id": winner_name,
        "return": _safe_float(winner_row.get("return", 0.0), 0.0),
        "cagr": _safe_float(winner_row.get("cagr", 0.0), 0.0),
        "mdd": _safe_float(winner_row.get("mdd", 0.0), 0.0),
    }
    baseline_row = {
        "model_id": str(baseline_row.get("model_id", "baseline")),
        "return": _safe_float(baseline_row.get("return", 0.0), 0.0),
        "cagr": _safe_float(baseline_row.get("cagr", 0.0), 0.0),
        "mdd": _safe_float(baseline_row.get("mdd", 0.0), 0.0),
        "note": str(baseline_row.get("note", "-")),
        "source": str(baseline_row.get("source", "-")),
    }
    if derived.get("hhi_series"):
        hhi_series = derived.get("hhi_series", [])
    if derived.get("top1_series"):
        top1_series = derived.get("top1_series", [])

    ranking_rows: list[dict] = []
    for idx in range(3):
        if idx < len(top3):
            row = top3[idx]
            ranking_rows.append(_build_ranking_row(
                row_key=f"top{idx + 1}",
                rank_label=f"{idx + 1}위",
                model_id=str(row.get("model_id", "-")),
                note="우승" if str(row.get("model_id", "-")) == winner_name else "-",
                ret=row.get("return"),
                cagr=row.get("cagr"),
                mdd=row.get("mdd"),
            ))
        else:
            ranking_rows.append(_build_ranking_row(
                row_key=f"top{idx + 1}",
                rank_label=f"{idx + 1}위",
                model_id="-",
                note="-",
                ret=None,
                cagr=None,
                mdd=None,
            ))

    ranking_rows.append(_build_ranking_row(
        row_key="baseline",
        rank_label="베이스라인",
        model_id=baseline_row["model_id"],
        note=baseline_row.get("note", "-"),
        ret=baseline_row.get("return"),
        cagr=baseline_row.get("cagr"),
        mdd=baseline_row.get("mdd"),
    ))
    ranking_rows.append(_build_ranking_row(
        row_key="winner",
        rank_label="우승모델",
        model_id=winner_row["model_id"],
        note="v4_6 winner",
        ret=winner_row.get("return"),
        cagr=winner_row.get("cagr"),
        mdd=winner_row.get("mdd"),
    ))

    top_rows = [
        f"""
        <tr data-row-key='{row['row_key']}'>
          <td>{row['rank_label']}</td>
          <td>{row['model_id']}</td>
          <td>{row['period']}</td>
          <td>{row['return_display']}</td>
          <td>{row['cagr_display']}</td>
          <td>{row['mdd_display']}</td>
          <td>{row['note']}</td>
        </tr>"""
        for row in ranking_rows
    ]

    summary_baseline = summary_payload.get("baseline_reference", {}) or {}
    payload = {
        "dates": dates,
        "latest": latest,
        "weightsByDate": by_date,
        "timelineRef": timeline_ref,
        "hhiSeries": hhi_series,
        "top1Series": top1_series,
        "ranking": {
            "top3": top3,
            "winner": winner_row,
            "winner_name": winner_name,
            "baseline": baseline_row,
            "rows": ranking_rows,
        },
        "portfolio_source": {
            "path": str(SINGLE_SOURCE_JSON.relative_to(BASE)),
            "model_id": single_source.get("model_id", winner_name),
        },
        "summary_snapshot": {
            "data_mode": summary_data_mode,
            "real_execution_ledger_used": summary_real_ledger,
            "execution_ledger_source": summary_payload.get("execution_ledger_source"),
            "real_execution_parity_mode": summary_payload.get("real_execution_parity_mode", "DISABLED"),
            "real_execution_parity_pass": summary_payload.get("real_execution_parity_pass", False),
            "real_execution_parity_label": summary_payload.get("real_execution_parity_label", ""),
            "winner": summary_payload.get("winner"),
            "winner_return_2021_plus": summary_payload.get("winner_return_2021_plus"),
            "winner_cagr_2021_plus": summary_payload.get("winner_cagr_2021_plus"),
            "winner_mdd_2021_plus": summary_payload.get("winner_mdd_2021_plus"),
            "baseline_model_id": summary_baseline.get("label", summary_baseline.get("model_id")),
            "baseline_return_2021_plus": summary_baseline.get("return_2021_plus"),
            "baseline_cagr_2021_plus": summary_baseline.get("cagr_2021_plus"),
            "baseline_mdd_2021_plus": summary_baseline.get("mdd_2021_plus"),
            "final_decision": summary_payload.get("final_decision"),
            "stop_reason": summary_payload.get("stop_reason"),
            "operational_aggregation_target": operation_policy.get("target"),
            "non_winners_policy": operation_policy.get("non_winners"),
        },
        "kpi_source_snapshot": {
            "winner_return_2021_plus": kpi.get("return_2021_plus"),
            "winner_cagr_2021_plus": kpi.get("cagr_2021_plus"),
            "winner_mdd_2021_plus": kpi.get("mdd_2021_plus"),
        },
        "chart_source": {
            "path": str(CHART_SOURCE_JSON.relative_to(BASE)),
            "winner_right_edge_return_2021_plus": ((chart_source.get("continuous", {}) or {}).get("winner_right_edge_return_2021_plus")),
            "winner_peak_return_2021_plus": ((chart_source.get("continuous", {}) or {}).get("winner_peak_return_2021_plus")),
            "winner_trough_return_2021_plus": ((chart_source.get("continuous", {}) or {}).get("winner_trough_return_2021_plus")),
            "winner_year_end": ((chart_source.get("yearly_reset", {}) or {}).get("winner_year_end", [])),
            "baseline_year_end": ((chart_source.get("yearly_reset", {}) or {}).get("baseline_year_end", [])),
        },
    }

    html = f"""<!doctype html>
<html lang='ko'>
<head>
  <meta charset='utf-8'/>
  <meta name='viewport' content='width=device-width, initial-scale=1'/>
  <title>Stage06 v4_6 Portfolio UI</title>
  <style>
    body {{ font-family: -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,sans-serif; margin: 20px; background:#0f1115; color:#e8ecf1; }}
    .row {{ display:flex; gap:12px; flex-wrap:wrap; }}
    .card {{ background:#171a21; border:1px solid #2b3240; border-radius:10px; padding:12px; }}
    .kpi {{ min-width:180px; }}
    table {{ border-collapse: collapse; width:100%; margin-top:10px; }}
    th,td {{ border-bottom:1px solid #2b3240; padding:8px; font-size:13px; text-align:left; vertical-align:top; }}
    .muted {{ color:#9aa4b2; font-size:12px; }}
    select {{ background:#171a21; color:#e8ecf1; border:1px solid #2b3240; padding:6px; border-radius:8px; }}
    .btn {{ background:#202634; color:#dbe7ff; border:1px solid #32435e; border-radius:8px; padding:2px 8px; cursor:pointer; font-size:12px; }}
    .modal {{ position:fixed; inset:0; background:rgba(0,0,0,.6); display:none; align-items:center; justify-content:center; z-index:999; }}
    .panel {{ width:min(900px,95vw); max-height:90vh; overflow:auto; background:#171a21; border:1px solid #2b3240; border-radius:10px; padding:12px; }}
    .legend-item {{ font-size:12px; margin:2px 0; }}
  </style>
</head>
<body>
  <h2>Stage06 v4_6 포트폴리오 UI</h2>
  <div class='muted' style='margin-top:6px;'>게이트 요약 · 교체 판단(replacement edge/persistence/confidence) · 최근 변동 · 차트 2종 · KPI</div>
  <div class='muted' style='margin-top:4px;'>data_mode: <b>{summary_data_mode}</b> · real_execution_parity_label: <b>{summary_payload.get("real_execution_parity_label", "-") or "-"}</b> · operational_aggregation: <b>{operation_policy.get("target", "미확인")}</b> (non_winners: {operation_policy.get("non_winners", "미확인")})</div>

  <div class='card' style='margin-top:10px;'>
    <h3 style='margin:0 0 8px;'>수익률 랭킹 (1/2/3 + 베이스라인 + 우승모델)</h3>
    <table>
      <thead>
        <tr>
          <th>순위</th>
          <th>알고리즘명</th>
          <th>기간</th>
          <th>누적수익률</th>
          <th>연평균수익률(CAGR)</th>
          <th>MDD</th>
          <th>비고</th>
        </tr>
      </thead>
      <tbody>
{''.join(top_rows)}
      </tbody>
    </table>
    <div class='muted' style='margin-top:8px;'>우승한 알고리즘: <b>{winner_name}</b></div>
  </div>

  <div id='loadErr' class='muted' style='display:none;margin-top:8px;color:#ffb3b3;'></div>

  <div class='row' style='margin-top:10px;'>
    <div class='card kpi'><div class='muted'>최신 기준 Top1 비중</div><div id='kTop1'></div></div>
    <div class='card kpi'><div class='muted'>최신 기준 HHI</div><div id='kHhi'></div></div>
  </div>

  <div class='card' style='margin-top:12px;'>
    <h3>평가 차트 (고정)</h3>
    <div style='margin-top:10px;'>
      <div><b>누적 평가용</b></div>
      <img src='charts/stage06_v4_6_yearly_continuous_2021plus.png' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
    <div style='margin-top:14px;'>
      <div><b>연도별 리셋 평가용</b></div>
      <img src='charts/stage06_v4_6_yearly_reset_2021plus.png' style='width:100%;max-width:1200px;border:1px solid #2b3240;border-radius:8px;margin-top:6px;' />
    </div>
  <div class='card' style='margin-top:12px;'>
    <h3 style='margin-top:0;'>일일비중참표 (일별 비중 참조)</h3>
    <div style='margin-top:8px;'>기준일: <select id='dateSel'></select></div>
    <table id='tl'><thead><tr><th>리밸런스일</th><th>편입</th><th>편출</th><th>현재 포트폴리오(비중)</th><th>비중 변화</th><th>상세</th></tr></thead><tbody></tbody></table>
    <div style='display:flex;justify-content:center;gap:8px;align-items:center;margin-top:10px;'>
      <button id='prevRef' class='btn'>◀ 이전</button>
      <span id='refPageInfo' class='muted'>1 / 1</span>
      <button id='nextRef' class='btn'>다음 ▶</button>
    </div>
  </div>


  </div>

  <div id='pieModal' class='modal'>
    <div class='panel'>
      <div style='display:flex;justify-content:space-between;align-items:center;'>
        <h3 id='pieTitle'>포트폴리오 원형그래프</h3>
        <button id='closeModal' class='btn'>닫기</button>
      </div>
      <canvas id='pieCanvas' width='520' height='520' style='max-width:100%;background:#0f1115;border-radius:8px;'></canvas>
      <div id='pieLegend' style='margin-top:10px;'></div>
    </div>
  </div>

<script src='./ui_data_v4_6.js'></script>
<script>
const PAGE_SIZE = 20;
let refPage = 1;
let DATA = null;

function parseCurrentPortfolio(text) {{
  if (!text || text === '-') return [];
  return String(text).split(';').map(x=>x.trim()).filter(Boolean).map(row => {{
    const m = row.match(/^(.*?)\\s([0-9.]+)%(?:,\\s*\\d+d)?$/);
    if (!m) return null;
    return {{ name: m[1].trim(), w: parseFloat(m[2]) }};
  }}).filter(Boolean);
}}

function drawPie(items, title) {{
  const modal = document.getElementById('pieModal');
  const c = document.getElementById('pieCanvas');
  const ctx = c.getContext('2d');
  const legend = document.getElementById('pieLegend');
  document.getElementById('pieTitle').textContent = title;
  ctx.clearRect(0,0,c.width,c.height);
  legend.innerHTML = '';

  if (!items.length) {{
    ctx.fillStyle='#9aa4b2';
    ctx.font='16px sans-serif';
    ctx.fillText('데이터 없음', 210, 260);
    modal.style.display='flex';
    return;
  }}

  const colors = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd','#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf'];
  let total = items.reduce((a,b)=>a+b.w,0);
  let start = -Math.PI/2;
  const cx=260, cy=260, r=190;

  items.forEach((it, idx) => {{
    const frac = it.w / total;
    const end = start + frac * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx,cy);
    ctx.arc(cx,cy,r,start,end);
    ctx.closePath();
    ctx.fillStyle = colors[idx % colors.length];
    ctx.fill();
    start = end;

    const div = document.createElement('div');
    div.className='legend-item';
    div.innerHTML = `<span style="display:inline-block;width:10px;height:10px;background:${{colors[idx % colors.length]}};margin-right:6px;"></span>${{it.name}} - ${{it.w.toFixed(1)}}%`;
    legend.appendChild(div);
  }});

  modal.style.display='flex';
}}

function renderRef() {{
  const sel = document.getElementById('dateSel');
  const d = sel.value;
  const top1Map = new Map((DATA.top1Series || []).map(x => [String(x.date), Number(x.top1)]));
  const hhiMap = new Map((DATA.hhiSeries || []).map(x => [String(x.date), Number(x.hhi)]));
  const top1 = top1Map.get(String(d));
  const hhi = hhiMap.get(String(d));
  document.getElementById('kTop1').textContent = Number.isFinite(top1) ? (top1.toFixed(2) + '%') : '-';
  document.getElementById('kHhi').textContent = Number.isFinite(hhi) ? hhi.toFixed(4) : '-';

  const tlb = document.querySelector('#tl tbody'); tlb.innerHTML='';
  const ordered = [...(DATA.timelineRef || [])].reverse();
  const totalPages = Math.max(1, Math.ceil(ordered.length / PAGE_SIZE));
  if (refPage > totalPages) refPage = totalPages;
  const start = (refPage - 1) * PAGE_SIZE;
  const pageRows = ordered.slice(start, start + PAGE_SIZE);
  pageRows.forEach(t => {{
    const tr=document.createElement('tr');
    tr.innerHTML = '<td>' + (t.date || '-') + '</td>'
      + '<td>' + (t.added || '-') + '</td>'
      + '<td>' + (t.removed || '-') + '</td>'
      + '<td>' + (t.current || '-') + '</td>'
      + '<td>' + (t.weight_change || '-') + '</td>'
      + '<td><button class="btn">더보기</button></td>';
    tr.querySelector('button').addEventListener('click', () => {{
      const items = parseCurrentPortfolio(t.current || '-');
      drawPie(items, `포트폴리오 비중 - ${{t.date}}`);
    }});
    tlb.appendChild(tr);
  }});

  document.getElementById('refPageInfo').textContent = refPage + ' / ' + totalPages;
  document.getElementById('prevRef').disabled = refPage <= 1;
  document.getElementById('nextRef').disabled = refPage >= totalPages;
}}

async function loadData() {{
  try {{
    const resp = await fetch('./ui_data_v4_6.json', {{cache:'no-store'}});
    if (!resp.ok) throw new Error(`HTTP ${{resp.status}}`);
    return await resp.json();
  }} catch (e) {{
    if (window.__UI_DATA_V4_6__) return window.__UI_DATA_V4_6__;
    throw e;
  }}
}}

async function init() {{
  try {{
    DATA = await loadData();
  }} catch (e) {{
    const err = document.getElementById('loadErr');
    err.style.display = 'block';
    err.textContent = '데이터 로딩 실패: ui_data_v4_6.json 확인 또는 HTTP 서버에서 열어주세요.';
    return;
  }}

  const sel = document.getElementById('dateSel');
  (DATA.dates || []).forEach(d => {{
    const o=document.createElement('option');
    o.value=d; o.textContent=d;
    sel.appendChild(o);
  }});
  sel.value = DATA.latest;

  renderRef();

  sel.addEventListener('change', renderRef);
  document.getElementById('prevRef').addEventListener('click', () => {{ if (refPage > 1) {{ refPage -= 1; renderRef(); }} }});
  document.getElementById('nextRef').addEventListener('click', () => {{
    const totalPages = Math.max(1, Math.ceil((DATA.timelineRef || []).length / PAGE_SIZE));
    if (refPage < totalPages) {{ refPage += 1; renderRef(); }}
  }});

  document.getElementById('closeModal').addEventListener('click', () => {{ document.getElementById('pieModal').style.display='none'; }});
  document.getElementById('pieModal').addEventListener('click', (e) => {{ if (e.target.id === 'pieModal') document.getElementById('pieModal').style.display='none'; }});
}}

init();
</script>
</body></html>"""

    OUT.parent.mkdir(parents=True, exist_ok=True)
    chart_ui_dir = OUT.parent / "charts"
    chart_ui_dir.mkdir(parents=True, exist_ok=True)
    if CHART_CONT.exists():
        shutil.copy2(CHART_CONT, chart_ui_dir / CHART_CONT.name)
    if CHART_RESET.exists():
        shutil.copy2(CHART_RESET, chart_ui_dir / CHART_RESET.name)

    payload_json = json.dumps(payload, ensure_ascii=False, indent=2)
    DATA_OUT.write_text(payload_json, encoding="utf-8")
    DATA_JS_OUT.write_text(f"window.__UI_DATA_V4_6__ = {payload_json};\n", encoding="utf-8")
    OUT.write_text(html, encoding="utf-8")
    print(json.dumps({
        "status": "ok",
        "out": str(OUT.relative_to(BASE)),
        "data": str(DATA_OUT.relative_to(BASE)),
        "data_js": str(DATA_JS_OUT.relative_to(BASE)),
        "single_source": str(SINGLE_SOURCE_JSON.relative_to(BASE)),
        "chart_source": str(CHART_SOURCE_JSON.relative_to(BASE)),
        "ranking_source": str(VALIDATED_JSON.relative_to(BASE)),
        "winner": winner_name,
        "baseline_source": baseline_row.get("source", "-"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
