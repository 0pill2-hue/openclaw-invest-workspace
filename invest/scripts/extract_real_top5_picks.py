#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
from pykrx import stock


def _nearest_prices(code: str, buy_date: pd.Timestamp, sell_date: pd.Timestamp) -> tuple[pd.Timestamp, float, pd.Timestamp, float]:
    start = (buy_date - pd.Timedelta(days=7)).strftime("%Y%m%d")
    end = (sell_date + pd.Timedelta(days=7)).strftime("%Y%m%d")
    ohlcv = stock.get_market_ohlcv_by_date(start, end, code)
    if ohlcv.empty:
        raise ValueError(f"No OHLCV for code={code} between {start}~{end}")

    ohlcv = ohlcv.sort_index()

    buy_slice = ohlcv.loc[ohlcv.index >= buy_date]
    if buy_slice.empty:
        raise ValueError(f"No buy trading day on/after {buy_date.date()} for {code}")
    buy_exec_date = buy_slice.index[0]
    buy_close = float(buy_slice.iloc[0]["종가"])

    sell_slice = ohlcv.loc[ohlcv.index <= sell_date]
    if sell_slice.empty:
        raise ValueError(f"No sell trading day on/before {sell_date.date()} for {code}")
    sell_exec_date = sell_slice.index[-1]
    sell_close = float(sell_slice.iloc[-1]["종가"])

    return buy_exec_date, buy_close, sell_exec_date, sell_close


def compute_realized(trades_csv: Path) -> pd.DataFrame:
    trades = pd.read_csv(trades_csv, dtype={"code": str})
    trades["rebalance_date"] = pd.to_datetime(trades["rebalance_date"])
    trades["next_rebalance_date"] = pd.to_datetime(trades["next_rebalance_date"])

    rows: list[dict] = []
    for _, r in trades.iterrows():
        code = r["code"].zfill(6)
        buy_date = r["rebalance_date"]
        sell_date = r["next_rebalance_date"]

        try:
            bdt, bpx, sdt, spx = _nearest_prices(code, buy_date, sell_date)
        except Exception:
            continue

        pnl_pct = (spx - bpx) / bpx * 100.0
        rows.append(
            {
                "year": int(buy_date.year),
                "name": str(r["name"]),
                "buy_month": bdt.strftime("%Y-%m"),
                "pnl_pct": pnl_pct,
            }
        )

    realized = pd.DataFrame(rows)
    if realized.empty:
        raise RuntimeError("No realized rows computed.")
    return realized


def compute_top5_by_year(realized: pd.DataFrame) -> pd.DataFrame:
    realized = realized.sort_values(["year", "pnl_pct"], ascending=[True, False]).copy()
    realized["rank"] = realized.groupby("year").cumcount() + 1
    top5 = realized[realized["rank"] <= 5].copy()
    return top5


def build_top5_markdown_table(top5: pd.DataFrame) -> str:
    years = sorted(top5["year"].unique().tolist())

    headers = ["연도", "1위 (수익%)", "2위 (수익%)", "3위 (수익%)", "4위 (수익%)", "5위 (수익%)"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]

    for y in years:
        ydf = top5[top5["year"] == y].sort_values("rank")
        cells = [str(y)]
        by_rank = {int(r["rank"]): r for _, r in ydf.iterrows()}
        for rk in range(1, 6):
            if rk in by_rank:
                r = by_rank[rk]
                cells.append(f"{r['name']} ({r['pnl_pct']:.2f}%, {r['buy_month']})")
            else:
                cells.append("-")
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def compute_cum_return_and_mdd(equity_csv: Path) -> tuple[float, float]:
    eq = pd.read_csv(equity_csv)
    eq = eq.sort_values("Date").copy()

    if "ret" in eq.columns:
        curve = (1.0 + eq["ret"].astype(float)).cumprod()
    elif "equity" in eq.columns:
        curve = eq["equity"].astype(float)
    else:
        raise RuntimeError("equity_csv must contain either 'equity' or 'ret' column")

    total_return = curve.iloc[-1] - 1.0
    running_max = curve.cummax()
    drawdown = curve / running_max - 1.0
    mdd = float(drawdown.min())

    return float(total_return), mdd


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trades-csv", default="invest/results/validated/stage06_highlander_trades.csv")
    ap.add_argument("--equity-csv", default="invest/results/validated/stage06_highlander_equity.csv")
    ap.add_argument("--output-md", default="reports/stage_updates/stage06/stage06_real_top5_picks.md")
    ap.add_argument("--output-csv", default="invest/results/validated/stage06_highlander_top5_by_year.csv")
    args = ap.parse_args()

    trades_csv = Path(args.trades_csv)
    equity_csv = Path(args.equity_csv)

    realized = compute_realized(trades_csv)
    top5 = compute_top5_by_year(realized)
    top5.to_csv(args.output_csv, index=False, encoding="utf-8-sig")

    total_return, mdd = compute_cum_return_and_mdd(equity_csv)

    md_lines = [
        "# Stage06 Highlander 실제 매매 기반 연도별 Top 5",
        "",
        f"- 기준 로그: `{trades_csv}`",
        "- 산출 방식: 매수일/매도일 종가 기반 개별 트레이드 실현손익(%) 계산 후, 연도별 내림차순 Top 5 추출",
        "",
        build_top5_markdown_table(top5),
        "",
        "## 요약",
        f"- 10년 총 누적 수익률(재계산): **{total_return * 100:.2f}%**",
        f"- MDD(재계산): **{mdd * 100:.2f}%**",
    ]

    out_md = Path(args.output_md)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text("\n".join(md_lines), encoding="utf-8")

    print(build_top5_markdown_table(top5))
    print(f"\n[요약] 총 누적 수익률={total_return * 100:.2f}% / MDD={mdd * 100:.2f}%")
    print(f"[saved] {out_md}")
    print(f"[saved] {args.output_csv}")


if __name__ == "__main__":
    main()
