#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[1]
RESULT_DIR = BASE / "invest/results/validated"
OHLCV_DIR = BASE / "invest/data/clean/production/kr/ohlcv"

IN_TRADES = RESULT_DIR / "stage06_highlander_trades.csv"
IN_BENCH_YEARLY = RESULT_DIR / "stage06_highlander_yearly_fullperiod.csv"

OUT_TRADES_PURGED = RESULT_DIR / "stage06_highlander_trades_manual_purged.csv"
OUT_PURGED_ROWS = RESULT_DIR / "stage06_highlander_purged_rows.csv"
OUT_EQUITY_PURGED = RESULT_DIR / "stage06_highlander_equity_manual_purged.csv"
OUT_YEARLY_PURGED = RESULT_DIR / "stage06_highlander_yearly_manual_purged.csv"
OUT_SUMMARY = RESULT_DIR / "stage06_highlander_manual_purge_summary.json"

TRADE_COST = 0.0035
BASELINE_TOTAL_RETURN = 820.6823963491299

# 명시적 강제 삭제 대상
KILL_CODE_SET = {
    # 남북경협
    "025980",  # 아난티
    "045390",  # 대아티아이
    "007110",  # 일신석재
    "033340",  # 좋은사람들
    "017800",  # 현대엘리베이
    "064350",  # 현대로템 (단, 방산 실적 구간 예외)
    "009270",  # 신원
    # 정치테마
    "004770",  # 써니전자
    "053800",  # 안랩
    "008350",  # 남선알미늄
    "084680",  # 이월드
    "007860",  # 서연
    "004830",  # 덕성
}

# 이름 기반 추가 삭제 키워드(초전도체 등)
KILL_NAME_KEYWORDS = [
    "아난티",
    "대아티아이",
    "일신석재",
    "좋은사람들",
    "현대엘리베이",
    "현대로템",
    "신원",
    "써니전자",
    "안랩",
    "남선알미늄",
    "이월드",
    "서연",
    "덕성",
    "신성델타테크",
    "초전도",
]

# 현대로템 방산 실적 구간 예외 규칙(확장 가능)
# 현재 데이터는 reason_tag 기반으로만 판단 가능하므로 방산 태그가 있으면 보존
DEFENSE_TAG_KEYWORDS = ["Defense", "방산"]


def load_close_series(code: str) -> pd.Series:
    fp = OHLCV_DIR / f"{code}.csv"
    if not fp.exists():
        return pd.Series(dtype=float)
    df = pd.read_csv(fp, usecols=["Date", "Close"])
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.dropna(subset=["Date", "Close"]).sort_values("Date")
    return pd.Series(df["Close"].astype(float).values, index=df["Date"])


def equity_from_trades(trades: pd.DataFrame) -> tuple[pd.Series, pd.DataFrame]:
    if trades.empty:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    trade_dates = sorted(pd.to_datetime(trades["rebalance_date"]).unique())
    if len(trade_dates) < 2:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    code_pool = sorted(set(trades["code"].astype(str).tolist()))
    close_map = {c: load_close_series(c) for c in code_pool}

    prev_weights: dict[str, float] = {}
    daily: list[tuple[pd.Timestamp, float]] = []

    for i in range(len(trade_dates) - 1):
        d0 = pd.Timestamp(trade_dates[i])
        d1 = pd.Timestamp(trade_dates[i + 1])

        snap = trades[pd.to_datetime(trades["rebalance_date"]) == d0]
        active = snap["code"].astype(str).tolist()
        active = sorted(set(active))

        if active:
            w = 1.0 / len(active)
            weights = {c: w for c in active}
        else:
            weights = {}

        turnover = 0.0
        for c in set(prev_weights) | set(weights):
            turnover += abs(weights.get(c, 0.0) - prev_weights.get(c, 0.0))

        month_days = pd.date_range(d0 + pd.Timedelta(days=1), d1, freq="B")
        month_rets: list[float] = []
        for day in month_days:
            r = 0.0
            for c, ww in weights.items():
                s = close_map.get(c)
                if s is None or day not in s.index:
                    continue
                loc = s.index.get_loc(day)
                if isinstance(loc, slice) or loc == 0:
                    continue
                prev_day = s.index[loc - 1]
                pr, cr = float(s.loc[prev_day]), float(s.loc[day])
                if pr <= 0:
                    continue
                r += ww * (cr / pr - 1)
            month_rets.append(r)

        if month_rets:
            month_rets[0] -= turnover * TRADE_COST
            daily.extend(list(zip(month_days, month_rets)))

        prev_weights = weights

    if not daily:
        return pd.Series(dtype=float), pd.DataFrame(columns=["Date", "ret", "equity"])

    r = pd.Series({d: rr for d, rr in daily}).sort_index()
    eq = (1 + r.fillna(0)).cumprod()
    eq_df = pd.DataFrame({"Date": eq.index, "ret": r.values, "equity": eq.values})
    return r, eq_df


def yearly_from_returns(r: pd.Series, bench_yearly: pd.DataFrame) -> pd.DataFrame:
    if r.empty:
        return pd.DataFrame(columns=["year", "model_return", "model_mdd", "kospi_return", "kospi_mdd", "kosdaq_return", "kosdaq_mdd"])

    rows = []
    for y in sorted(set(r.index.year)):
        ry = r[r.index.year == y]
        eq = (1 + ry.fillna(0)).cumprod()
        mret = float(eq.iloc[-1] - 1) if not eq.empty else 0.0
        mmdd = float((eq / eq.cummax() - 1).min()) if not eq.empty else 0.0

        b = bench_yearly[bench_yearly["year"] == y]
        if b.empty:
            kospi_r = kospi_mdd = kosdaq_r = kosdaq_mdd = 0.0
        else:
            row = b.iloc[0]
            kospi_r = float(row["kospi_return"])
            kospi_mdd = float(row["kospi_mdd"])
            kosdaq_r = float(row["kosdaq_return"])
            kosdaq_mdd = float(row["kosdaq_mdd"])

        rows.append(
            {
                "year": int(y),
                "model_return": mret,
                "model_mdd": mmdd,
                "kospi_return": kospi_r,
                "kospi_mdd": kospi_mdd,
                "kosdaq_return": kosdaq_r,
                "kosdaq_mdd": kosdaq_mdd,
            }
        )
    return pd.DataFrame(rows)


def should_keep_rotem(row: pd.Series) -> bool:
    code = str(row.get("code", "")).zfill(6)
    if code != "064350":
        return False
    reason = str(row.get("reason_tag", ""))
    return any(k.lower() in reason.lower() for k in DEFENSE_TAG_KEYWORDS)


def main() -> int:
    trades = pd.read_csv(IN_TRADES, dtype={"code": str})
    trades["code"] = trades["code"].astype(str).str.zfill(6)
    trades["name"] = trades["name"].astype(str)
    bench_yearly = pd.read_csv(IN_BENCH_YEARLY)

    name_hit = trades["name"].apply(lambda n: any(k in n for k in KILL_NAME_KEYWORDS))
    code_hit = trades["code"].isin(KILL_CODE_SET)
    kill_mask = name_hit | code_hit

    if "064350" in set(trades.loc[kill_mask, "code"].tolist()):
        keep_rotem_mask = trades.apply(should_keep_rotem, axis=1)
        kill_mask = kill_mask & (~keep_rotem_mask)

    purged_rows = trades[kill_mask].copy()
    kept_trades = trades[~kill_mask].copy()

    purged_rows.to_csv(OUT_PURGED_ROWS, index=False, encoding="utf-8-sig")
    kept_trades.to_csv(OUT_TRADES_PURGED, index=False, encoding="utf-8-sig")

    baseline_pct = BASELINE_TOTAL_RETURN * 100

    if purged_rows.empty:
        # 삭제 거래가 없으면 성과 불변: 기존 validated 산출을 그대로 사용
        src_eq = RESULT_DIR / "stage06_highlander_equity.csv"
        if src_eq.exists():
            eq_df = pd.read_csv(src_eq)
        else:
            eq_df = pd.DataFrame(columns=["Date", "ret", "equity"])
        eq_df.to_csv(OUT_EQUITY_PURGED, index=False, encoding="utf-8-sig")

        yearly = bench_yearly.copy()
        yearly.to_csv(OUT_YEARLY_PURGED, index=False, encoding="utf-8-sig")

        total_ret = BASELINE_TOTAL_RETURN
    else:
        r, eq_df = equity_from_trades(kept_trades)
        eq_df.to_csv(OUT_EQUITY_PURGED, index=False, encoding="utf-8-sig")

        yearly = yearly_from_returns(r, bench_yearly)
        yearly.to_csv(OUT_YEARLY_PURGED, index=False, encoding="utf-8-sig")

        total_ret = float((1 + r.fillna(0)).prod() - 1) if not r.empty else 0.0

    purged_pct = total_ret * 100

    removed_symbols = []
    if not purged_rows.empty:
        removed_symbols = (
            purged_rows.groupby(["code", "name"]).size().reset_index(name="count").sort_values("count", ascending=False).to_dict(orient="records")
        )

    summary = {
        "result_grade": "VALIDATED",
        "input_trades": str(IN_TRADES.relative_to(BASE)),
        "baseline_total_return_10y": BASELINE_TOTAL_RETURN,
        "baseline_total_return_pct": baseline_pct,
        "purged_total_return_10y": total_ret,
        "purged_total_return_pct": purged_pct,
        "removed_trade_rows": int(len(purged_rows)),
        "removed_symbols": removed_symbols,
        "kill_list_codes": sorted(KILL_CODE_SET),
        "kill_list_name_keywords": KILL_NAME_KEYWORDS,
        "files": {
            "purged_trades": str(OUT_TRADES_PURGED.relative_to(BASE)),
            "purged_rows": str(OUT_PURGED_ROWS.relative_to(BASE)),
            "equity_purged": str(OUT_EQUITY_PURGED.relative_to(BASE)),
            "yearly_purged": str(OUT_YEARLY_PURGED.relative_to(BASE)),
        },
    }

    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
