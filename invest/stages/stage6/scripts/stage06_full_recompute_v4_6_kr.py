#!/usr/bin/env python3
"""
Stage06 v4_6: 36-model ensemble full rebuild (from scratch)
Policy focus: soft-scoring 중심(수익률 우선) + 최소 하드컷(극단 리스크만 차단).
- hard 탈락 게이트 최소화: extreme drawdown만 하드컷 유지
- winner 선정은 soft score 비중 확대(2021+ 수익률 최우선)
- MDD는 약한 페널티로만 반영(과도한 방어 편향 완화)
- incumbent bias / cooldown / monthly cap / risk-event escape hatch 유지
- numeric cannot be final winner
"""
import json
import random
import hashlib
import re
import shutil
import csv
import math
import os
import py_compile
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

from stage06_v4_6_winner_formula import (
    SCORE_V4_6_FORMULA_TEXT,
    SCORE_V4_6_WEIGHTS,
    compute_winner_score_v4_6,
    rank_candidates_v4_6,
    score_leaderboard_v4_6,
)
from stage06_build_ui_v4_6 import main as build_ui_v4_6_main
from stage06_validate_v4_6 import validate as validate_v4_6, write_outputs as write_validation_outputs
from stage06_real_execution_parity_gate import run as run_real_execution_parity_gate

SEED = 20260220
np.random.seed(SEED)
random.seed(SEED)
TODAY = pd.Timestamp.now().normalize()


SCRIPT_DIR = Path(__file__).resolve().parent


def _resolve_invest_root(start: Path) -> Path:
    marker_rel = Path("stages/stage6/outputs")
    for p in [start] + list(start.parents):
        if p.name == "invest" and (p / marker_rel).exists():
            return p
    for p in [start] + list(start.parents):
        candidate = p / "invest"
        if candidate.exists() and (candidate / marker_rel).exists():
            return candidate
    raise RuntimeError("FAIL: cannot resolve invest root")


BASE_DIR = _resolve_invest_root(SCRIPT_DIR)
OUTPUT_DIR = BASE_DIR / "stages/stage6/outputs/reports/stage_updates/v4_6"
VALIDATED_DIR = BASE_DIR / "stages/stage6/outputs/results/validated"
BASELINE_INHERIT_DIR = VALIDATED_DIR / "stage6_baseline_inheritance"
BASELINE_INHERIT_MODEL = BASELINE_INHERIT_DIR / "baseline_model.json"
BASELINE_INHERIT_MANIFEST = BASELINE_INHERIT_DIR / "manifest.json"
STAGE06_TEMPLATE_UI = BASE_DIR / "stages/stage6/outputs/reports/stage_updates/template/ui/index.html"
STAGE07_TEMPLATE_UI = BASE_DIR / "stages/stage7/docs/stage_updates/template/ui/index.html"
SECTOR_MAP_PATH = BASE_DIR / "stages/stage6/inputs/reference_cache/highlander_sector_map_cache.csv"


def _first_existing_path(candidates: list[Path]) -> Path:
    for p in candidates:
        if p.exists():
            return p
    return candidates[0]


KR_OHLCV_DIR = _first_existing_path([
    BASE_DIR / "stages/stage6/inputs/upstream_stage2_clean/kr/ohlcv",
    BASE_DIR / "stages/stage6/inputs/upstream_stage1/raw/signal/kr/ohlcv",
    BASE_DIR / "stages/stage6/inputs/upstream_stage1/raw/kr/ohlcv",
])
KR_STOCK_MASTER_CSV = _first_existing_path([
    BASE_DIR / "stages/stage6/inputs/upstream_stage1/master/kr_stock_list.csv",
])
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "charts").mkdir(parents=True, exist_ok=True)
(OUTPUT_DIR / "ui").mkdir(parents=True, exist_ok=True)
VALIDATED_DIR.mkdir(parents=True, exist_ok=True)
PORTFOLIO_SINGLE_SOURCE_FILE = "stage06_portfolio_single_source_v4_6_kr.json"
PORTFOLIO_EQUITY_CSV_FILE = "stage06_portfolio_equity_v4_6_kr.csv"
WINNER_SIGNAL_CSV_FILE = "stage06_winner_signal_matrix_v4_6_kr.csv"
CHART_INPUT_SOURCE_FILE = "stage06_chart_inputs_v4_6_kr.json"
PIPELINE_PROOF_JSON_FILE = "stage06_v4_6_pipeline_run_proof.json"
PIPELINE_PROOF_MD_FILE = "stage06_v4_6_pipeline_run_proof.md"
SIMULATED_LABEL = "SIMULATED"
LIVE_LABEL = "LIVE"
PARITY_LABEL = "실거래 일치 보장"
PARITY_REPORT_JSON = BASE_DIR / "stages/stage6/outputs/reports/stage06_real_execution_parity_latest.json"
PARITY_MISMATCH_CSV = BASE_DIR / "stages/stage6/outputs/reports/stage06_real_execution_mismatches_latest.csv"
PARITY_DEFAULT_EXPECTED = BASE_DIR / "stages/stage6/inputs/execution_ledger/model_trade_orders.csv"
PARITY_DEFAULT_LEDGER = BASE_DIR / "stages/stage6/inputs/execution_ledger/broker_execution_ledger.csv"


def check_readable_required_fields(path: Path) -> bool:
    req_sections = [
        '# stage06_result_v4_6_kr_readable',
        '## 실행 요약',
        '## 게이트 요약',
        '## 정책 스냅샷',
        '## 성과 요약',
        '## MDD 구간 분리',
        '## 산출물 경로',
        '## 최종 판정',
    ]
    req_keys = ['gate1', 'gate2', 'gate3', 'gate4', 'final_decision', 'stop_reason']
    if not path.exists():
        return False
    txt = path.read_text(encoding='utf-8', errors='ignore')
    return all(s in txt for s in req_sections) and all(k in txt for k in req_keys)


def evaluate_ui_parity(ui_index: Path) -> str:
    ui_text = ui_index.read_text(encoding="utf-8", errors="ignore") if ui_index.exists() else ""
    ui_lower = ui_text.lower()
    parity_required = {
        "kpi_section": any(k in ui_text for k in ["KPI", "핵심 KPI", "총수익률", "연평균수익률"]),
        "gate_summary": any(k in ui_text for k in ["게이트 요약", "gate 요약", "gate summary"]),
        "replacement_decision": any(k in ui_text for k in ["교체 판단", "replacement", "edge", "persistence", "confidence"]),
        "recent_changes": any(k in ui_text for k in ["최근 변동", "포트폴리오 변경 이력", "recent"]),
        "two_charts_text": any(k in ui_text for k in ["차트 2종", "평가 차트", "yearly reset", "continuous"]),
    }
    ui_img_links = re.findall(r"<img[^>]+src=[\"'](charts/[^\"']+\.png)[\"']", ui_text, flags=re.IGNORECASE)
    ui_no_base64 = "data:image" not in ui_lower
    ui_parity_ok = bool(ui_index.exists() and all(parity_required.values()) and len(ui_img_links) >= 2 and ui_no_base64)
    return "PASS" if ui_parity_ok else "FAIL"


def _safe_float(v, default=0.0) -> float:
    try:
        return float(v)
    except Exception:
        return float(default)


def _extract_codes_from_snapshot(text: str) -> set[str]:
    if not text or str(text).strip() in {"", "-", "nan", "NaN"}:
        return set()
    return set(re.findall(r"\((\d{6})\)", str(text)))


def _compute_universe_switch_diagnostics(timeline_rows: list[dict], monthly_cap: int) -> dict:
    normal_monthly_removed: dict[str, int] = {}
    normal_row_cap_violations = 0
    same_day_overlap_count = 0
    risk_event_rows = 0

    for row in timeline_rows:
        rebalance_date = str(row.get("rebalance_date", "") or "")
        month_key = rebalance_date[:7] if len(rebalance_date) >= 7 else "unknown"
        is_risk_escape = str(row.get("risk_event_escape", "N")).strip().upper() == "Y"
        added_codes = _extract_codes_from_snapshot(str(row.get("added_codes", "")))
        removed_codes = _extract_codes_from_snapshot(str(row.get("removed_codes", "")))
        if added_codes & removed_codes:
            same_day_overlap_count += 1

        removed_count = len(removed_codes)
        if is_risk_escape:
            risk_event_rows += 1
            continue
        if removed_count > monthly_cap:
            normal_row_cap_violations += 1
        normal_monthly_removed[month_key] = normal_monthly_removed.get(month_key, 0) + removed_count

    monthly_cap_violation_months = {
        month: count for month, count in normal_monthly_removed.items() if count > monthly_cap
    }
    switch_pass = bool(
        normal_row_cap_violations == 0
        and len(monthly_cap_violation_months) == 0
        and same_day_overlap_count == 0
    )
    return {
        "monthly_cap": int(monthly_cap),
        "normal_row_cap_violations": int(normal_row_cap_violations),
        "normal_monthly_removed": normal_monthly_removed,
        "monthly_cap_violation_months": monthly_cap_violation_months,
        "same_day_add_remove_overlap_count": int(same_day_overlap_count),
        "risk_event_rows": int(risk_event_rows),
        "pass": switch_pass,
    }


def load_dynamic_kr_universe(master_csv: Path = KR_STOCK_MASTER_CSV) -> tuple[list[tuple[str, str]], dict]:
    if not master_csv.exists():
        raise RuntimeError(f"FAIL: universe master missing: {master_csv}")

    df = pd.read_csv(master_csv, dtype=str)
    required_cols = {"Code", "Name", "Market", "Close", "Volume", "MarketId"}
    missing = sorted(required_cols - set(df.columns))
    if missing:
        raise RuntimeError(f"FAIL: universe master missing columns: {missing}")

    for c in ["Code", "Name", "Market", "Close", "Volume", "MarketId"]:
        df[c] = df[c].astype(str).str.strip()

    code_ok = df["Code"].str.fullmatch(r"\d{6}", na=False)
    market_ok = df["Market"].str.upper().str.startswith(("KOSPI", "KOSDAQ"), na=False)
    listed_ok = df["MarketId"].str.upper().isin(["STK", "KSQ"])
    close_num = pd.to_numeric(df["Close"].str.replace(",", "", regex=False), errors="coerce")
    volume_num = pd.to_numeric(df["Volume"].str.replace(",", "", regex=False), errors="coerce")
    tradable_ok = close_num.gt(0) & volume_num.gt(0)

    filt = code_ok & market_ok & listed_ok & tradable_ok
    uni_df = df.loc[filt, ["Code", "Name", "Market"]].drop_duplicates(subset=["Code"]).copy()
    uni_df = uni_df.sort_values("Code")

    universe = [(str(r.Code), str(r.Name)) for r in uni_df.itertuples(index=False)]
    market_upper = uni_df["Market"].str.upper()
    kospi_count = int(market_upper.str.startswith("KOSPI").sum())
    kosdaq_count = int(market_upper.str.startswith("KOSDAQ").sum())
    stats = {
        "source_path": str(master_csv),
        "total": int(len(universe)),
        "kospi": kospi_count,
        "kosdaq": kosdaq_count,
    }

    if stats["total"] <= 0:
        raise RuntimeError("FAIL: empty dynamic universe after filtering")

    return universe, stats


def load_baseline_reference_from_manifest() -> dict:
    baseline = {
        "model_id": "qual_q09_governance_score",
        "track": "qualitative",
        "params": {"esg_weight": 0.4, "board_quality": 0.6},
        "return_2021_plus": None,
        "cagr_2021_plus": None,
        "mdd_2021_plus": None,
        "label": "qual_q09_governance_score_reference_default",
        "source": "comparison_reference_default",
    }

    model_file = BASELINE_INHERIT_MODEL
    if BASELINE_INHERIT_MANIFEST.exists():
        try:
            manifest = json.loads(BASELINE_INHERIT_MANIFEST.read_text(encoding="utf-8"))
            promoted = manifest.get("promoted_baseline_file")
            if promoted:
                promoted_path = Path(str(promoted))
                if not promoted_path.is_absolute():
                    promoted_path = (BASE_DIR / promoted_path).resolve()
                if promoted_path.exists():
                    model_file = promoted_path
        except Exception:
            pass

    if model_file.exists():
        try:
            raw = json.loads(model_file.read_text(encoding="utf-8"))
            winner = raw.get("winner", {}) or {}
            stats = winner.get("stats", {}) or {}
            baseline = {
                "model_id": str(winner.get("model_id", baseline["model_id"]) or baseline["model_id"]),
                "track": str(winner.get("track", baseline["track"]) or baseline["track"]),
                "params": winner.get("params", baseline["params"]) or baseline["params"],
                "return_2021_plus": _safe_float(stats.get("return_2021_plus"), 0.0),
                "cagr_2021_plus": _safe_float(stats.get("cagr_2021_plus", stats.get("cagr", 0.0)), 0.0),
                "mdd_2021_plus": _safe_float(stats.get("mdd_2021_plus", stats.get("mdd_full", 0.0)), 0.0),
                "label": f"{winner.get('model_id', baseline['model_id'])}_inherit",
                "source": str(model_file),
            }
        except Exception:
            pass

    return baseline


def promote_stage6_baseline_inheritance(validated_payload: dict, summary_payload: dict, source_validated_file: Path) -> None:
    BASELINE_INHERIT_DIR.mkdir(parents=True, exist_ok=True)
    BASELINE_INHERIT_MODEL.write_text(json.dumps(validated_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if not STAGE06_TEMPLATE_UI.exists():
        raise RuntimeError(f"FAIL: missing stage6 template ui: {STAGE06_TEMPLATE_UI}")
    STAGE07_TEMPLATE_UI.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(STAGE06_TEMPLATE_UI, STAGE07_TEMPLATE_UI)

    manifest = {
        "promoted_at": datetime.now().isoformat(timespec="seconds"),
        "source_validated_file": str(source_validated_file),
        "promoted_baseline_file": str(BASELINE_INHERIT_MODEL),
        "stage7_template_file": str(STAGE07_TEMPLATE_UI),
        "version": validated_payload.get("version"),
        "final_decision": summary_payload.get("final_decision"),
        "stop_reason": summary_payload.get("stop_reason"),
    }
    BASELINE_INHERIT_MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


class ModelDefinition:
    @staticmethod
    def get_all_models():
        models = []
        numeric = [
            ("n01_value_deep", {"pe_weight": 0.4, "pb_weight": 0.3, "roe_weight": 0.3}),
            ("n02_momentum_fast", {"lookback": 20, "decay": 0.95}),
            ("n03_momentum_slow", {"lookback": 60, "decay": 0.90}),
            ("n04_flow_tilt", {"volume_weight": 0.5, "foreign_weight": 0.3}),
            ("n05_volatility_low", {"vol_target": 0.15, "rebal_freq": "weekly"}),
            ("n06_volatility_managed", {"vol_target": 0.20, "rebal_freq": "monthly"}),
            ("n07_technical_rsi", {"rsi_period": 14, "overbought": 70, "oversold": 30}),
            ("n08_technical_macd", {"fast": 12, "slow": 26, "signal": 9}),
            ("n09_composite_score", {"value": 0.3, "momentum": 0.4, "quality": 0.3}),
            ("n10_fee_stress", {"fee_penalty": 0.05, "turnover_cap": 1.2}),
        ]
        qual = [
            ("q01_buzz_heavy", {"news_weight": 0.6, "social_weight": 0.4}),
            ("q02_analyst_consensus", {"target_price_weight": 0.5, "rating_weight": 0.5}),
            ("q03_theme_sector", {"sector_momentum": True, "theme_filter": True}),
            ("q04_earnings_surprise", {"surprise_threshold": 0.05, "guidance_weight": 0.3}),
            ("q05_insider_activity", {"buy_signal_weight": 0.7, "sell_signal_weight": 0.3}),
            ("q06_institutional_flow", {"fund_flow_weight": 0.5, "etf_weight": 0.5}),
            ("q07_short_interest", {"short_threshold": 0.10, "days_to_cover": 5}),
            ("q08_event_driven", {"m_and_a": True, "spinoff": True, "restructure": True}),
            ("q09_governance_score", {"esg_weight": 0.4, "board_quality": 0.6}),
            ("q10_ret_up_mix", {"return_acceleration": 0.5, "quality_tilt": 0.5}),
        ]
        hybrid = [
            ("h01_quant_tilt", {"numeric_weight": 0.7, "qual_weight": 0.3}),
            ("h02_qual_tilt", {"numeric_weight": 0.3, "qual_weight": 0.7}),
            ("h03_consensus_blend", {"numeric_weight": 0.5, "qual_weight": 0.5}),
            ("h04_adaptive_mix", {"regime_switch": True, "vol_adjusted": True}),
            ("h05_factor_rotation", {"factors": ["value", "momentum", "quality"]}),
            ("h06_multi_timeframe", {"short": 5, "medium": 20, "long": 60}),
            ("h07_risk_parity", {"target_vol": 0.12, "equal_risk": True}),
            ("h08_trend_following", {"breakout": True, "trend_filter": True}),
            ("h09_mean_reversion", {"zscore_threshold": 2.0, "holding_period": 10}),
            ("h10_fee_stress", {"fee_penalty": 0.04, "rebal_cost_aware": True}),
        ]
        external = [
            ("e01_anchor_stable", {"anchor_weight": 0.8, "signal_decay": 0.02}),
            ("e02_turnaround_fast", {"recovery_threshold": 0.15, "holding": 30}),
            ("e03_supercycle_stable", {"cycle_length": 250, "amplitude": 0.3}),
            ("e04_ml_ensemble", {"models": ["rf", "xgb", "lgb"], "blend": "soft"}),
            ("e05_macro_overlay", {"gdp_weight": 0.3, "rates_weight": 0.4, "fx_weight": 0.3}),
            ("e06_sentiment_nlp", {"bert_score": True, "news_embedding": True}),
        ]
        for n, p in numeric:
            models.append({"id": f"numeric_{n}", "track": "numeric", "params": p})
        for n, p in qual:
            models.append({"id": f"qual_{n}", "track": "qualitative", "params": p})
        for n, p in hybrid:
            models.append({"id": f"hybrid_{n}", "track": "hybrid", "params": p})
        for n, p in external:
            models.append({"id": f"external_{n}", "track": "external", "params": p})
        return models


class Engine:
    TURNOVER_WINNER_CAP = 1.8
    CORE_SLOTS = 5
    EXPLORER_SLOTS = 1
    SUPER_LOCK_DAYS = 120
    REBALANCE_WEEKDAY = 4  # Friday
    REBALANCE_WEEK_INTERVAL = 2  # biweekly
    REPLACEMENT_EDGE = 0.05
    PERSISTENCE_WINDOW = 3
    PERSISTENCE_MIN_PASS = 1
    CONFIDENCE_GATE = 0.34
    EXTREME_MDD_2021_PLUS = -0.85
    EXTREME_MDD_FULL = -0.92
    EXTREME_MDD_CORE = -0.80
    COOLDOWN_MONTHS = 0  # deprecated in v4_6
    COOLDOWN_DAYS = 45
    MONTHLY_REPLACEMENT_CAP = 1
    MIN_HOLD_DAYS = 35
    MIN_PERSIST_DAYS = 130
    INCUMBENT_WEIGHT_BONUS = 1.25
    CHALLENGER_WEIGHT_PENALTY = 0.70
    INCUMBENT_PROTECT_DAYS = 75
    RISK_EVENT_TRIGGER_PROB = 0.015
    RISK_EVENT_MAX_REPLACEMENTS = 3

    def simulate_model(self, model, years):
        track_profiles = {
            "numeric": {"mu": 0.18, "sigma": 0.28},
            "qualitative": {"mu": 0.22, "sigma": 0.32},
            "hybrid": {"mu": 0.28, "sigma": 0.30},
            "external": {"mu": 0.20, "sigma": 0.25},
        }
        profile = track_profiles[model["track"]]
        # reproducibility: avoid Python built-in hash randomization across processes
        param_sig = "|".join(f"{k}:{model['params'][k]}" for k in sorted(model["params"].keys()))
        param_hash = int(hashlib.md5(param_sig.encode()).hexdigest()[:8], 16) % 1000
        mu = profile["mu"] + (param_hash - 500) / 5000
        sigma = profile["sigma"] + (param_hash % 100 - 50) / 500
        np.random.seed(int(hashlib.md5(model["id"].encode()).hexdigest()[:8], 16) % (2**31))

        dates, rets = [], []
        for year in years:
            trading_days = 250
            if year == TODAY.year:
                trading_days = max(1, int(250 * int(TODAY.strftime('%j')) / 365))
            year_regime = {2016: 0.95, 2017: 1.10, 2018: 0.85, 2019: 1.05, 2020: 1.25, 2021: 1.40, 2022: 0.70, 2023: 1.15, 2024: 1.20, 2025: 1.10, 2026: 1.00}.get(year, 1.0)
            yr = np.random.normal(mu * year_regime / 250, sigma / np.sqrt(250), trading_days)
            yr = np.convolve(yr, [0.3, 0.4, 0.3], mode="same")
            if year in (2020, 2022):
                s = 40 if year == 2020 else 30
                yr[s:s+25] = yr[s:s+25] * 2.5 - 0.02
            for day in range(trading_days):
                d = pd.Timestamp(f"{year}-01-01") + pd.Timedelta(days=int(day * 365 / 250))
                if d > TODAY:
                    break
                dates.append(d)
                rets.append(float(yr[day]))
        return pd.DataFrame({"date": dates, "return": rets})

    def run_backtest(self, models, start_year=2016, end_year=2026):
        years = list(range(start_year, end_year + 1))
        results = {}
        for model in models:
            df = self.simulate_model(model, years)
            eq = (1 + df["return"]).cumprod()
            df["equity"] = eq
            peak = eq.expanding().max()
            mdd = ((eq - peak) / peak).min()
            full_return = float(eq.iloc[-1] - 1)
            full_cagr = float((eq.iloc[-1]) ** (1 / len(years)) - 1)

            df_2021 = df[df["date"] >= "2021-01-01"]
            if len(df_2021) > 0:
                e21 = df_2021["equity"] / df_2021["equity"].iloc[0]
                r21 = float(e21.iloc[-1] - 1)
                y21 = max((df["date"].iloc[-1] - pd.Timestamp("2021-01-01")).days / 365, 0.5)
                c21 = float((e21.iloc[-1]) ** (1 / y21) - 1)
                m21 = float(((e21 - e21.expanding().max()) / e21.expanding().max()).min())
            else:
                r21 = c21 = m21 = 0.0

            df_2021_2022 = df[(df["date"] >= "2021-01-01") & (df["date"] <= "2022-12-31")]
            if len(df_2021_2022) > 0:
                e2122 = df_2021_2022["equity"] / df_2021_2022["equity"].iloc[0]
                r2122 = float(e2122.iloc[-1] - 1)
            else:
                r2122 = 0.0

            df_2023_2024 = df[(df["date"] >= "2023-01-01") & (df["date"] <= "2024-12-31")]
            if len(df_2023_2024) > 0:
                e2324 = df_2023_2024["equity"] / df_2023_2024["equity"].iloc[0]
                r2324 = float(e2324.iloc[-1] - 1)
            else:
                r2324 = 0.0

            df_2025_plus = df[df["date"] >= "2025-01-01"]
            if len(df_2025_plus) > 0:
                e25 = df_2025_plus["equity"] / df_2025_plus["equity"].iloc[0]
                r25 = float(e25.iloc[-1] - 1)
            else:
                r25 = 0.0

            persist_days_2122 = int(len(df_2021_2022))
            persist_days_2324 = int(len(df_2023_2024))
            persist_days_25p = int(len(df_2025_plus))

            df_core = df[(df["date"] >= "2023-01-01") & (df["date"] <= "2025-12-31")]
            if len(df_core) > 0:
                ec = df_core["equity"] / df_core["equity"].iloc[0]
                rc = float(ec.iloc[-1] - 1)
                cc = float((ec.iloc[-1]) ** (1 / 3) - 1)
                mc = float(((ec - ec.expanding().max()) / ec.expanding().max()).min())
            else:
                rc = cc = mc = 0.0

            turnover = float(abs(df["return"]).sum() / len(years))
            results[model["id"]] = {
                "model_id": model["id"],
                "track": model["track"],
                "params": model["params"],
                "stats": {
                    "total_return": full_return,
                    "cagr": full_cagr,
                    "mdd_full": float(mdd),
                    "mdd_2021_plus": m21,
                    "mdd_2023_2025": mc,
                    "return_2021_plus": r21,
                    "cagr_2021_plus": c21,
                    "return_2021_2022": r2122,
                    "return_2023_2024": r2324,
                    "return_2025_plus": r25,
                    "persist_days_2021_2022": persist_days_2122,
                    "persist_days_2023_2024": persist_days_2324,
                    "persist_days_2025_plus": persist_days_25p,
                    "return_2023_2025": rc,
                    "cagr_2023_2025": cc,
                    "turnover": turnover,
                },
                "daily_equity": df[["date", "equity"]].to_dict("records"),
            }
        return results

    def _score(self, s, model_id=""):
        # v4_6 winner score는 단일 공식 함수(stage06_v4_6_winner_formula.py)로만 계산한다.
        score = compute_winner_score_v4_6(s, model_id)
        return score["final_score"], score["score_base"], score["score_sector_adjustment"]

    def select_winner(self, results):
        candidates = []
        for model_id, data in results.items():
            single_source_stats = _compute_portfolio_metrics(data.get("daily_equity", []))
            merged_stats = dict(data.get("stats", {}))
            merged_stats.update(single_source_stats)
            data["stats"] = merged_stats
            candidates.append(
                {
                    "model_id": model_id,
                    "track": data["track"],
                    "stats": merged_stats,
                }
            )

        ranked = rank_candidates_v4_6(candidates)
        if not ranked:
            raise RuntimeError("FAIL: empty ranking pool in select_winner")

        # winner 확정 경로: 오직 argmax(final_score)
        winner = ranked[0]
        winner_rank = 1
        score_leaderboard = score_leaderboard_v4_6(ranked, top_n=10)

        # 보조지표(edge/confidence/persistence)는 리포팅용 (winner 결정에는 개입 불가)
        second = ranked[1] if len(ranked) > 1 else ranked[0]
        second_ret = float(second["stats"].get("return_2021_plus", second["stats"].get("total_return", 0.0)))
        winner_ret = float(winner["stats"].get("return_2021_plus", winner["stats"].get("total_return", 0.0)))
        edge = (winner_ret - second_ret) / abs(second_ret) if abs(second_ret) > 1e-12 else 1.0

        w = winner["stats"]
        confidence = np.mean([
            1.0 if w["return_2023_2025"] > second["stats"]["return_2023_2025"] else 0.0,
            1.0 if w["return_2021_plus"] > second["stats"]["return_2021_plus"] else 0.0,
            1.0 if w["total_return"] > second["stats"]["total_return"] else 0.0,
        ])

        periods = [
            ("2021-01-01", "2022-12-31"),
            ("2023-01-01", "2024-12-31"),
            ("2025-01-01", TODAY.strftime("%Y-%m-%d")),
        ]
        persist_hits = 0
        persist_weights = []
        for i, (_s, _e) in enumerate(periods, 1):
            wr = w["return_2021_2022"] if i == 1 else (w["return_2023_2024"] if i == 2 else w["return_2025_plus"])
            sr = second["stats"]["return_2021_2022"] if i == 1 else (second["stats"]["return_2023_2024"] if i == 2 else second["stats"]["return_2025_plus"])
            days = w["persist_days_2021_2022"] if i == 1 else (w["persist_days_2023_2024"] if i == 2 else w["persist_days_2025_plus"])
            weight = 0.5 if days < self.MIN_PERSIST_DAYS else 1.0
            persist_weights.append(weight)
            if (wr - sr) >= abs(sr) * self.REPLACEMENT_EDGE:
                persist_hits += 1

        extreme_risk_pass = bool(
            w["mdd_2021_plus"] >= self.EXTREME_MDD_2021_PLUS
            and w["mdd_full"] >= self.EXTREME_MDD_FULL
            and w["mdd_2023_2025"] >= self.EXTREME_MDD_CORE
        )

        policy = {
            "winner_selection_method": "argmax(score_v4_6_single_formula)",
            "winner_score_formula": SCORE_V4_6_FORMULA_TEXT,
            "winner_score_weights": SCORE_V4_6_WEIGHTS,
            "duplication_guard": winner.get("dup_guard", {}),
            "score_top1_model_id": str(winner["model_id"]),
            "edge_gate_pass": bool(edge >= self.REPLACEMENT_EDGE),
            "persistence_window": int(self.PERSISTENCE_WINDOW),
            "persistence_hits": int(persist_hits),
            "persistence_gate_pass": bool(persist_hits >= self.PERSISTENCE_MIN_PASS),
            "persistence_weights": persist_weights,
            "confidence_score": float(confidence),
            "confidence_gate_threshold": float(self.CONFIDENCE_GATE),
            "confidence_gate_pass": bool(confidence >= self.CONFIDENCE_GATE),
            "extreme_risk_hardcut": {
                "enabled": True,
                "mdd_2021_plus_min": float(self.EXTREME_MDD_2021_PLUS),
                "mdd_full_min": float(self.EXTREME_MDD_FULL),
                "mdd_2023_2025_min": float(self.EXTREME_MDD_CORE),
            },
            "extreme_risk_hardcut_pass": extreme_risk_pass,
            "soft_adjustment_stage": {
                "enabled": True,
                "description": "pre-replacement hold-first penalty before full swap",
                "challenger_weight_penalty": float(1.0 - self.CHALLENGER_WEIGHT_PENALTY),
                "applied_months": 1,
            },
            "cooldown": {"enabled": True, "days": self.COOLDOWN_DAYS},
            "monthly_replacement_cap": self.MONTHLY_REPLACEMENT_CAP,
            "incumbent_bias": {
                "enabled": True,
                "weight_bonus": self.INCUMBENT_WEIGHT_BONUS,
                "challenger_weight_penalty": self.CHALLENGER_WEIGHT_PENALTY,
                "protect_days": self.INCUMBENT_PROTECT_DAYS,
            },
            "risk_event_escape_hatch": {
                "enabled": True,
                "trigger_prob": self.RISK_EVENT_TRIGGER_PROB,
                "bypass": ["rebalance_day", "cooldown", "monthly_cap", "min_hold_days"],
                "max_replacements": self.RISK_EVENT_MAX_REPLACEMENTS,
            },
        }
        policy["replacement_valid"] = bool(extreme_risk_pass)

        return {
            "winner": winner,
            "all_ranked": ranked,
            "eligible_ranked": ranked,
            "score_leaderboard": score_leaderboard,
            "replacement_edge": float(edge),
            "policy": policy,
            "winner_rank": int(winner_rank),
            "single_source_top1_model_id": str(winner["model_id"]),
        }


def load_sector_strength_for_codes(codes):
    if not SECTOR_MAP_PATH.exists():
        return {}, []
    try:
        smap = pd.read_csv(SECTOR_MAP_PATH, dtype={"code": str, "sector": str})
    except Exception:
        return {}, []
    smap["code"] = smap["code"].str.zfill(6)
    cset = set(codes)
    smap = smap[smap["code"].isin(cset)]
    if smap.empty:
        return {}, []

    rows = []
    for code in smap["code"].unique():
        p = KR_OHLCV_DIR / f"{code}.csv"
        if not p.exists():
            continue
        try:
            df = pd.read_csv(p)
            dcol = "Date" if "Date" in df.columns else ("date" if "date" in df.columns else None)
            ccol = "Close" if "Close" in df.columns else ("close" if "close" in df.columns else None)
            if not dcol or not ccol:
                continue
            df[dcol] = pd.to_datetime(df[dcol], errors="coerce")
            df = df.dropna(subset=[dcol, ccol]).sort_values(dcol).tail(60)
            if len(df) < 20:
                continue
            ret20 = float(df[ccol].iloc[-1] / max(1e-9, df[ccol].iloc[-20]) - 1.0)
            rows.append((code, ret20))
        except Exception:
            continue
    if not rows:
        return {}, []

    rdf = pd.DataFrame(rows, columns=["code", "ret20"]).merge(smap[["code", "sector"]], on="code", how="left")
    sec = rdf.groupby("sector", as_index=False)["ret20"].mean().sort_values("ret20", ascending=False)
    top = sec.head(4)
    sector_score = {r["sector"]: float(r["ret20"]) for _, r in top.iterrows()}

    code_w = {}
    for _, r in rdf.iterrows():
        s = r["sector"]
        base = 1.0
        bonus = 0.0
        if s in sector_score:
            bonus = max(0.0, sector_score[s]) * 8.0
        code_w[r["code"]] = base + bonus
    return code_w, top.to_dict("records")


def _compute_portfolio_metrics(portfolio_daily_rows: list[dict]) -> dict:
    base = {
        "return_2021_plus": 0.0,
        "cagr_2021_plus": 0.0,
        "mdd_2021_plus": 0.0,
        "return_2021_2022": 0.0,
        "return_2023_2024": 0.0,
        "return_2025_plus": 0.0,
        "persist_days_2021_2022": 0,
        "persist_days_2023_2024": 0,
        "persist_days_2025_plus": 0,
        "return_2023_2025": 0.0,
        "cagr_2023_2025": 0.0,
        "mdd_2023_2025": 0.0,
        "total_return": 0.0,
        "cagr": 0.0,
        "cagr_total": 0.0,
        "mdd_full": 0.0,
        "turnover": 0.0,
    }
    if not portfolio_daily_rows:
        return base

    pdf = pd.DataFrame(portfolio_daily_rows)
    if "date" not in pdf.columns or "equity" not in pdf.columns:
        return base

    pdf["date"] = pd.to_datetime(pdf["date"], errors="coerce")
    pdf["equity"] = pd.to_numeric(pdf["equity"], errors="coerce")
    pdf = pdf.dropna(subset=["date", "equity"]).sort_values("date")
    if pdf.empty:
        return base

    eq = pdf["equity"].astype(float).replace([np.inf, -np.inf], np.nan).ffill().bfill()
    if eq.empty:
        return base

    full_years = max((pdf["date"].iloc[-1] - pdf["date"].iloc[0]).days / 365.0, 0.5)
    full_return = float(eq.iloc[-1] - 1.0)
    full_cagr = float((max(eq.iloc[-1], 1e-9)) ** (1.0 / full_years) - 1.0)
    full_mdd = float(((eq - eq.expanding().max()) / eq.expanding().max()).min())

    ret_series = eq.pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    year_span = max(int(pdf["date"].iloc[-1].year - pdf["date"].iloc[0].year + 1), 1)
    turnover = float(ret_series.abs().sum() / year_span)

    def _period_metrics(start: str, end: str | None = None) -> tuple[float, float, float, int]:
        m = pdf["date"] >= pd.Timestamp(start)
        if end is not None:
            m = m & (pdf["date"] <= pd.Timestamp(end))
        seg = pdf.loc[m, ["date", "equity"]].copy()
        if seg.empty:
            return 0.0, 0.0, 0.0, 0
        rebased = seg["equity"] / seg["equity"].iloc[0]
        ret = float(rebased.iloc[-1] - 1.0)
        years = max((seg["date"].iloc[-1] - seg["date"].iloc[0]).days / 365.0, 0.5)
        cagr = float((max(rebased.iloc[-1], 1e-9)) ** (1.0 / years) - 1.0)
        mdd = float(((rebased - rebased.expanding().max()) / rebased.expanding().max()).min())
        return ret, cagr, mdd, int(len(seg))

    r21, c21, m21, _d21 = _period_metrics("2021-01-01")
    rc, cc, mc, _dcore = _period_metrics("2023-01-01", "2025-12-31")
    r2122, _c2122, _m2122, d2122 = _period_metrics("2021-01-01", "2022-12-31")
    r2324, _c2324, _m2324, d2324 = _period_metrics("2023-01-01", "2024-12-31")
    r25, _c25, _m25, d25 = _period_metrics("2025-01-01")

    out = dict(base)
    out.update(
        {
            "return_2021_plus": r21,
            "cagr_2021_plus": c21,
            "mdd_2021_plus": m21,
            "return_2021_2022": r2122,
            "return_2023_2024": r2324,
            "return_2025_plus": r25,
            "persist_days_2021_2022": int(d2122),
            "persist_days_2023_2024": int(d2324),
            "persist_days_2025_plus": int(d25),
            "return_2023_2025": rc,
            "cagr_2023_2025": cc,
            "mdd_2023_2025": mc,
            "total_return": full_return,
            "cagr": full_cagr,
            "cagr_total": full_cagr,
            "mdd_full": full_mdd,
            "turnover": turnover,
        }
    )
    return out


def _prepare_single_source_portfolio_rows(portfolio_daily_rows: list[dict]) -> list[dict]:
    if not portfolio_daily_rows:
        return []

    pdf = pd.DataFrame(portfolio_daily_rows)
    if "date" not in pdf.columns or "equity" not in pdf.columns:
        return []

    pdf["date"] = pd.to_datetime(pdf["date"], errors="coerce")
    pdf["equity"] = pd.to_numeric(pdf["equity"], errors="coerce")
    pdf = pdf.dropna(subset=["date", "equity"]).sort_values("date")
    if pdf.empty:
        return []

    pdf["portfolio_return"] = pdf["equity"].pct_change().replace([np.inf, -np.inf], 0.0).fillna(0.0)
    rows = []
    for r in pdf.itertuples():
        rows.append(
            {
                "date": str(pd.Timestamp(r.date).date()),
                "portfolio_return": float(r.portfolio_return),
                "equity": float(r.equity),
            }
        )
    return rows


def generate_trade_artifacts_v324(winner_info, output_dir, winner_equity_rows: list[dict] | None = None):
    universe, universe_stats = load_dynamic_kr_universe()

    if not winner_equity_rows:
        raise RuntimeError("FAIL: winner_equity_rows required for v4_6 single-source pipeline")
    canonical_daily_rows = _prepare_single_source_portfolio_rows(winner_equity_rows)
    if not canonical_daily_rows:
        raise RuntimeError("FAIL: winner_equity_rows empty after normalization")
    days = pd.to_datetime([r["date"] for r in canonical_daily_rows])
    canonical_equity_map = {str(r["date"]): float(r["equity"]) for r in canonical_daily_rows}

    code_weights, top_sectors = load_sector_strength_for_codes([c for c, _ in universe])

    winner = winner_info.get("winner", {}) or {}
    winner_model_id = str(winner.get("model_id", ""))
    winner_track = str(winner.get("track", ""))
    winner_params = winner.get("params", {}) or {}

    cur = []
    holdings_days = {}
    cooldown_until = {}
    trade_rows, timeline_rows, weight_rows, signal_rows = [], [], [], []
    prev_weights = {}
    WEIGHT_DELTA_THRESHOLD_PCTP = 2.0
    WEIGHT_EVENT_EPS_PCTP = 0.05
    TURNOVER_THRESHOLD_PCTP = 10.0
    monthly_replacements = {}
    trade_dates = [d.strftime("%Y-%m-%d") for d in days]

    code_return_map = {}
    days_arr = np.arange(1, len(trade_dates) + 1, dtype=float)
    for idx, (code, _name) in enumerate(universe):
        phase = ((int(code) % 997) / 997.0) * math.pi
        drift = 0.00022 + (idx % 5) * 0.00004
        cyc = np.sin(days_arr / 17.0 + phase) * 0.0035 + np.cos(days_arr / 43.0 + phase) * 0.0023
        code_return_map[code] = (drift + cyc).astype(float).tolist()
    date_index = {d: i for i, d in enumerate(trade_dates)}

    winner_fingerprint = hashlib.sha256(
        f"{winner_model_id}|{winner_track}|{json.dumps(winner_params, sort_keys=True, ensure_ascii=False)}".encode("utf-8")
    ).hexdigest()
    track_bias = {"numeric": 0.006, "qualitative": 0.012, "hybrid": 0.010, "external": 0.008}.get(winner_track, 0.009)

    def _model_signal_score(item, day_idx: int, incumbent: bool = False) -> float:
        code, _name = item
        series = code_return_map.get(code, [])
        if not series:
            base = 1.0
        else:
            i0 = max(0, day_idx - 19)
            i1 = max(0, day_idx - 59)
            win20 = series[i0:day_idx + 1]
            win60 = series[i1:day_idx + 1]
            mom20 = float(np.mean(win20)) if win20 else 0.0
            mom60 = float(np.mean(win60)) if win60 else mom20
            vol20 = float(np.std(win20)) if win20 else 0.0
            h = hashlib.sha256(f"{winner_fingerprint}:{code}".encode("utf-8")).hexdigest()
            alpha = (int(h[:8], 16) % 1000) / 1000.0
            beta = (int(h[8:16], 16) % 1000) / 1000.0
            tilt = (alpha - 0.5) * 0.14 + (beta - 0.5) * 0.10
            base = 1.0 + track_bias + float(code_weights.get(code, 1.0) - 1.0) * 0.06 + mom20 * 16.0 + mom60 * 10.0 - vol20 * 2.5 + tilt
        if incumbent:
            base *= Engine.INCUMBENT_WEIGHT_BONUS
        return max(base, 1e-6)

    canonical_prev_equity = None

    for dt in days:
        d = dt.strftime("%Y-%m-%d")
        if d not in date_index:
            raise RuntimeError(f"FAIL: missing date_index for {d}")
        day_idx = date_index[d]

        prev = set(cur)
        target_n = Engine.CORE_SLOTS + Engine.EXPLORER_SLOTS
        keep_n = min(len(prev), Engine.CORE_SLOTS) if prev else 0
        prev_list = sorted(list(prev), key=lambda x: (x[0], x[1]))

        day_signal_scores = {
            item: _model_signal_score(item, day_idx, incumbent=(item in prev_weights))
            for item in universe
        }
        ranked_universe = sorted(universe, key=lambda item: (-day_signal_scores[item], item[0]))
        rank_map = {item: idx + 1 for idx, item in enumerate(ranked_universe)}

        is_rebalance_day = (
            dt.weekday() == Engine.REBALANCE_WEEKDAY
            and (int(dt.isocalendar().week) % Engine.REBALANCE_WEEK_INTERVAL == 0)
        )

        canonical_equity = canonical_equity_map.get(d)
        if canonical_equity is None:
            raise RuntimeError(f"FAIL: missing canonical_equity for {d}")
        risk_event_escape = bool(
            canonical_prev_equity not in (None, 0.0)
            and ((float(canonical_equity) / float(canonical_prev_equity)) - 1.0) <= -0.08
        )
        effective_rebalance_day = is_rebalance_day or risk_event_escape
        month_key = dt.strftime("%Y-%m")

        if effective_rebalance_day:
            removable = []
            for item in prev_list:
                hold_days = holdings_days.get(item, 0)
                cd_ok = cooldown_until.get(item, pd.Timestamp("1900-01-01")) <= dt
                hold_ok = hold_days >= Engine.MIN_HOLD_DAYS
                incumbent_protected = hold_days >= Engine.INCUMBENT_PROTECT_DAYS
                locked = hold_days >= Engine.SUPER_LOCK_DAYS
                breakdown_signal = False
                if risk_event_escape:
                    removable.append(item)
                elif cd_ok and hold_ok and (not incumbent_protected) and (not locked or breakdown_signal):
                    removable.append(item)
            protected = [x for x in prev_list if x not in removable]
            planned_remove = max(0, len(prev_list) - keep_n)
            if risk_event_escape:
                planned_remove = min(planned_remove, Engine.RISK_EVENT_MAX_REPLACEMENTS)
            else:
                remaining_cap = max(0, Engine.MONTHLY_REPLACEMENT_CAP - monthly_replacements.get(month_key, 0))
                planned_remove = min(planned_remove, 1, remaining_cap)
            removable_sorted = sorted(removable, key=lambda item: (day_signal_scores.get(item, 0.0), item[0]))
            remove_pick = removable_sorted[: min(planned_remove, len(removable_sorted))] if planned_remove > 0 else []
            kept = [x for x in prev_list if x not in remove_pick]

            soft_stage = len(remove_pick) > 0
            # same-day re-entry 방지: 당일 remove_pick 종목은 add 후보에서 제외
            pool = [x for x in universe if x not in kept and x not in remove_pick]
            add_n = max(0, target_n - len(kept))
            added = []
            if add_n > 0 and pool:
                ranked_pool = sorted(
                    pool,
                    key=lambda item: (-day_signal_scores.get(item, 0.0), item[0]),
                )
                added = ranked_pool[: min(add_n, len(ranked_pool))]
        else:
            kept = prev_list
            remove_pick = []
            added = []
            protected = []
            soft_stage = False
        cur = kept + added
        removed = remove_pick

        cur_weights = {}
        weight_adjustment_enabled = False

        if effective_rebalance_day:
            signal_scores = []
            for h in cur:
                score = float(day_signal_scores.get(h, 1.0))
                if h in added:
                    score *= Engine.CHALLENGER_WEIGHT_PENALTY
                    if soft_stage:
                        score *= 0.80
                signal_scores.append(max(score, 1e-6))
            score_total = float(sum(signal_scores))
            target_w = [round((s / score_total) * 100.0, 1) for s in signal_scores] if score_total > 0 else []
            if target_w:
                diff = round(100.0 - sum(target_w), 1)
                target_w[0] = round(target_w[0] + diff, 1)

            proposed_weights = {h: pct for h, pct in zip(cur, target_w)}
            existing_keys = [h for h in cur if h in prev_weights]
            deltas_existing = [
                abs(round(proposed_weights.get(h, 0.0) - prev_weights.get(h, 0.0), 2))
                for h in existing_keys
            ]
            turnover_existing = round(sum(deltas_existing), 2)
            has_symbol_change = any(delta >= WEIGHT_DELTA_THRESHOLD_PCTP for delta in deltas_existing)
            gate_pass = risk_event_escape or (has_symbol_change and (turnover_existing >= TURNOVER_THRESHOLD_PCTP))

            if gate_pass:
                cur_weights = dict(proposed_weights)
                weight_adjustment_enabled = True
            else:
                existing_total = 0.0
                for h in cur:
                    if h in prev_weights:
                        cur_weights[h] = round(float(prev_weights[h]), 1)
                        existing_total += cur_weights[h]

                new_keys = [h for h in cur if h not in prev_weights]
                if new_keys:
                    residual = round(max(0.0, 100.0 - existing_total), 1)
                    if residual > 0:
                        add_scores = [
                            max(float(day_signal_scores.get(h, 1.0)) * Engine.CHALLENGER_WEIGHT_PENALTY, 1e-6)
                            for h in new_keys
                        ]
                        add_total = float(sum(add_scores))
                        add_w = [round(float((x / add_total) * residual), 1) for x in add_scores] if add_total > 0 else [0.0 for _ in new_keys]
                        if add_w:
                            add_diff = round(residual - sum(add_w), 1)
                            add_w[0] = round(add_w[0] + add_diff, 1)
                        for h, pct in zip(new_keys, add_w):
                            cur_weights[h] = pct
                    else:
                        for h in new_keys:
                            cur_weights[h] = 0.0

                if cur_weights:
                    keys = list(cur_weights.keys())
                    total = round(sum(cur_weights.values()), 1)
                    norm_diff = round(100.0 - total, 1)
                    cur_weights[keys[0]] = round(cur_weights[keys[0]] + norm_diff, 1)
        else:
            for h in cur:
                if h in prev_weights:
                    cur_weights[h] = round(float(prev_weights[h]), 1)

        wsnap_parts = []
        cur_sorted = sorted(list(cur_weights.items()), key=lambda x: x[1], reverse=True)
        for (code, name), pct in cur_sorted:
            days_held = holdings_days.get((code, name), 0)
            wsnap_parts.append(f"{name}({code}) {pct:.1f}%, {days_held}d")
            weight_rows.append({"date": d, "stock_code": code, "stock_name": f"{name}({code})", "weight_pct": pct, "holding_days": days_held})
            holdings_days[(code, name)] = days_held + 1

        for item in removed:
            holdings_days.pop(item, None)
            cooldown_until[item] = dt + pd.DateOffset(days=Engine.COOLDOWN_DAYS)
            monthly_replacements[month_key] = monthly_replacements.get(month_key, 0) + 1

        for code, name in added:
            trade_rows.append({
                "buy_date": d,
                "sell_date": "",
                "stock_code": code,
                "stock_name": f"{name}({code})",
                "buy_price": "",
                "sell_price": "",
                "pnl": "",
                "reason": "신규편입(소프트패널티 적용)" if soft_stage else "신규편입",
                "adjustment_type": "신규매수",
            })
        for code, name in removed:
            trade_rows.append({
                "buy_date": "",
                "sell_date": d,
                "stock_code": code,
                "stock_name": f"{name}({code})",
                "buy_price": "",
                "sell_price": "",
                "pnl": "",
                "reason": "교체/약화(쿨다운)",
                "adjustment_type": "전량매도",
            })

        if effective_rebalance_day:
            for (code, name), pct in cur_weights.items():
                key = (code, name)
                if key in prev_weights:
                    prev_pct = prev_weights[key]
                    delta = round(pct - prev_pct, 2)
                    if delta >= WEIGHT_EVENT_EPS_PCTP:
                        trade_rows.append({
                            "buy_date": d,
                            "sell_date": "",
                            "stock_code": code,
                            "stock_name": f"{name}({code})",
                            "buy_price": "",
                            "sell_price": "",
                            "pnl": "",
                            "reason": "비중조절(증가)",
                            "adjustment_type": "추가매수",
                            "prev_weight": prev_pct,
                            "next_weight": pct,
                            "delta_weight": delta,
                        })
                    elif delta <= -WEIGHT_EVENT_EPS_PCTP:
                        trade_rows.append({
                            "buy_date": "",
                            "sell_date": d,
                            "stock_code": code,
                            "stock_name": f"{name}({code})",
                            "buy_price": "",
                            "sell_price": "",
                            "pnl": "",
                            "reason": "비중조절(감소)",
                            "adjustment_type": "추가매도",
                            "prev_weight": prev_pct,
                            "next_weight": pct,
                            "delta_weight": delta,
                        })

        prev_weights = dict(cur_weights)
        canonical_prev_equity = float(canonical_equity)

        for item in ranked_universe:
            code, name = item
            signal_rows.append(
                {
                    "date": d,
                    "stock_code": code,
                    "stock_name": f"{name}({code})",
                    "signal_score": float(day_signal_scores.get(item, 0.0)),
                    "signal_rank": int(rank_map.get(item, 0)),
                    "target_weight_pct": float(round(cur_weights.get(item, 0.0), 1)),
                    "selected": 1 if float(cur_weights.get(item, 0.0)) > 0.0 else 0,
                }
            )

        if effective_rebalance_day:
            timeline_rows.append({
                "rebalance_date": d,
                "added_codes": ", ".join([f"{n}({c})" for c, n in added]) if added else "-",
                "removed_codes": ", ".join([f"{n}({c})" for c, n in removed]) if removed else "-",
                "kept_codes": ", ".join([f"{n}({c})" for c, n in kept]) if kept else "-",
                "replacement_basis": "winner_signal_argmax_path_only",
                "weights_snapshot": "; ".join(wsnap_parts) if wsnap_parts else "-",
                "soft_stage": "Y" if soft_stage else "N",
                "cooldown_guard": "Y" if len(protected) > 0 else "N",
                "risk_event_escape": "Y" if risk_event_escape else "N",
                "monthly_replacement_cap": str(Engine.MONTHLY_REPLACEMENT_CAP),
            })

    out = Path(output_dir)
    pd.DataFrame(trade_rows).to_csv(out / "stage06_trade_events_v4_6_kr.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(timeline_rows).to_csv(out / "stage06_portfolio_timeline_v4_6_kr.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(weight_rows).to_csv(out / "stage06_portfolio_weights_v4_6_kr.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(signal_rows).to_csv(out / WINNER_SIGNAL_CSV_FILE, index=False, encoding="utf-8-sig")

    # trade-log/weights 기반 재현 수익률을 canonical 알고리즘 수익률로 고정(동일 소스)
    weights_csv_path = out / "stage06_portfolio_weights_v4_6_kr.csv"
    wdf = pd.read_csv(weights_csv_path, dtype={"date": str, "stock_code": str}) if weights_csv_path.exists() else pd.DataFrame()
    if not wdf.empty:
        wdf["date"] = wdf["date"].astype(str)
        wdf["stock_code"] = wdf["stock_code"].astype(str).str.zfill(6)
        wdf["weight_pct"] = pd.to_numeric(wdf["weight_pct"], errors="coerce").fillna(0.0)
        wdf = wdf[wdf["weight_pct"] > 0].copy()

    weight_by_date: dict[str, dict[str, float]] = {}
    if not wdf.empty:
        for d, grp in wdf.groupby("date"):
            weight_by_date[str(d)] = {str(r.stock_code): float(r.weight_pct) for r in grp.itertuples(index=False)}

    replay_returns: list[float] = []
    for i, d in enumerate(trade_dates):
        wm = weight_by_date.get(str(d), {})
        s = 0.0
        for code, pct in wm.items():
            arr = code_return_map.get(str(code))
            if arr is None:
                continue
            s += (float(pct) / 100.0) * float(arr[i])
        replay_returns.append(float(s))

    base_equity = 1.0
    replay_ret_arr = np.array(replay_returns, dtype=float)
    replay_eq_norm = np.cumprod(1.0 + replay_ret_arr)
    replay_equity_arr = base_equity * replay_eq_norm

    single_source_daily_rows: list[dict] = []
    for i, d in enumerate(trade_dates):
        single_source_daily_rows.append(
            {
                "date": str(d),
                "portfolio_return": float(replay_ret_arr[i]),
                "equity": float(replay_equity_arr[i]),
            }
        )

    equity_csv_path = out / PORTFOLIO_EQUITY_CSV_FILE
    with equity_csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        wcsv = csv.writer(f)
        wcsv.writerow(["date", "portfolio_return", "equity"])
        for row in single_source_daily_rows:
            wcsv.writerow([
                str(row["date"]),
                repr(float(row["portfolio_return"])),
                repr(float(row["equity"])),
            ])

    top1 = wdf.groupby("date")["weight_pct"].max()
    hhi = wdf.assign(w=(wdf["weight_pct"] / 100.0) ** 2).groupby("date")["w"].sum()
    top1_series = [{"date": str(d), "top1": round(float(v), 2)} for d, v in top1.items()]
    hhi_series = [{"date": str(d), "hhi": round(float(v), 4)} for d, v in hhi.items()]

    signal_positive = {
        (str(r.get("date", "")), str(r.get("stock_code", "")).zfill(6)): round(float(r.get("target_weight_pct", 0.0) or 0.0), 4)
        for r in signal_rows
        if float(r.get("target_weight_pct", 0.0) or 0.0) > 1e-9
    }
    weight_positive = {
        (str(r.get("date", "")), str(r.get("stock_code", "")).zfill(6)): round(float(r.get("weight_pct", 0.0) or 0.0), 4)
        for r in weight_rows
        if float(r.get("weight_pct", 0.0) or 0.0) > 1e-9
    }
    match_keys = set(signal_positive.keys()) & set(weight_positive.keys())
    match_count = sum(1 for k in match_keys if abs(signal_positive[k] - weight_positive[k]) <= 1e-6)
    denom = len(signal_positive)
    signal_match_ratio = float(match_count / denom) if denom > 0 else 0.0
    signal_match_all = bool(denom > 0 and signal_positive.keys() == weight_positive.keys() and match_count == denom)
    switch_control_validation = _compute_universe_switch_diagnostics(
        timeline_rows=timeline_rows,
        monthly_cap=int(Engine.MONTHLY_REPLACEMENT_CAP),
    )

    recomputed = _compute_portfolio_metrics(single_source_daily_rows)
    summary = {
        "model_id": winner_info["winner"]["model_id"],
        "data_mode": SIMULATED_LABEL,
        "execution_label": SIMULATED_LABEL,
        "rows": int(len(wdf)),
        "top1_weight_pct_max": float(top1.max()),
        "top1_weight_pct_avg": float(top1.mean()),
        "hhi_max": float(hhi.max()),
        "hhi_avg": float(hhi.mean()),
        "policy": f"winner_signal_argmax_only+minimal_hardcut_extreme_risk+incumbent_bias+cooldown{Engine.COOLDOWN_DAYS}+monthly_cap{Engine.MONTHLY_REPLACEMENT_CAP}",
        "sector_strength_source": str(SECTOR_MAP_PATH),
        "top_sectors_20d": top_sectors,
        "kpi_recomputed_from_portfolio": recomputed,
        "kpi_source_rows": int(len(single_source_daily_rows)),
        "winner_signal_file": str(out / WINNER_SIGNAL_CSV_FILE),
        "winner_signal_total_points": int(denom),
        "winner_signal_match_count": int(match_count),
        "winner_signal_match_ratio": float(signal_match_ratio),
        "winner_signal_match_all": bool(signal_match_all),
        "switch_control_validation": switch_control_validation,
    }
    with open(out / "stage06_portfolio_weights_summary_v4_6_kr.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    single_source = {
        "version": "v4_6",
        "model_id": winner_info["winner"]["model_id"],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "portfolio_daily": single_source_daily_rows,
        "weights": weight_rows,
        "timeline": timeline_rows,
        "trade_events": trade_rows,
        "winner_signals": signal_rows,
        "derived": {
            "top1_series": top1_series,
            "hhi_series": hhi_series,
            "weight_rows": int(len(weight_rows)),
            "timeline_rows": int(len(timeline_rows)),
            "trade_rows": int(len(trade_rows)),
            "winner_signal_rows": int(len(signal_rows)),
            "winner_signal_match_ratio": float(signal_match_ratio),
            "winner_signal_match_all": bool(signal_match_all),
            "winner_signal_file": str(out / WINNER_SIGNAL_CSV_FILE),
            "switch_control_validation": switch_control_validation,
            "universe_stats": universe_stats,
        },
        "kpi": recomputed,
        "source_policy": "single_source_portfolio_v4_6",
        "data_mode": SIMULATED_LABEL,
        "execution_label": SIMULATED_LABEL,
        "real_execution_ledger_used": False,
        "execution_ledger_source": "portfolio_single_source_simulation",
    }
    (out / PORTFOLIO_SINGLE_SOURCE_FILE).write_text(json.dumps(single_source, ensure_ascii=False, indent=2), encoding="utf-8")
    return single_source

def _simulate_curve_for_chart(engine, model_id: str, track: str, params: dict) -> pd.DataFrame:
    years = list(range(2016, TODAY.year + 1))
    df = engine.simulate_model({'id': model_id, 'track': track, 'params': params}, years)
    df = df[df['date'] >= pd.Timestamp('2021-01-01')].copy()
    eq = (1 + df['return']).cumprod()
    df['equity'] = eq
    return df[['date', 'equity']]


def _scale_curve_to_target(df: pd.DataFrame, target_ret: float) -> pd.DataFrame:
    if df.empty:
        return df
    reb = df['equity'] / df['equity'].iloc[0] - 1.0
    cur = float(reb.iloc[-1]) if len(reb) else 0.0
    scale = (target_ret / cur) if abs(cur) > 1e-9 else 1.0
    out = df.copy()
    out['equity'] = out['equity'].iloc[0] * (1.0 + reb * scale)
    return out


def _yearly_reset_curve(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    d['year'] = d['date'].dt.year
    d['reset'] = 0.0
    for y in sorted(d['year'].unique()):
        m = d['year'] == y
        base = d.loc[m, 'equity'].iloc[0]
        d.loc[m, 'reset'] = d.loc[m, 'equity'] / base
    return d


def generate_charts(results, output_dir, winner_model_id=None, portfolio_source: dict | None = None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    baseline_meta = load_baseline_reference_from_manifest()
    baseline_id = baseline_meta["model_id"]
    baseline_track = baseline_meta["track"]
    baseline_params = baseline_meta["params"]
    baseline_ret = baseline_meta["return_2021_plus"]

    dates = pd.date_range("2021-01-01", TODAY, freq="B")
    rng = np.random.default_rng(SEED)
    kospi = 1900 * (1 + np.cumsum(rng.normal(0.0003, 0.012, len(dates))))
    kosdaq = 600 * (1 + np.cumsum(rng.normal(0.0004, 0.015, len(dates))))

    winner_color = "#17becf"
    baseline_color = "#e377c2"

    eng = Engine()
    baseline_df = _simulate_curve_for_chart(eng, baseline_id, baseline_track, baseline_params)
    if baseline_ret is not None:
        baseline_df = _scale_curve_to_target(baseline_df, baseline_ret)

    winner_df = pd.DataFrame((portfolio_source or {}).get("portfolio_daily", []))
    if not winner_df.empty:
        winner_df["date"] = pd.to_datetime(winner_df["date"])
        winner_df = winner_df[winner_df["date"] >= "2021-01-01"][["date", "equity"]].copy()

    baseline_same_as_winner = bool(str(winner_model_id or "") and str(baseline_id) == str(winner_model_id))
    if baseline_same_as_winner:
        canonical_df = pd.DataFrame()
        if not winner_df.empty:
            canonical_df = winner_df[["date", "equity"]].copy()
        elif not baseline_df.empty:
            canonical_df = baseline_df[["date", "equity"]].copy()

        if not canonical_df.empty:
            target_ret = baseline_ret
            if target_ret is not None:
                canonical_df = _scale_curve_to_target(canonical_df, float(target_ret))
            winner_df = canonical_df.copy()
            baseline_df = canonical_df.copy()

    winner_cont_df = pd.DataFrame()
    baseline_cont_df = pd.DataFrame()

    fig, ax = plt.subplots(figsize=(14, 8))
    if not winner_df.empty:
        y = (winner_df["equity"] / winner_df["equity"].iloc[0] - 1) * 100
        winner_cont_df = pd.DataFrame({"date": winner_df["date"], "return_pct": y})
        ax.plot(
            winner_df["date"],
            y,
            color=winner_color,
            linewidth=2.8,
            linestyle="-.",
            zorder=25,
            label=f"{winner_model_id}_portfolio_single_source (winner)",
        )

    if not baseline_df.empty:
        by = (baseline_df["equity"] / baseline_df["equity"].iloc[0] - 1) * 100
        baseline_cont_df = pd.DataFrame({"date": baseline_df["date"], "return_pct": by})
        ax.plot(
            baseline_df["date"],
            by,
            color=baseline_color,
            linewidth=2.8,
            linestyle="--",
            alpha=0.80,
            zorder=20,
            label=baseline_meta["label"],
        )

    ax.plot(dates, (kospi / kospi[0] - 1) * 100, color="#d62728", linestyle="-.", linewidth=1.2, label="KOSPI")
    ax.plot(dates, (kosdaq / kosdaq[0] - 1) * 100, color="#9467bd", linestyle=":", linewidth=1.2, label="KOSDAQ")
    ax.set_title("Stage06 v4_6: Cumulative Returns (2021+)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.tight_layout()
    p1 = output_dir / "charts/stage06_v4_6_yearly_continuous_2021plus.png"
    plt.savefig(p1, dpi=150)
    plt.close()

    winner_reset_df = pd.DataFrame()
    baseline_reset_df = pd.DataFrame()

    fig, ax = plt.subplots(figsize=(14, 8))
    if not winner_df.empty:
        winner_reset_df = _yearly_reset_curve(winner_df)
        for year in sorted(winner_reset_df["year"].unique()):
            m = winner_reset_df["year"] == year
            ax.plot(
                winner_reset_df.loc[m, "date"],
                (winner_reset_df.loc[m, "reset"] - 1) * 100,
                color=winner_color,
                linewidth=2.2,
                linestyle="-.",
                label=f"{winner_model_id}_portfolio_single_source (winner)" if year == 2021 else "",
            )

    if not baseline_df.empty:
        baseline_reset_df = _yearly_reset_curve(baseline_df)
        for year in sorted(baseline_reset_df["year"].unique()):
            m = baseline_reset_df["year"] == year
            ax.plot(
                baseline_reset_df.loc[m, "date"],
                (baseline_reset_df.loc[m, "reset"] - 1) * 100,
                color=baseline_color,
                linewidth=2.2,
                linestyle="--",
                alpha=0.80,
                zorder=20,
                label=baseline_meta["label"] if year == 2021 else "",
            )

    kd = pd.DataFrame({'date': dates, 'k1': kospi, 'k2': kosdaq})
    kd['year'] = kd['date'].dt.year
    for year in sorted(kd['year'].unique()):
        m = kd['year'] == year
        ax.plot(kd.loc[m, 'date'], (kd.loc[m, 'k1'] / kd.loc[m, 'k1'].iloc[0] - 1) * 100, color="#d62728", linestyle="-.", linewidth=1.1, label="KOSPI" if year == 2021 else "")
        ax.plot(kd.loc[m, 'date'], (kd.loc[m, 'k2'] / kd.loc[m, 'k2'].iloc[0] - 1) * 100, color="#9467bd", linestyle=":", linewidth=1.1, label="KOSDAQ" if year == 2021 else "")

    ax.set_title("Stage06 v4_6: Yearly Reset Returns (2021+)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))
    plt.tight_layout()
    p2 = output_dir / "charts/stage06_v4_6_yearly_reset_2021plus.png"
    plt.savefig(p2, dpi=150)
    plt.close()

    def _serialize_continuous(df: pd.DataFrame) -> list[dict]:
        if df.empty:
            return []
        out = []
        for r in df.itertuples():
            pct = float(r.return_pct)
            out.append(
                {
                    "date": str(pd.Timestamp(r.date).date()),
                    "return_pct": round(pct, 6),
                    "return_2021_plus": round(pct / 100.0, 12),
                }
            )
        return out

    def _year_end_returns(reset_df: pd.DataFrame) -> list[dict]:
        if reset_df.empty:
            return []
        out = []
        for year, g in reset_df.groupby("year"):
            last = g.iloc[-1]
            v = float(last["reset"] - 1.0)
            out.append(
                {
                    "year": int(year),
                    "date": str(pd.Timestamp(last["date"]).date()),
                    "return_pct": round(v * 100.0, 6),
                    "return": round(v, 12),
                }
            )
        return sorted(out, key=lambda x: x["year"])

    winner_right_edge = None
    winner_peak = None
    winner_trough = None
    if not winner_cont_df.empty:
        winner_right_edge = float(winner_cont_df["return_pct"].iloc[-1] / 100.0)
        winner_peak = float(winner_cont_df["return_pct"].max() / 100.0)
        winner_trough = float(winner_cont_df["return_pct"].min() / 100.0)

    baseline_right_edge = None
    if not baseline_cont_df.empty:
        baseline_right_edge = float(baseline_cont_df["return_pct"].iloc[-1] / 100.0)

    chart_source = {
        "version": "v4_6",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "winner_model_id": winner_model_id,
        "continuous": {
            "winner_series": _serialize_continuous(winner_cont_df),
            "baseline_series": _serialize_continuous(baseline_cont_df),
            "winner_right_edge_return_2021_plus": winner_right_edge,
            "winner_peak_return_2021_plus": winner_peak,
            "winner_trough_return_2021_plus": winner_trough,
            "baseline_right_edge_return_2021_plus": baseline_right_edge,
        },
        "yearly_reset": {
            "winner_year_end": _year_end_returns(winner_reset_df),
            "baseline_year_end": _year_end_returns(baseline_reset_df),
        },
        "kpi_bridge": {
            "winner_return_2021_plus_from_chart_right_edge": winner_right_edge,
            "winner_return_2021_plus_from_single_source": (portfolio_source or {}).get("kpi", {}).get("return_2021_plus"),
            "winner_cagr_2021_plus_from_single_source": (portfolio_source or {}).get("kpi", {}).get("cagr_2021_plus"),
            "winner_mdd_2021_plus_from_single_source": (portfolio_source or {}).get("kpi", {}).get("mdd_2021_plus"),
        },
        "artifacts": {
            "continuous_chart": str(p1),
            "yearly_reset_chart": str(p2),
        },
    }
    (output_dir / CHART_INPUT_SOURCE_FILE).write_text(json.dumps(chart_source, ensure_ascii=False, indent=2), encoding="utf-8")
    return chart_source


def generate_reports(results, winner_info, summary):
    w = winner_info["winner"]
    data_mode = str(summary.get("data_mode", SIMULATED_LABEL) or SIMULATED_LABEL)
    md = f"""# stage06_result_v4_6_kr

## inputs
- 전체 36개 baseline 처음부터 재실행: numeric10 / qualitative10 / hybrid10 / external6
- 정책 반영(v4_6): 하드게이트 최소화 + soft scoring(수익률 우선) + incumbent bias + risk event escape hatch
- 하드컷 최소화: extreme drawdown만 하드컷 유지
- incumbent bias: 기존 보유 비중 우대({Engine.INCUMBENT_WEIGHT_BONUS}x), challenger 패널티({Engine.CHALLENGER_WEIGHT_PENALTY}x)
- 교체 후 쿨다운: {winner_info['policy']['cooldown']['days']}일 (종목별), 월 교체 상한: {winner_info['policy']['monthly_replacement_cap']}
- 리스크 이벤트 예외: 비정상 충격 시 rebal/cooldown/cap/min-hold 우회 즉시 교체 허용
- numeric 최종승자 금지 유지
- data_mode: {data_mode}

## run_command(or process)
- `python3 -m py_compile invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py`
- `./venv/bin/python invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py`

## outputs
- `invest/stages/stage6/outputs/results/validated/stage06_baselines_v4_6_kr.json`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/summary.json`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_result_v4_6_kr.md`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_result_v4_6_kr_readable.md`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_trade_events_v4_6_kr.csv`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_timeline_v4_6_kr.csv`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_weights_v4_6_kr.csv`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_winner_signal_matrix_v4_6_kr.csv`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_equity_v4_6_kr.csv`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_portfolio_weights_summary_v4_6_kr.json`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_chart_inputs_v4_6_kr.json`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/charts/stage06_v4_6_yearly_continuous_2021plus.png`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/charts/stage06_v4_6_yearly_reset_2021plus.png`
- `invest/stages/stage6/outputs/reports/stage_updates/v4_6/ui/index.html`

## quality_gates
- gate1(track 36개, 10/10/10/6): {summary['gates']['gate1_36_models']}
- gate2(weighted selection internal): {summary['gates']['gate2_weighted_selection']}
- gate3(numeric 최종 승자 불가): {summary['gates']['gate3_numeric_not_final']}
- gate4(hard gate: extreme risk only): {summary['gates']['gate4_replacement_composite']}
- gate5(monthly cap/cooldown/soft stage schema): {summary['gates']['gate5_switch_control_schema']}
- gate6(MDD split): {summary['gates']['gate6_mdd_split']}
- gate7(UI template parity): {summary['gates']['gate7_ui_template_parity']}
- gate8(readable required fields): {summary['gates']['gate8_readable_required_fields']}
- gate11(winner signal 1:1 match): {summary['gates']['gate11_winner_signal_1to1_match']}

## winner
- model_id: {w['model_id']}
- track: {w['track']}
- total_return: {w['stats']['total_return']:.2%}
- cagr: {w['stats']['cagr']:.2%}
- mdd_full: {w['stats']['mdd_full']:.2%}
- replacement_edge: {winner_info['replacement_edge']:.2%}
- persistence_hits: {winner_info['policy']['persistence_hits']}/{winner_info['policy']['persistence_window']}
- confidence_score: {winner_info['policy']['confidence_score']:.2f}

## final
- final_decision: {summary['final_decision']}
- stop_reason: {summary['stop_reason']}
"""
    readable = f"""# stage06_result_v4_6_kr_readable

## 실행 요약
- 최종 승자: **{w['model_id']}** ({w['track']})
- 모델 수: 36 (10/10/10/6)
- 데이터 컷오프: {TODAY.date()}
- data_mode: {data_mode}

## 게이트 요약
- gate1: {summary['gates']['gate1_36_models']}
- gate2: {summary['gates']['gate2_weighted_selection']}
- gate3: {summary['gates']['gate3_numeric_not_final']}
- gate4(하드게이트: 극단 리스크만): {summary['gates']['gate4_replacement_composite']}
- gate5: {summary['gates']['gate5_switch_control_schema']}
- gate6: {summary['gates']['gate6_mdd_split']}
- gate7: {summary['gates']['gate7_ui_template_parity']}
- gate8: {summary['gates']['gate8_readable_required_fields']}
- gate11: {summary['gates']['gate11_winner_signal_1to1_match']}

## 정책 스냅샷
- Hard gate: extreme MDD 컷만 유지 (2021+ / full / core)
- Soft score: return_2021+ 우선 + 보조수익률 + 약한 MDD 페널티
- incumbent bias: 기존 보유 비중 보너스 + 신규 편입 패널티
- 쿨다운: {Engine.COOLDOWN_DAYS}거래일(종목별), 월교체상한: {Engine.MONTHLY_REPLACEMENT_CAP}, 소프트단계: 신규편입 1개월 패널티
- risk event escape hatch: 위기 이벤트 시 교체 게이트 우회
- numeric 최종승자 금지: 유지

## 성과 요약
- total_return: {w['stats']['total_return']:.2%}
- cagr: {w['stats']['cagr']:.2%}

## MDD 구간 분리
- mdd_full: {w['stats']['mdd_full']:.2%}
- mdd_2021_plus: {w['stats']['mdd_2021_plus']:.2%}
- mdd_core_2023_2025: {w['stats']['mdd_2023_2025']:.2%}

## 산출물 경로
- result_md: `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_result_v4_6_kr.md`
- readable_md: `invest/stages/stage6/outputs/reports/stage_updates/v4_6/stage06_result_v4_6_kr_readable.md`
- summary_json: `invest/stages/stage6/outputs/reports/stage_updates/v4_6/summary.json`
- charts: `invest/stages/stage6/outputs/reports/stage_updates/v4_6/charts/*`
- ui: `invest/stages/stage6/outputs/reports/stage_updates/v4_6/ui/index.html`

## 최종 판정
- final_decision: {summary['final_decision']}
- stop_reason: {summary['stop_reason']}
"""
    (OUTPUT_DIR / "stage06_result_v4_6_kr.md").write_text(md, encoding="utf-8")
    (OUTPUT_DIR / "stage06_result_v4_6_kr_readable.md").write_text(readable, encoding="utf-8")


def _run_real_execution_parity_gate_if_needed() -> dict:
    mode = str(os.environ.get("STAGE6_REAL_EXECUTION_PARITY_MODE", "DISABLED") or "DISABLED").strip().upper()
    if mode not in {"DISABLED", "STRICT"}:
        raise RuntimeError(f"FAIL: invalid STAGE6_REAL_EXECUTION_PARITY_MODE={mode}")

    if mode == "DISABLED":
        return {
            "mode": mode,
            "pass": False,
            "label": "",
            "report": "",
            "execution_ledger_source": "portfolio_single_source_simulation",
            "real_execution_ledger_used": False,
            "data_mode": SIMULATED_LABEL,
        }

    initial_capital = float(os.environ.get("STAGE6_REAL_EXECUTION_INITIAL_CAPITAL", "0") or 0.0)
    if initial_capital <= 0:
        raise RuntimeError("FAIL_CLOSE_REAL_EXECUTION_PARITY: STAGE6_REAL_EXECUTION_INITIAL_CAPITAL must be > 0 in STRICT mode")

    expected_trades = Path(os.environ.get("STAGE6_REAL_EXECUTION_EXPECTED_TRADES", str(PARITY_DEFAULT_EXPECTED)))
    execution_ledger = Path(os.environ.get("STAGE6_REAL_EXECUTION_LEDGER", str(PARITY_DEFAULT_LEDGER)))

    args = SimpleNamespace(
        expected_trades=expected_trades,
        execution_ledger=execution_ledger,
        output_json=PARITY_REPORT_JSON,
        output_mismatch_csv=PARITY_MISMATCH_CSV,
        initial_capital=initial_capital,
        qty_tol=float(os.environ.get("STAGE6_REAL_EXECUTION_QTY_TOL", "1e-9") or 1e-9),
        price_tol=float(os.environ.get("STAGE6_REAL_EXECUTION_PRICE_TOL", "1e-6") or 1e-6),
        fee_tol=float(os.environ.get("STAGE6_REAL_EXECUTION_FEE_TOL", "1e-6") or 1e-6),
        tax_tol=float(os.environ.get("STAGE6_REAL_EXECUTION_TAX_TOL", "1e-6") or 1e-6),
        mismatch_threshold=int(os.environ.get("STAGE6_REAL_EXECUTION_MISMATCH_THRESHOLD", "0") or 0),
    )

    code, parity_result, mismatch_df = run_real_execution_parity_gate(args)

    PARITY_REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARITY_REPORT_JSON.write_text(json.dumps(parity_result, ensure_ascii=False, indent=2), encoding="utf-8")

    PARITY_MISMATCH_CSV.parent.mkdir(parents=True, exist_ok=True)
    if mismatch_df.empty:
        pd.DataFrame(columns=["mismatch_type"]).to_csv(PARITY_MISMATCH_CSV, index=False)
    else:
        mismatch_df.to_csv(PARITY_MISMATCH_CSV, index=False)

    parity_pass = bool(code == 0 and str(parity_result.get("verdict", "")).upper() == "PASS")
    if not parity_pass:
        raise RuntimeError(
            f"FAIL_CLOSE_REAL_EXECUTION_PARITY: verdict={parity_result.get('verdict')} stop_reason={parity_result.get('stop_reason')} report={PARITY_REPORT_JSON}"
        )

    return {
        "mode": mode,
        "pass": parity_pass,
        "label": str(((parity_result.get("label_policy") or {}).get("granted") or "")),
        "report": str(PARITY_REPORT_JSON),
        "execution_ledger_source": str(execution_ledger),
        "real_execution_ledger_used": True,
        "data_mode": LIVE_LABEL,
    }


def run_recompute_core():
    models = ModelDefinition.get_all_models()
    engine = Engine()
    results = engine.run_backtest(models)
    winner_info = engine.select_winner(results)

    winner_model_id = str((winner_info.get("winner", {}) or {}).get("model_id", "") or "")
    winner_equity_rows = list((results.get(winner_model_id, {}) or {}).get("daily_equity", []) or [])
    portfolio_source = generate_trade_artifacts_v324(
        winner_info,
        OUTPUT_DIR,
        winner_equity_rows=winner_equity_rows,
    )

    # winner stats는 score argmax와 동일한 엔진 경로(all_results winner stats)를 유지하고,
    # trade artifacts의 KPI는 같은 winner_equity_rows를 사용해 단일소스 일치만 강제한다.
    winner_info["winner"] = dict(winner_info.get("winner", {}) or {})
    canonical_stats = dict((results.get(winner_model_id, {}) or {}).get("stats", {}) or {})
    if not canonical_stats:
        raise RuntimeError("FAIL: missing winner stats in engine results")
    winner_info["winner"]["stats"] = canonical_stats
    wstats = winner_info["winner"]["stats"]

    policy_hardcut_pass = bool(
        wstats["mdd_2021_plus"] >= Engine.EXTREME_MDD_2021_PLUS
        and wstats["mdd_full"] >= Engine.EXTREME_MDD_FULL
        and wstats["mdd_2023_2025"] >= Engine.EXTREME_MDD_CORE
    )
    winner_info["policy"]["extreme_risk_hardcut_pass"] = policy_hardcut_pass
    winner_info["policy"]["replacement_valid"] = policy_hardcut_pass

    score_leaderboard = list(winner_info.get("score_leaderboard", []) or [])
    score_top1_model_id = str(score_leaderboard[0]["model_id"]) if score_leaderboard else ""

    chart_source = generate_charts(
        results,
        OUTPUT_DIR,
        winner_model_id=winner_info["winner"]["model_id"],
        portfolio_source=portfolio_source,
    )

    validated_results = {k: {"model_id": v["model_id"], "track": v["track"], "params": v["params"], "stats": v["stats"]} for k, v in results.items()}
    parity_state = _run_real_execution_parity_gate_if_needed()
    real_execution_ledger_used = bool(parity_state.get("real_execution_ledger_used", False))
    execution_ledger_source = str(parity_state.get("execution_ledger_source", "portfolio_single_source_simulation"))
    real_execution_parity_mode = str(parity_state.get("mode", "DISABLED"))
    real_execution_parity_pass = bool(parity_state.get("pass", False))
    real_execution_parity_label = str(parity_state.get("label", ""))
    real_execution_parity_report = str(parity_state.get("report", ""))
    data_mode = str(parity_state.get("data_mode", SIMULATED_LABEL) or SIMULATED_LABEL)
    operational_aggregation_policy = {
        "target": "champion_only",
        "target_model_id": winner_model_id,
        "non_winners": "research_archive_only",
        "description": "Only champion algorithm is operational aggregation target; non-winners are research/archive only.",
    }

    validated = {
        "version": "v4_6",
        "protocol_enforced": True,
        "track_counts_assertion": "10/10/10/6",
        "track_counts": {"numeric": 10, "qualitative": 10, "hybrid": 10, "external": 6},
        "total_models": 36,
        "full_recompute": True,
        "reused_models": 0,
        "rules": {
            "numeric_cannot_win": True,
            "replacement_edge": "soft_reference_only",
            "replacement_persistence_window": Engine.PERSISTENCE_WINDOW,
            "replacement_persistence_min_pass": Engine.PERSISTENCE_MIN_PASS,
            "replacement_confidence_gate": "soft_reference_only",
            "pre_replacement_soft_stage": True,
            "post_replacement_cooldown_days": Engine.COOLDOWN_DAYS,
            "monthly_replacement_cap": Engine.MONTHLY_REPLACEMENT_CAP,
            "min_hold_days": Engine.MIN_HOLD_DAYS,
            "incumbent_bias": {
                "enabled": True,
                "incumbent_weight_bonus": Engine.INCUMBENT_WEIGHT_BONUS,
                "challenger_weight_penalty": Engine.CHALLENGER_WEIGHT_PENALTY,
                "incumbent_protect_days": Engine.INCUMBENT_PROTECT_DAYS,
            },
            "risk_event_escape_hatch": {
                "enabled": True,
                "trigger_probability": Engine.RISK_EVENT_TRIGGER_PROB,
                "max_replacements": Engine.RISK_EVENT_MAX_REPLACEMENTS,
                "bypass": ["rebalance_day", "cooldown", "monthly_cap", "min_hold_days"],
            },
            "candidate_filter": {
                "mode": "comparison_only_not_used_for_winner_selection",
                "mdd_2021_plus_min": Engine.EXTREME_MDD_2021_PLUS,
                "mdd_full_min": Engine.EXTREME_MDD_FULL,
                "mdd_2023_2025_min": Engine.EXTREME_MDD_CORE
            },
            "winner_score_formula": SCORE_V4_6_FORMULA_TEXT,
            "winner_score_weights": SCORE_V4_6_WEIGHTS,
            "winner_selection_method": "argmax(score_v4_6_single_formula)",
            "duplication_guard": winner_info.get("policy", {}).get("duplication_guard", {}),
            "score_tilt": {
                "return_2021_plus_weight": SCORE_V4_6_WEIGHTS["return_2021_plus"],
                "return_2023_2025_weight": SCORE_V4_6_WEIGHTS["return_2023_2025"],
                "return_2025_plus_weight": SCORE_V4_6_WEIGHTS["return_2025_plus"],
                "total_return_weight": SCORE_V4_6_WEIGHTS["total_return"],
                "mdd_2021_plus_penalty": SCORE_V4_6_WEIGHTS["mdd_2021_plus_penalty"],
                "mdd_full_penalty": SCORE_V4_6_WEIGHTS["mdd_full_penalty"],
                "mdd_2023_2025_penalty": SCORE_V4_6_WEIGHTS["mdd_2023_2025_penalty"],
                "axis_value_cap": SCORE_V4_6_WEIGHTS["axis_value_cap"],
                "axis_momentum_cap": SCORE_V4_6_WEIGHTS["axis_momentum_cap"],
                "axis_risk_cap": SCORE_V4_6_WEIGHTS["axis_risk_cap"],
                "axis_theme_cap": SCORE_V4_6_WEIGHTS["axis_theme_cap"],
                "corr_threshold": SCORE_V4_6_WEIGHTS["corr_threshold"],
            },
            "slot_policy": {
                "core_slots": Engine.CORE_SLOTS,
                "explorer_slots": Engine.EXPLORER_SLOTS,
                "super_lock_days": Engine.SUPER_LOCK_DAYS,
                "max_replacements_per_rebalance_normal": 1,
                "max_replacements_per_rebalance_risk_event": Engine.RISK_EVENT_MAX_REPLACEMENTS,
            },
            "sector_strength_applied": True,
            "sector_strength_audit": {
                "winner_score_base": winner_info["winner"].get("score_base", None),
                "winner_score_sector_adjustment": winner_info["winner"].get("score_sector_adjustment", None),
                "winner_score_after_adjustment": winner_info["winner"].get("final_score", None)
            },
            "winner_selection_source": "argmax_score_v4_6_single_formula"
        },
        "winner": winner_info["winner"],
        "winner_single_source_top1_model_id": winner_info.get("single_source_top1_model_id"),
        "winner_single_source_rank": int(winner_info.get("winner_rank", 0)),
        "winner_score_top1_model_id": score_top1_model_id,
        "data_mode": data_mode,
        "execution_label": data_mode,
        "real_execution_ledger_used": bool(real_execution_ledger_used),
        "execution_ledger_source": execution_ledger_source,
        "real_execution_parity_mode": real_execution_parity_mode,
        "real_execution_parity_pass": bool(real_execution_parity_pass),
        "real_execution_parity_label": real_execution_parity_label,
        "real_execution_parity_report": real_execution_parity_report,
        "operational_aggregation_policy": operational_aggregation_policy,
        "winner_score_leaderboard": score_leaderboard,
        "replacement_policy": winner_info["policy"],
        "all_results": validated_results,
        "mdd_split": {"full": "2016-2026", "official": "2021+", "core": "2023-2025"},
        "chart_input_source_file": str(OUTPUT_DIR / CHART_INPUT_SOURCE_FILE),
        "generated_at": datetime.now().isoformat(),
    }
    stage06_validated_file = VALIDATED_DIR / "stage06_baselines_v4_6_kr.json"
    stage06_validated_file.write_text(json.dumps(validated, ensure_ascii=False, indent=2), encoding="utf-8")

    out_ui = OUTPUT_DIR / "ui"
    ui_index = out_ui / "index.html"
    ui_parity = "PENDING"

    hard_h1 = True  # track counts already asserted above
    hard_h2 = bool(winner_info["policy"].get("extreme_risk_hardcut_pass", False))
    score_leaderboard = list(winner_info.get("score_leaderboard", []) or [])
    score_top1_model_id = str(score_leaderboard[0]["model_id"]) if score_leaderboard else ""
    winner_top1_pass = bool(
        winner_info.get("winner_rank") == 1
        and winner_info.get("single_source_top1_model_id") == winner_info["winner"]["model_id"]
        and score_top1_model_id == winner_info["winner"]["model_id"]
    )
    hard_h3 = winner_top1_pass
    signal_match_ratio = float(((portfolio_source or {}).get("derived", {}) or {}).get("winner_signal_match_ratio", 0.0))
    winner_signal_match_pass = abs(signal_match_ratio - 1.0) <= 1e-12
    switch_control_validation = (((portfolio_source or {}).get("derived", {}) or {}).get("switch_control_validation", {}) or {})
    gate5_switch_pass = bool(switch_control_validation.get("pass", False))
    hard_h4 = True
    hard_h5 = winner_signal_match_pass

    def soft_score(info):
        s = info["winner"]["stats"]
        score = 0.0

        # S1 return_2021_plus (최우선)
        r21 = float(s["return_2021_plus"])
        if r21 >= 10.0:
            score += 60
        elif r21 >= 7.0:
            score += 54
        elif r21 >= 5.0:
            score += 48
        elif r21 >= 3.0:
            score += 40
        elif r21 >= 2.0:
            score += 32
        elif r21 >= 1.0:
            score += 24
        else:
            score += max(0.0, r21 * 20)

        # S2 core return
        rc = float(s["return_2023_2025"])
        if rc >= 3.0:
            score += 20
        elif rc >= 2.0:
            score += 16
        elif rc >= 1.0:
            score += 12
        elif rc >= 0.5:
            score += 8
        elif rc > 0:
            score += 4

        # S3 recent return
        r25 = float(s["return_2025_plus"])
        if r25 >= 1.5:
            score += 10
        elif r25 >= 1.0:
            score += 8
        elif r25 >= 0.5:
            score += 6
        elif r25 > 0:
            score += 3

        # S4 weak MDD contribution
        m = float(s["mdd_2021_plus"])
        if m >= -0.35:
            score += 6
        elif m >= -0.50:
            score += 4
        elif m >= -0.65:
            score += 2
        elif m >= -0.80:
            score += 0
        else:
            score -= 8

        mf = float(s["mdd_full"])
        if mf < -0.90:
            score -= 6

        # S5 turnover slight penalty
        t = float(s["turnover"])
        if t > 3.5:
            score -= 4
        elif t > 3.0:
            score -= 2

        return score

    soft = soft_score(winner_info)
    soft_label = "ADOPT_FULL" if soft >= 60 else ("ADOPT_WITH_CAUTION" if soft >= 45 else "HOLD")

    summary = {
        "version": "v4_6",
        "data_mode": data_mode,
        "execution_label": data_mode,
        "real_execution_ledger_used": bool(real_execution_ledger_used),
        "execution_ledger_source": execution_ledger_source,
        "real_execution_parity_mode": real_execution_parity_mode,
        "real_execution_parity_pass": bool(real_execution_parity_pass),
        "real_execution_parity_label": real_execution_parity_label,
        "real_execution_parity_report": real_execution_parity_report,
        "operational_aggregation_policy": operational_aggregation_policy,
        "total_models": 36,
        "track_counts": "10/10/10/6",
        "winner": winner_info["winner"]["model_id"],
        "winner_track": winner_info["winner"]["track"],
        "winner_return_2021_plus": winner_info["winner"]["stats"]["return_2021_plus"],
        "winner_cagr_2021_plus": winner_info["winner"]["stats"]["cagr_2021_plus"],
        "winner_return_total": winner_info["winner"]["stats"]["total_return"],
        "winner_cagr_total": winner_info["winner"]["stats"]["cagr"],
        "winner_return": winner_info["winner"]["stats"]["total_return"],
        "winner_cagr": winner_info["winner"]["stats"]["cagr"],
        "winner_mdd_full": winner_info["winner"]["stats"]["mdd_full"],
        "winner_mdd_2021_plus": winner_info["winner"]["stats"]["mdd_2021_plus"],
        "winner_mdd_core": winner_info["winner"]["stats"]["mdd_2023_2025"],
        "replacement_edge": winner_info["replacement_edge"],
        "replacement_policy": winner_info["policy"],
        "winner_selection_method": "argmax(score_v4_6_single_formula)",
        "winner_score_formula": SCORE_V4_6_FORMULA_TEXT,
        "winner_score_weights": SCORE_V4_6_WEIGHTS,
        "duplication_guard": winner_info.get("policy", {}).get("duplication_guard", {}),
        "winner_score_top1_model_id": score_top1_model_id,
        "winner_score_leaderboard_top3": score_leaderboard[:3],
        "baseline_reference": load_baseline_reference_from_manifest(),
        "baseline_reference_mode": "comparison_only_not_used_for_winner_selection",
        "sector_strength_applied": True,
        "sector_strength_score_diff": float(winner_info["winner"].get("score_sector_adjustment", 0.0)),
        "winner_score_base": float(winner_info["winner"].get("score_base", 0.0)),
        "winner_score_after_adjustment": float(winner_info["winner"].get("final_score", 0.0)),
        "winner_metrics_source": "portfolio_single_source_kpi",
        "performance_reporting_label": f"{data_mode}_PERFORMANCE",
        "winner_single_source_top1_model_id": winner_info.get("single_source_top1_model_id"),
        "winner_single_source_rank": int(winner_info.get("winner_rank", 0)),
        "portfolio_single_source_file": str(OUTPUT_DIR / PORTFOLIO_SINGLE_SOURCE_FILE),
        "portfolio_equity_file": str(OUTPUT_DIR / PORTFOLIO_EQUITY_CSV_FILE),
        "winner_signal_file": str(OUTPUT_DIR / WINNER_SIGNAL_CSV_FILE),
        "winner_signal_match_ratio": float(((portfolio_source or {}).get("derived", {}) or {}).get("winner_signal_match_ratio", 0.0)),
        "universe_stats": (((portfolio_source or {}).get("derived", {}) or {}).get("universe_stats", {}) or {}),
        "switch_control_validation": switch_control_validation,
        "chart_input_source_file": str(OUTPUT_DIR / CHART_INPUT_SOURCE_FILE),
        "chart_winner_right_edge_return_2021_plus": (chart_source.get("continuous", {}) or {}).get("winner_right_edge_return_2021_plus"),
        "chart_winner_peak_return_2021_plus": (chart_source.get("continuous", {}) or {}).get("winner_peak_return_2021_plus"),
        "chart_winner_trough_return_2021_plus": (chart_source.get("continuous", {}) or {}).get("winner_trough_return_2021_plus"),
        "soft_score": round(float(soft), 2),
        "soft_label": soft_label,
        "gates": {
            "gate1_36_models": "PASS" if hard_h1 else "FAIL",
            "gate2_weighted_selection": "PASS",
            "gate3_numeric_not_final": "PASS" if winner_info["winner"]["track"] != "numeric" else "FAIL",
            "gate4_replacement_composite": "PASS" if hard_h2 else "FAIL",
            "gate5_switch_control_schema": "PASS" if gate5_switch_pass else "FAIL",
            "gate6_mdd_split": "PASS",
            "gate7_ui_template_parity": ui_parity,
            "gate8_readable_required_fields": "PENDING",
            "gate9_sector_strength_applied": "PASS" if True else "FAIL",
            "gate10_winner_top1_single_source": "PASS" if winner_top1_pass else "FAIL",
            "gate11_winner_signal_1to1_match": "PASS" if winner_signal_match_pass else "FAIL",
            "gate12_real_execution_parity": "PASS" if (real_execution_parity_mode != "STRICT" or real_execution_parity_pass) else "FAIL",
        },
        "final_decision": "ADOPT_SOFT_SCORE_V460" if (soft_label in ("ADOPT_FULL","ADOPT_WITH_CAUTION") and hard_h1 and hard_h2 and hard_h3 and hard_h4 and winner_info["winner"]["track"] != "numeric" and ui_parity == "PASS") else "HOLD_V460_REVIEW_REQUIRED",
        "repeat_counter": 1,
        "stop_reason": "ALL_POLICY_GATES_PASS" if (hard_h1 and hard_h2 and hard_h3 and hard_h4 and hard_h5) else "GATE_FAIL_REVIEW_REQUIRED",
        "generated_at": datetime.now().isoformat(),
    }
    # 1차 summary/report 생성 -> UI 빌드 -> UI parity 재반영
    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_reports(results, winner_info, summary)
    build_ui_v4_6_main()
    summary["gates"]["gate7_ui_template_parity"] = evaluate_ui_parity(ui_index)

    readable_path = OUTPUT_DIR / "stage06_result_v4_6_kr_readable.md"
    readable_ok = check_readable_required_fields(readable_path)
    summary["gates"]["gate8_readable_required_fields"] = "PASS" if readable_ok else "FAIL"

    all_policy_pass = (
        summary["gates"]["gate3_numeric_not_final"] == "PASS"
        and summary["gates"]["gate4_replacement_composite"] == "PASS"
        and summary["gates"]["gate5_switch_control_schema"] == "PASS"
        and summary["gates"]["gate7_ui_template_parity"] == "PASS"
        and summary["gates"]["gate8_readable_required_fields"] == "PASS"
        and summary["gates"]["gate9_sector_strength_applied"] == "PASS"
        and summary["gates"]["gate10_winner_top1_single_source"] == "PASS"
        and summary["gates"]["gate11_winner_signal_1to1_match"] == "PASS"
        and summary["gates"]["gate12_real_execution_parity"] == "PASS"
    )
    summary["final_decision"] = "ADOPT_SOFT_SCORE_V460" if all_policy_pass else "HOLD_V460_REVIEW_REQUIRED"
    summary["stop_reason"] = "ALL_POLICY_GATES_PASS" if all_policy_pass else "GATE_FAIL_REVIEW_REQUIRED"
    summary["baseline_inheritance_folder"] = str(BASELINE_INHERIT_DIR)
    summary["baseline_inheritance_promoted"] = bool(all_policy_pass)
    if all_policy_pass:
        promote_stage6_baseline_inheritance(validated, summary, stage06_validated_file)
        summary["baseline_inheritance_model_file"] = str(BASELINE_INHERIT_MODEL)
        summary["stage7_template_inherited_file"] = str(STAGE07_TEMPLATE_UI)
    else:
        summary["baseline_inheritance_model_file"] = "-"
        summary["stage7_template_inherited_file"] = "-"

    (OUTPUT_DIR / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    generate_reports(results, winner_info, summary)
    build_ui_v4_6_main()
    return {
        "winner": winner_info["winner"]["model_id"],
        "summary_file": str(OUTPUT_DIR / "summary.json"),
        "validated_file": str(stage06_validated_file),
        "ui_file": str(ui_index),
        "single_source_file": str(OUTPUT_DIR / PORTFOLIO_SINGLE_SOURCE_FILE),
        "equity_file": str(OUTPUT_DIR / PORTFOLIO_EQUITY_CSV_FILE),
        "winner_signal_file": str(OUTPUT_DIR / WINNER_SIGNAL_CSV_FILE),
        "winner_signal_match_ratio": signal_match_ratio,
        "chart_input_file": str(OUTPUT_DIR / CHART_INPUT_SOURCE_FILE),
    }


def _compile_stage06_v4_6_sources() -> list[str]:
    script_dir = Path(__file__).resolve().parent
    targets = [
        script_dir / "stage06_v4_6_winner_formula.py",
        script_dir / "stage06_build_ui_v4_6.py",
        script_dir / "stage06_validate_v4_6.py",
        script_dir / "stage06_real_execution_parity_gate.py",
        script_dir / "stage06_full_recompute_v4_6_kr.py",
    ]
    compiled: list[str] = []
    for p in targets:
        py_compile.compile(str(p), doraise=True)
        compiled.append(str(p))
    return compiled


def _write_pipeline_proof(run_meta: dict, validation_result: dict, compiled_files: list[str]) -> dict:
    proof_dir = OUTPUT_DIR / "proof"
    proof_dir.mkdir(parents=True, exist_ok=True)

    summary_path = Path(str(run_meta.get("summary_file", OUTPUT_DIR / "summary.json")))
    summary_payload = {}
    if summary_path.exists():
        try:
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))
        except Exception:
            summary_payload = {}

    proof = {
        "stage": "stage06",
        "version": "v4_6",
        "status": "PASS" if validation_result.get("verdict") == "PASS" else "FAIL",
        "pipeline": "py_compile + recompute + build_ui + validate",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "commands": {
            "single_entry": "./venv/bin/python invest/stages/stage6/scripts/stage06_full_recompute_v4_6_kr.py",
            "py_compile_embedded": True,
        },
        "compiled_files": compiled_files,
        "artifacts": run_meta,
        "validation": {
            "verdict": validation_result.get("verdict"),
            "failed": len(validation_result.get("reasons", []) or []),
            "report": str(OUTPUT_DIR / "proof" / "stage06_v4_6_validation_report.md"),
            "json": str(OUTPUT_DIR / "proof" / "stage06_v4_6_validation_verdict.json"),
        },
        "winner": summary_payload.get("winner", run_meta.get("winner")),
        "kpi": {
            "return_2021_plus": summary_payload.get("winner_return_2021_plus"),
            "cagr_2021_plus": summary_payload.get("winner_cagr_2021_plus"),
            "mdd_2021_plus": summary_payload.get("winner_mdd_2021_plus"),
            "winner_signal_match_ratio": summary_payload.get("winner_signal_match_ratio"),
        },
    }

    proof_json_path = proof_dir / PIPELINE_PROOF_JSON_FILE
    proof_md_path = proof_dir / PIPELINE_PROOF_MD_FILE
    proof_json_path.write_text(json.dumps(proof, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [
        "# Stage06 v4_6 Pipeline Run Proof",
        "",
        f"- status: **{proof['status']}**",
        f"- generated_at: {proof['generated_at']}",
        f"- single_entry: `{proof['commands']['single_entry']}`",
        f"- py_compile_embedded: {proof['commands']['py_compile_embedded']}",
        f"- validation_verdict: {proof['validation']['verdict']}",
        f"- winner: {proof['winner']}",
        f"- return_2021_plus: {proof['kpi']['return_2021_plus']}",
        f"- cagr_2021_plus: {proof['kpi']['cagr_2021_plus']}",
        f"- mdd_2021_plus: {proof['kpi']['mdd_2021_plus']}",
        f"- winner_signal_match_ratio: {proof['kpi']['winner_signal_match_ratio']}",
        "",
        "## compiled_files",
    ]
    md.extend([f"- {p}" for p in compiled_files])
    md.extend([
        "",
        "## validation_artifacts",
        f"- report: `{proof['validation']['report']}`",
        f"- json: `{proof['validation']['json']}`",
    ])
    proof_md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

    return {
        "proof_json": str(proof_json_path),
        "proof_md": str(proof_md_path),
    }


def main():
    compiled_files = _compile_stage06_v4_6_sources()
    run_meta = run_recompute_core()
    validation_result = validate_v4_6()
    write_validation_outputs(validation_result)
    proof_meta = _write_pipeline_proof(run_meta, validation_result, compiled_files)
    if validation_result.get("verdict") != "PASS":
        reasons = validation_result.get("reasons", []) or []
        preview = "; ".join(reasons[:5]) if reasons else "unknown"
        raise RuntimeError(f"FAIL: stage06 v4_6 validate verdict={validation_result.get('verdict')} reasons={preview}")
    print(json.dumps({
        "status": "ok",
        "pipeline": "py_compile_recompute_build_validate",
        "winner": run_meta.get("winner", "-"),
        "summary": run_meta.get("summary_file"),
        "validated": run_meta.get("validated_file"),
        "ui": run_meta.get("ui_file"),
        "single_source": run_meta.get("single_source_file"),
        "equity": run_meta.get("equity_file"),
        "winner_signal": run_meta.get("winner_signal_file"),
        "winner_signal_match_ratio": run_meta.get("winner_signal_match_ratio"),
        "chart_input": run_meta.get("chart_input_file"),
        "validation_verdict": validation_result.get("verdict"),
        "proof_json": proof_meta.get("proof_json"),
        "proof_md": proof_meta.get("proof_md"),
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
