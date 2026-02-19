#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pykrx import stock

BASE = Path(__file__).resolve().parents[1]
RESULT_V320 = BASE / "invest/results/validated/stage05_baselines_v3_20_kr.json"
RESULT_V318 = BASE / "invest/results/validated/stage05_baselines_v3_18_kr.json"
OUT_REPORT = BASE / "invest/reports/stage_updates/stage05/v3_20/stage05_result_v3_20_kr_readable_detailed.md"
OUT_EVENTS_CSV = BASE / "invest/reports/stage_updates/stage05/v3_20/stage05_trade_events_v3_20_kr.csv"
OUT_TIMELINE_CSV = BASE / "invest/reports/stage_updates/stage05/v3_20/stage05_portfolio_timeline_v3_20_kr.csv"
OUT_CHART_DIR = BASE / "invest/reports/stage_updates/stage05/v3_20/charts"
OUT_CHART_KOSPI = OUT_CHART_DIR / "stage05_v3_20_vs_kospi.png"
OUT_CHART_KOSPI_KOSDAQ = OUT_CHART_DIR / "stage05_v3_20_vs_kospi_kosdaq.png"


def import_stage05_module():
    mod_path = BASE / "invest/scripts/stage05_3x3_v3_9_kr.py"
    name = "stage05_3x3_v3_9_kr_mod_for_detail"
    spec = importlib.util.spec_from_file_location(name, mod_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import stage05_3x3_v3_9_kr.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def fmt_pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def fmt_pct_from_ratio(r: float) -> str:
    return f"{r:.2f}%"


def md_escape(v: Any) -> str:
    s = str(v)
    return s.replace("|", "\\|").replace("\n", "<br>")


def table_md(rows: list[dict[str, Any]], columns: list[str]) -> str:
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for r in rows:
        lines.append("| " + " | ".join(md_escape(r.get(c, "")) for c in columns) + " |")
    return "\n".join(lines)


def feature_state(df: pd.DataFrame, d: pd.Timestamp, p: dict[str, Any]) -> dict[str, float]:
    h = df.loc[:d]
    c = h["Close"]
    ret_s = float(c.pct_change(int(p["ret_short"])).iloc[-1]) if len(c) > int(p["ret_short"]) else 0.0
    ret_m = float(c.pct_change(int(p["ret_mid"])).iloc[-1]) if len(c) > int(p["ret_mid"]) else 0.0
    ma_f = float(c.ewm(span=int(p["trend_fast"])).mean().iloc[-1]) if len(c) else 0.0
    ma_s = float(c.ewm(span=int(p["trend_slow"])).mean().iloc[-1]) if len(c) else 0.0
    ma120 = float(c.rolling(120).mean().iloc[-1]) if len(c) >= 120 else ma_s

    prev = c.iloc[:-1]
    if len(prev) >= int(p["trend_slow"]):
        prev_ma_f = float(prev.ewm(span=int(p["trend_fast"])).mean().iloc[-1])
        prev_ma_s = float(prev.ewm(span=int(p["trend_slow"])).mean().iloc[-1])
    else:
        prev_ma_f, prev_ma_s = ma_f, ma_s

    return {
        "ret_s": ret_s,
        "ret_m": ret_m,
        "ma_f": ma_f,
        "ma_s": ma_s,
        "ma120": ma120,
        "prev_ma_f": prev_ma_f,
        "prev_ma_s": prev_ma_s,
    }


def classify_buy_reason(f: dict[str, float]) -> str:
    supercycle = (f["ma_f"] > f["ma_s"] > f["ma120"]) and (f["ret_m"] > 0)
    turnaround = (f["ret_s"] > 0) and (
        (f["ret_m"] <= 0) or ((f["ma_f"] > f["ma_s"]) and (f["prev_ma_f"] <= f["prev_ma_s"]))
    )
    if supercycle:
        return "슈퍼사이클 지속"
    if turnaround:
        return "턴어라운드 진입"
    return "리스크완화"


def bend_signal(f: dict[str, float]) -> bool:
    return bool((f["ma_f"] < f["ma_s"]) or (f["ret_s"] < 0 and f["ret_m"] < 0))


def build_name_mapper(codes: list[str]) -> dict[str, str]:
    mapper: dict[str, str] = {}
    for c in sorted(set(codes)):
        try:
            nm = stock.get_market_ticker_name(c)
            mapper[c] = nm if nm else c
        except Exception:
            mapper[c] = c
    return mapper


def replay_with_events(mod, model: dict[str, Any]) -> dict[str, Any]:
    p = dict(model["effective_params"])
    score_model = str(model["score_model"])

    mod.guard_kr_only()
    universe = mod.load_universe(limit=int(p["universe_limit"]))
    supplies = {c: mod.load_supply(c) for c in universe}
    dates = mod.rebalance_dates(universe)

    cash = 1.0
    holdings: dict[str, dict[str, Any]] = {}
    eq_curve: list[tuple[pd.Timestamp, float]] = []
    trade_rows: list[dict[str, Any]] = []
    timeline_rows: list[dict[str, Any]] = []
    monthly_rows: list[dict[str, Any]] = []
    supercycle_rows: list[dict[str, Any]] = []

    trade_count = 0
    replacement_count = 0
    trailing_stop_count = 0
    buy_notional = 0.0
    sell_notional = 0.0

    reason_counts = {"replacement": 0, "trailing_stop": 0, "final_liquidation": 0}

    trade_id = 0

    def mark_sell(code: str, date: pd.Timestamp, price: float, sell_reason: str, reason_key: str, detail: str = ""):
        nonlocal cash, trade_count, sell_notional, trade_id
        if code not in holdings:
            return
        pos = holdings.pop(code)
        gross = float(pos["shares"]) * float(price)
        fee = gross * float(p["fee"])
        cash += gross - fee
        sell_notional += gross
        trade_count += 1
        reason_counts[reason_key] = reason_counts.get(reason_key, 0) + 1
        trade_id += 1

        holding_days = int((date - pd.to_datetime(pos["buy_date"])).days)
        pnl = float(price / max(1e-12, float(pos["buy_price"])) - 1.0)

        trade_rows.append(
            {
                "trade_id": trade_id,
                "buy_date": pd.to_datetime(pos["buy_date"]).strftime("%Y-%m-%d"),
                "sell_date": date.strftime("%Y-%m-%d"),
                "stock_code": code,
                "stock_name": code,
                "buy_price": float(pos["buy_price"]),
                "sell_price": float(price),
                "return_pct": pnl * 100.0,
                "holding_days": holding_days,
                "buy_reason": str(pos.get("buy_reason", "리스크완화")),
                "sell_reason": sell_reason,
                "sell_reason_detail": detail,
            }
        )

    for d in dates:
        start_set = set(holdings.keys())
        day_sell_reasons: list[str] = []

        px_now: dict[str, float] = {}
        score_by_code: dict[str, float] = {}
        feat_by_code: dict[str, dict[str, float]] = {}

        for code, df in universe.items():
            h = df.loc[:d]
            if h.empty:
                continue
            px_now[code] = float(h["Close"].iloc[-1])
            score_pack = mod.calc_scores(d, df, supplies.get(code), p)
            if score_pack is None:
                continue
            score_by_code[code] = float(score_pack[score_model])
            feat_by_code[code] = feature_state(df, d, p)

        if not score_by_code:
            total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
            eq_curve.append((d, total))
            continue

        # trailing stop
        for code in list(holdings.keys()):
            if code not in px_now:
                continue
            current_price = float(px_now[code])
            holdings[code]["peak_price"] = max(float(holdings[code]["peak_price"]), current_price)
            peak = float(holdings[code]["peak_price"])
            drawdown = (current_price / peak) - 1.0 if peak > 0 else 0.0
            if drawdown <= float(p["trailing_stop_pct"]):
                mark_sell(
                    code,
                    d,
                    current_price,
                    sell_reason="트레일링스탑",
                    reason_key="trailing_stop",
                    detail=f"peak 대비 {drawdown * 100:.2f}% 하락",
                )
                day_sell_reasons.append("트레일링스탑")
                trailing_stop_count += 1

        ranked = sorted(score_by_code.items(), key=lambda x: x[1], reverse=True)
        top = ranked[: int(p["max_pos"])]
        top_set = {c for c, _ in top}

        n_hold = len(holdings)
        replace_cap = int(math.floor(n_hold * float(p["monthly_replace_cap"]))) if n_hold > 0 else 0

        challengers = [(c, s) for c, s in top if c not in holdings]
        chosen_challengers: set[str] = set()
        to_replace: list[tuple[str, str, float]] = []

        for code in sorted([c for c in holdings.keys() if c not in top_set], key=lambda x: score_by_code.get(x, -999.0)):
            if len(to_replace) >= replace_cap:
                break
            held_days = int((d - holdings[code]["buy_date"]).days)
            if held_days < int(p["min_hold_days"]):
                continue

            incumbent = score_by_code.get(code, -999.0)
            eligible = [
                (cc, ss)
                for cc, ss in challengers
                if cc not in chosen_challengers and ss >= incumbent + float(p["replace_edge"])
            ]
            if not eligible:
                continue
            challenger, ch_score = sorted(eligible, key=lambda x: x[1], reverse=True)[0]
            chosen_challengers.add(challenger)
            to_replace.append((code, challenger, float(ch_score - incumbent)))

        for old_code, challenger, gap in to_replace:
            if old_code in px_now:
                fs = feat_by_code.get(old_code, {"ma_f": 0.0, "ma_s": 0.0, "ret_s": 0.0, "ret_m": 0.0})
                if bend_signal(fs):
                    sell_reason = "꺾임신호"
                    detail = f"score_gap={gap:.4f}, challenger={challenger}"
                else:
                    sell_reason = "교체(+15% 우위)"
                    detail = f"score_gap={gap:.4f}, challenger={challenger}"
                mark_sell(old_code, d, float(px_now[old_code]), sell_reason=sell_reason, reason_key="replacement", detail=detail)
                day_sell_reasons.append(sell_reason)
                replacement_count += 1

        slots_left = max(int(p["max_pos"]) - len(holdings), 0)
        buy_candidates = [c for c, _ in top if c not in holdings][:slots_left]

        buy_scores = {c: score_by_code[c] for c in buy_candidates}
        weights = mod.normalize_weights(buy_scores)

        start_cash = cash
        for c in buy_candidates:
            if c not in px_now:
                continue
            buy_cash = start_cash * weights.get(c, 0.0)
            buy_cash = min(buy_cash, cash)
            if buy_cash <= 0:
                continue
            price = float(px_now[c])
            fee = buy_cash * float(p["fee"])
            net = buy_cash - fee
            shares = net / price if price > 0 else 0.0
            if shares <= 0:
                continue

            fs = feat_by_code.get(c, {"ret_s": 0.0, "ret_m": 0.0, "ma_f": 0.0, "ma_s": 0.0, "ma120": 0.0, "prev_ma_f": 0.0, "prev_ma_s": 0.0})
            buy_reason = classify_buy_reason(fs)

            cash -= buy_cash
            holdings[c] = {
                "shares": shares,
                "buy_price": price,
                "buy_date": d,
                "peak_price": price,
                "buy_reason": buy_reason,
            }
            buy_notional += buy_cash
            trade_count += 1

        total = cash + sum(v["shares"] * px_now.get(c, v["buy_price"]) for c, v in holdings.items())
        eq_curve.append((d, total))

        end_set = set(holdings.keys())
        added = sorted(end_set - start_set)
        removed = sorted(start_set - end_set)
        kept = sorted(start_set & end_set)

        def _names(codes: list[str]) -> str:
            return ", ".join(codes) if codes else "-"

        rs_counts = pd.Series(day_sell_reasons).value_counts().to_dict() if day_sell_reasons else {}
        reason_summary = ", ".join(f"{k}:{v}" for k, v in rs_counts.items()) if rs_counts else "-"

        timeline_rows.append(
            {
                "rebalance_date": d.strftime("%Y-%m-%d"),
                "added_codes": _names(added),
                "removed_codes": _names(removed),
                "kept_codes": _names(kept),
                "replacement_basis": reason_summary,
            }
        )

        # month-end holdings snapshot
        hold_values = {c: float(v["shares"]) * float(px_now.get(c, v["buy_price"])) for c, v in holdings.items()}
        total_hold = sum(hold_values.values())
        total_port = total

        rows_desc: list[str] = []
        sc_count = 0
        bend_count = 0
        for c, val in sorted(hold_values.items(), key=lambda x: x[1], reverse=True):
            wt = (val / total_port) * 100.0 if total_port > 0 else 0.0
            hd = int((d - holdings[c]["buy_date"]).days)
            rows_desc.append(f"{c}({wt:.1f}%, {hd}d)")

            fs = feat_by_code.get(c)
            if fs is not None:
                if (fs["ma_f"] > fs["ma_s"] > fs["ma120"]) and (fs["ret_m"] > 0):
                    sc_count += 1
                if bend_signal(fs):
                    bend_count += 1

        monthly_rows.append(
            {
                "month_end": d.strftime("%Y-%m-%d"),
                "holdings_n": int(len(holdings)),
                "holdings_weights_days": "; ".join(rows_desc) if rows_desc else "-",
            }
        )

        supercycle_rows.append(
            {
                "date": d.strftime("%Y-%m-%d"),
                "sustain_score": round(sc_count / max(1, len(holdings)), 4),
                "bend_signals": int(bend_count),
                "liquidation_triggers": reason_summary,
            }
        )

    # final liquidation
    if eq_curve:
        d = eq_curve[-1][0]
        px_now = {c: float(df.loc[:d]["Close"].iloc[-1]) for c, df in universe.items() if not df.loc[:d].empty}
        for c in list(holdings.keys()):
            if c in px_now:
                mark_sell(c, d, float(px_now[c]), sell_reason="최종청산", reason_key="final_liquidation", detail="백테스트 종료")

    eq = pd.Series({d: v for d, v in eq_curve}).sort_index()
    annual, stats = mod.annual_stats_from_curve(eq)
    avg_eq = float(eq.mean()) if len(eq) else 1.0
    years = max(len(annual), 1)
    turnover_proxy = float((buy_notional + sell_notional) / (avg_eq * years + 1e-9))

    stats_full = {
        **stats,
        "turnover_proxy": turnover_proxy,
        "trade_count": trade_count,
        "replacement_count": replacement_count,
        "trailing_stop_count": trailing_stop_count,
    }

    return {
        "dates": dates,
        "eq": eq,
        "stats": stats_full,
        "reason_counts": reason_counts,
        "trade_rows": trade_rows,
        "timeline_rows": timeline_rows,
        "monthly_rows": monthly_rows,
        "supercycle_rows": supercycle_rows,
        "universe_codes": list(universe.keys()),
    }


def fetch_benchmark_close(ticker: str, start: str, end: str) -> pd.Series:
    df = stock.get_index_ohlcv_by_date(start.replace("-", ""), end.replace("-", ""), ticker)
    if df.empty:
        return pd.Series(dtype=float)
    close = pd.to_numeric(df["종가"], errors="coerce").dropna()
    close.index = pd.to_datetime(close.index)
    return close.sort_index()


def align_series_to_dates(close: pd.Series, dates: pd.DatetimeIndex) -> pd.Series:
    vals = {}
    for d in dates:
        h = close.loc[:d]
        if h.empty:
            vals[d] = np.nan
        else:
            vals[d] = float(h.iloc[-1])
    s = pd.Series(vals).sort_index().ffill().bfill()
    return s / max(1e-12, float(s.iloc[0])) if not s.empty else s


def plot_compare(
    strategy_eq: pd.Series,
    kospi_eq: pd.Series,
    kosdaq_eq: pd.Series | None,
    effective_years: list[int],
    out_path: Path,
    title_suffix: str,
) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15, 5), constrained_layout=True)

    def _plot(ax, mask, subtitle):
        s = strategy_eq[mask]
        k = kospi_eq.reindex(s.index).ffill().bfill()
        ax.plot(s.index, (s - 1.0) * 100.0, label="Stage05 v3_20 내부선발(hybrid_h2, replay)", linewidth=2.2)
        ax.plot(k.index, (k - 1.0) * 100.0, label="KOSPI", linewidth=1.8)
        if kosdaq_eq is not None and not kosdaq_eq.empty:
            q = kosdaq_eq.reindex(s.index).ffill().bfill()
            ax.plot(q.index, (q - 1.0) * 100.0, label="KOSDAQ", linewidth=1.5, alpha=0.9)
        ax.axhline(0, color="gray", linewidth=0.8)
        ax.set_title(subtitle)
        ax.set_ylabel("누적수익률 (%)")
        ax.set_xlabel("기간")
        ax.grid(alpha=0.25)
        ax.legend(loc="best", fontsize=8)

    full_mask = strategy_eq.index.notna()
    eff_mask = strategy_eq.index.year.isin(effective_years)
    _plot(axes[0], full_mask, "Full Reference")
    _plot(axes[1], eff_mask, "Official Effective Window")

    fig.suptitle(f"Stage05 v3_20 vs Benchmarks ({title_suffix})")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main() -> int:
    mod = import_stage05_module()

    v320 = json.loads(RESULT_V320.read_text(encoding="utf-8"))
    v318 = json.loads(RESULT_V318.read_text(encoding="utf-8"))

    best = dict(v320["main_selection_best_internal_only"])
    best_model_id = str(best["model_id"])

    replay = replay_with_events(mod, best)

    # verify stats equality with canonical v3_20 numbers
    canonical = best["stats"]
    verify = replay["stats"]
    verification = {
        "total_return_diff": float(verify["total_return"] - canonical["total_return"]),
        "mdd_diff": float(verify["mdd"] - canonical["mdd"]),
        "cagr_diff": float(verify["cagr"] - canonical["cagr"]),
        "trade_count_diff": int(verify["trade_count"] - canonical["trade_count"]),
        "replacement_count_diff": int(verify["replacement_count"] - canonical["replacement_count"]),
        "trailing_stop_count_diff": int(verify["trailing_stop_count"] - canonical["trailing_stop_count"]),
    }

    # names mapping
    event_codes = [r["stock_code"] for r in replay["trade_rows"]]
    hold_codes = replay["universe_codes"]
    code_name = build_name_mapper(event_codes + hold_codes)

    for r in replay["trade_rows"]:
        c = r["stock_code"]
        r["stock_name"] = code_name.get(c, c)
        r["return_pct_fmt"] = fmt_pct_from_ratio(float(r["return_pct"]))

    for r in replay["timeline_rows"]:
        for k in ["added_codes", "removed_codes", "kept_codes"]:
            if r[k] == "-":
                continue
            names = [code_name.get(x.strip(), x.strip()) for x in r[k].split(",") if x.strip()]
            r[k] = ", ".join(names) if names else "-"

    for r in replay["monthly_rows"]:
        if r["holdings_weights_days"] == "-":
            continue
        chunks = [x.strip() for x in r["holdings_weights_days"].split(";") if x.strip()]
        mapped = []
        for ch in chunks:
            code = ch.split("(")[0]
            mapped.append(ch.replace(code, code_name.get(code, code), 1))
        r["holdings_weights_days"] = "; ".join(mapped)

    # export CSV outputs
    trade_df = pd.DataFrame(replay["trade_rows"]).sort_values(["sell_date", "buy_date", "stock_code"]).reset_index(drop=True)
    timeline_df = pd.DataFrame(replay["timeline_rows"])
    monthly_df = pd.DataFrame(replay["monthly_rows"])
    super_df = pd.DataFrame(replay["supercycle_rows"])

    OUT_EVENTS_CSV.parent.mkdir(parents=True, exist_ok=True)
    trade_df.to_csv(OUT_EVENTS_CSV, index=False, encoding="utf-8-sig")
    timeline_df.to_csv(OUT_TIMELINE_CSV, index=False, encoding="utf-8-sig")

    # benchmark + charts
    strategy_eq = replay["eq"].copy()
    start = strategy_eq.index.min().strftime("%Y-%m-%d")
    end = strategy_eq.index.max().strftime("%Y-%m-%d")

    kospi_close = fetch_benchmark_close("1001", start, end)
    kospi_eq = align_series_to_dates(kospi_close, strategy_eq.index)

    kosdaq_eq: pd.Series | None = None
    kosdaq_note = ""
    try:
        kosdaq_close = fetch_benchmark_close("2001", start, end)
        if not kosdaq_close.empty:
            kosdaq_eq = align_series_to_dates(kosdaq_close, strategy_eq.index)
    except Exception:
        kosdaq_eq = None

    effective_years = list(v318.get("chosen_round_gate", {}).get("effective_window_detail", {}).get("valid_years", [2023, 2024, 2025]))

    plot_compare(strategy_eq, kospi_eq, None, effective_years, OUT_CHART_KOSPI, title_suffix="KOSPI")

    if kosdaq_eq is not None and not kosdaq_eq.empty:
        plot_compare(strategy_eq, kospi_eq, kosdaq_eq, effective_years, OUT_CHART_KOSPI_KOSDAQ, title_suffix="KOSPI + KOSDAQ")
        kosdaq_note = "KOSDAQ 보조선도 생성 완료"
    else:
        kosdaq_note = "KOSDAQ 데이터 제약으로 KOSPI 단독 그래프만 사용"

    # interpretation numbers
    full_ret_strategy = float(strategy_eq.iloc[-1] / strategy_eq.iloc[0] - 1.0)
    full_ret_kospi = float(kospi_eq.iloc[-1] / kospi_eq.iloc[0] - 1.0)

    eff_mask = strategy_eq.index.year.isin(effective_years)
    strategy_eff = strategy_eq[eff_mask]
    kospi_eff = kospi_eq.reindex(strategy_eff.index).ffill().bfill()

    eff_ret_strategy = float(strategy_eff.iloc[-1] / strategy_eff.iloc[0] - 1.0) if len(strategy_eff) > 1 else 0.0
    eff_ret_kospi = float(kospi_eff.iloc[-1] / kospi_eff.iloc[0] - 1.0) if len(kospi_eff) > 1 else 0.0

    if kosdaq_eq is not None and not kosdaq_eq.empty:
        kosdaq_eff = kosdaq_eq.reindex(strategy_eff.index).ffill().bfill()
        full_ret_kosdaq = float(kosdaq_eq.iloc[-1] / kosdaq_eq.iloc[0] - 1.0)
        eff_ret_kosdaq = float(kosdaq_eff.iloc[-1] / kosdaq_eff.iloc[0] - 1.0) if len(kosdaq_eff) > 1 else 0.0
    else:
        full_ret_kosdaq = None
        eff_ret_kosdaq = None

    # markdown tables
    ledger_rows_md = []
    for r in trade_df.to_dict("records"):
        ledger_rows_md.append(
            {
                "매수일": r["buy_date"],
                "매도일": r["sell_date"],
                "종목명": r["stock_name"],
                "수익률%": f"{float(r['return_pct']):.2f}%",
                "매수사유": r["buy_reason"],
                "매도사유": r["sell_reason"],
            }
        )

    timeline_rows_md = []
    for r in timeline_df.to_dict("records"):
        timeline_rows_md.append(
            {
                "리밸런싱일": r["rebalance_date"],
                "편입": r["added_codes"],
                "편출": r["removed_codes"],
                "유지": r["kept_codes"],
                "교체근거": r["replacement_basis"],
            }
        )

    monthly_rows_md = []
    for r in monthly_df.to_dict("records"):
        monthly_rows_md.append(
            {
                "월말": r["month_end"],
                "보유종목수(1~6)": int(r["holdings_n"]),
                "비중/보유일수": r["holdings_weights_days"],
            }
        )

    super_rows_md = []
    for r in super_df.to_dict("records"):
        super_rows_md.append(
            {
                "일자": r["date"],
                "지속점수": f"{float(r['sustain_score']):.2f}",
                "꺾임신호": int(r["bend_signals"]),
                "청산트리거": r["liquidation_triggers"],
            }
        )

    report_lines = [
        "# stage05_result_v3_20_kr_readable_detailed",
        "",
        "## 목적",
        "- Stage05 v3_20 내부선발 1등 모델 기준으로 **언제 사고/팔았고, 왜 사고/팔았는지, 포트폴리오가 어떻게 변했는지**를 가독성 중심으로 재출력",
        "- 기존 성능 수치(`invest/results/validated/stage05_baselines_v3_20_kr.json`)는 변경하지 않고 설명 레이어만 강화",
        "",
        "## 기준 모델",
        f"- model_id: **{best_model_id}**",
        f"- track: **{best['track']}**",
        f"- 누적수익률: **{fmt_pct(float(canonical['total_return']))}**",
        f"- CAGR: **{fmt_pct(float(canonical['cagr']))}**",
        f"- MDD: **{fmt_pct(float(canonical['mdd']))}**",
        f"- 거래수: **{int(canonical['trade_count'])}회** (교체 {int(canonical['replacement_count'])} / 트레일링스탑 {int(canonical['trailing_stop_count'])})",
        "",
        "## 재생성 검증(설명용 리플레이)",
        "- canonical(공식) 성과 수치는 v3_20 JSON 값을 그대로 유지",
        "- 아래 diff는 거래 이벤트/원장 복원을 위해 현재 raw 스냅샷으로 리플레이했을 때의 편차(설명용)",
        f"- total_return diff(replay-canonical): {verification['total_return_diff']:.10f}",
        f"- mdd diff(replay-canonical): {verification['mdd_diff']:.10f}",
        f"- cagr diff(replay-canonical): {verification['cagr_diff']:.10f}",
        f"- trade_count diff: {verification['trade_count_diff']}",
        f"- replacement_count diff: {verification['replacement_count_diff']}",
        f"- trailing_stop_count diff: {verification['trailing_stop_count_diff']}",
        "",
        "## 벤치마크 비교 그래프",
        f"- KOSPI 그래프: `{OUT_CHART_KOSPI.relative_to(BASE)}`",
        f"- KOSPI+KOSDAQ 그래프: `{OUT_CHART_KOSPI_KOSDAQ.relative_to(BASE)}` ({kosdaq_note})",
        "",
        f"![stage05_v3_20_vs_kospi]({OUT_CHART_KOSPI.relative_to(BASE).as_posix()})",
        "",
    ]

    if kosdaq_eq is not None and not kosdaq_eq.empty and OUT_CHART_KOSPI_KOSDAQ.exists():
        report_lines += [
            f"![stage05_v3_20_vs_kospi_kosdaq]({OUT_CHART_KOSPI_KOSDAQ.relative_to(BASE).as_posix()})",
            "",
        ]

    report_lines += [
        "### 그래프 해석",
        f"- canonical 성과(공식): 누적수익률 {fmt_pct(float(canonical['total_return']))}, CAGR {fmt_pct(float(canonical['cagr']))}, MDD {fmt_pct(float(canonical['mdd']))}",
        f"- replay 곡선 기준 Full reference: 전략 {fmt_pct(full_ret_strategy)} vs KOSPI {fmt_pct(full_ret_kospi)}"
        + (f" vs KOSDAQ {fmt_pct(full_ret_kosdaq)}" if full_ret_kosdaq is not None else ""),
        f"- replay 곡선 기준 Official effective window({', '.join(str(y) for y in effective_years)}): 전략 {fmt_pct(eff_ret_strategy)} vs KOSPI {fmt_pct(eff_ret_kospi)}"
        + (f" vs KOSDAQ {fmt_pct(eff_ret_kosdaq)}" if eff_ret_kosdaq is not None else ""),
        "- 축/범례는 모두 누적수익률(%) 기준으로 통일",
        "",
        "## A. 거래원장표 (매수/매도/사유)",
        f"- 전체 완료거래: **{len(ledger_rows_md)}건**",
        table_md(ledger_rows_md, ["매수일", "매도일", "종목명", "수익률%", "매수사유", "매도사유"]),
        "",
        "## B. 포트폴리오 변화표",
        table_md(timeline_rows_md, ["리밸런싱일", "편입", "편출", "유지", "교체근거"]),
        "",
        "## C. 월별 보유표",
        table_md(monthly_rows_md, ["월말", "보유종목수(1~6)", "비중/보유일수"]),
        "",
        "## D. 슈퍼사이클 추적표",
        table_md(super_rows_md, ["일자", "지속점수", "꺾임신호", "청산트리거"]),
        "",
        "## 산출물",
        f"- `{OUT_REPORT.relative_to(BASE)}`",
        f"- `{OUT_EVENTS_CSV.relative_to(BASE)}`",
        f"- `{OUT_TIMELINE_CSV.relative_to(BASE)}`",
        f"- `{OUT_CHART_KOSPI.relative_to(BASE)}`",
        f"- `{OUT_CHART_KOSPI_KOSDAQ.relative_to(BASE)}`",
        "",
        "## reason 분류 기준(재계산)",
        "- buy_reason",
        "  - 턴어라운드 진입: 단기 반등 + 중기 약세/방향전환 초기",
        "  - 슈퍼사이클 지속: ma_fast > ma_slow > ma120 & ret_mid>0",
        "  - 리스크완화: 상기 2조건 외 상위점수 기반 분산편입",
        "- sell_reason",
        "  - 교체(+15% 우위): challenger_score >= incumbent_score + 0.15",
        "  - 트레일링스탑: peak 대비 -20% 하락",
        "  - 꺾임신호: ma_fast<ma_slow 또는 ret_short/ret_mid 동시 음수 구간의 교체매도",
        "  - 최종청산: 백테스트 종료 시점 일괄청산",
    ]

    OUT_REPORT.write_text("\n".join(report_lines) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "ok",
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "best_model": best_model_id,
                "verification": verification,
                "outputs": {
                    "report": str(OUT_REPORT.relative_to(BASE)),
                    "trade_events_csv": str(OUT_EVENTS_CSV.relative_to(BASE)),
                    "portfolio_timeline_csv": str(OUT_TIMELINE_CSV.relative_to(BASE)),
                    "chart_kospi": str(OUT_CHART_KOSPI.relative_to(BASE)),
                    "chart_kospi_kosdaq": str(OUT_CHART_KOSPI_KOSDAQ.relative_to(BASE)),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
