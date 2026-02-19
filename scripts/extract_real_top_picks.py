#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from pykrx import stock


@dataclass
class TradeResult:
    year: int
    code: str
    name: str
    buy_date: str
    sell_date: str
    pnl_pct: float


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


def extract_top_picks(trades_csv: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trades = pd.read_csv(trades_csv, dtype={"code": str})
    trades["rebalance_date"] = pd.to_datetime(trades["rebalance_date"])
    trades["next_rebalance_date"] = pd.to_datetime(trades["next_rebalance_date"])

    rows: list[dict] = []
    for _, r in trades.iterrows():
        code = r["code"].zfill(6)
        name = r["name"]
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
                "code": code,
                "name": name,
                "buy_date": bdt.strftime("%Y-%m-%d"),
                "sell_date": sdt.strftime("%Y-%m-%d"),
                "pnl_pct": pnl_pct,
            }
        )

    realized = pd.DataFrame(rows)
    if realized.empty:
        raise RuntimeError("No realized rows computed.")

    top_idx = realized.groupby("year")["pnl_pct"].idxmax()
    top = realized.loc[top_idx].sort_values("year").reset_index(drop=True)
    return realized, top


def to_markdown(top: pd.DataFrame) -> str:
    out = top.rename(
        columns={
            "year": "연도",
            "name": "실제 매매 종목",
            "buy_date": "매수일",
            "sell_date": "매도일",
            "pnl_pct": "수익률(%)",
        }
    )[["연도", "실제 매매 종목", "매수일", "매도일", "수익률(%)"]].copy()
    out["수익률(%)"] = out["수익률(%)"].map(lambda x: f"{x:.2f}%")

    headers = ["연도", "실제 매매 종목", "매수일", "매도일", "수익률(%)"]
    lines = [
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for _, r in out.iterrows():
        lines.append(
            f"| {r['연도']} | {r['실제 매매 종목']} | {r['매수일']} | {r['매도일']} | {r['수익률(%)']} |"
        )
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--trades-csv",
        default="invest/results/validated/stage06_highlander_trades.csv",
        help="Path to stage06_highlander_trades.csv",
    )
    ap.add_argument(
        "--output-md",
        default="reports/stage_updates/stage06/stage06_real_top_picks.md",
        help="Output markdown path",
    )
    args = ap.parse_args()

    trades_csv = Path(args.trades_csv)
    realized, top = extract_top_picks(trades_csv)

    hallucination_names = {"아난티", "써니전자"}
    names_in_log = set(pd.read_csv(trades_csv)["name"].astype(str).tolist())
    missing = sorted(hallucination_names - names_in_log)

    md_lines = []
    md_lines.append("# Stage06 Highlander 실제 매매 기반 연도별 Top Pick")
    md_lines.append("")
    md_lines.append("- 기준 데이터: `stage06_highlander_trades.csv` (실제 매매 로그)")
    md_lines.append("- 산출 방식: 매수일/매도일 종가 기준 구간 수익률(%) 계산 후, 연도별 최고값 1건 추출")
    md_lines.append("")
    md_lines.append(to_markdown(top))
    md_lines.append("")
    md_lines.append("## 할루시네이션 종목 검증")
    if len(missing) == len(hallucination_names):
        md_lines.append("- `아난티`, `써니전자` 모두 실제 로그(`stage06_highlander_trades.csv`)에 없음 ✅")
    else:
        present = sorted(hallucination_names & names_in_log)
        md_lines.append(f"- 주의: 다음 종목은 로그에 존재함: {present}")

    out_path = Path(args.output_md)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(md_lines), encoding="utf-8")

    print(to_markdown(top))
    print("\n[검증]", "아난티" in names_in_log, "써니전자" in names_in_log)
    print("[saved]", out_path)


if __name__ == "__main__":
    main()
