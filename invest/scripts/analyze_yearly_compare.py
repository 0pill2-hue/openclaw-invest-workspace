#!/usr/bin/env python3
"""
S06B-T-AG-001 yearly return comparison vs KOSPI/KOSDAQ.

NOTE:
- Repository does not contain daily backtest log for S06B-T-AG-001.
- Uses existing backtest annual output (my_algo_return) as proxy model series.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import pandas as pd
from pykrx import stock


MODEL_ID = "S06B-T-AG-001"
DEFAULT_START = "2016-01-01"
DEFAULT_END = "2026-02-18"
MODEL_PROXY_CSV = Path("invest/results/test/annual_returns_comparison_20260218_010620.csv")
OUT_DIR = Path("invest/results/test")


@dataclass
class RunResult:
    table: pd.DataFrame
    summary: Dict[str, float]
    markdown: str
    out_csv: Path
    out_md: Path


def yearly_from_index(start: str, end: str, code: str) -> pd.Series:
    s = start.replace("-", "")
    e = end.replace("-", "")
    df = stock.get_index_ohlcv_by_date(s, e, code)
    if df.empty:
        raise RuntimeError(f"index data empty for code={code}")
    daily = df["종가"].pct_change().dropna()
    yearly = (1.0 + daily).groupby(daily.index.year).prod() - 1.0
    yearly.index = yearly.index.astype(int)
    return yearly


def load_model_proxy() -> pd.Series:
    if not MODEL_PROXY_CSV.exists():
        raise FileNotFoundError(f"model proxy csv not found: {MODEL_PROXY_CSV}")

    rows = []
    with MODEL_PROXY_CSV.open("r", encoding="utf-8-sig") as f:
        for line in f:
            if line.startswith("#") or not line.strip():
                continue
            rows.append(line)

    from io import StringIO

    df = pd.read_csv(StringIO("".join(rows)))
    if "year" not in df.columns or "my_algo_return" not in df.columns:
        raise RuntimeError("proxy csv format mismatch")
    s = pd.Series(df["my_algo_return"].values / 100.0, index=df["year"].astype(int), name="model_return")
    return s


def make_table(model: pd.Series, kospi: pd.Series, kosdaq: pd.Series) -> pd.DataFrame:
    idx = sorted(set(model.index) | set(kospi.index) | set(kosdaq.index))
    out = pd.DataFrame(index=idx)
    out.index.name = "연도"
    out["모델수익률"] = model
    out["코스피"] = kospi
    out["코스닥"] = kosdaq

    def win_lose(r):
        if pd.isna(r["모델수익률"]) or pd.isna(r["코스피"]) or pd.isna(r["코스닥"]):
            return "N/A"
        return "승" if (r["모델수익률"] > r["코스피"] and r["모델수익률"] > r["코스닥"]) else "패"

    out["승패여부"] = out.apply(win_lose, axis=1)
    return out


def pct(x: float) -> str:
    if pd.isna(x):
        return "-"
    return f"{x*100:.2f}%"


def to_markdown(table: pd.DataFrame, summary: Dict[str, float], start: str, end: str) -> str:
    md = []
    md.append(f"# 연도별 수익률 비교 ({MODEL_ID})")
    md.append("")
    md.append(f"- 기간: {start} ~ {end}")
    md.append("- 모델 데이터: `invest/results/test/annual_returns_comparison_20260218_010620.csv`의 `my_algo_return` 프록시")
    md.append("- 벤치마크: KOSPI(1001), KOSDAQ(2001) 일별 종가 기반 연복리 수익률")
    md.append("")
    md.append("| 연도 | 모델수익률 | 코스피 | 코스닥 | 승패여부 |")
    md.append("|---:|---:|---:|---:|:---:|")
    for y, r in table.iterrows():
        md.append(f"| {int(y)} | {pct(r['모델수익률'])} | {pct(r['코스피'])} | {pct(r['코스닥'])} | {r['승패여부']} |")

    md.append("")
    md.append("## 요약 (총 누적 수익률)")
    md.append(f"- 모델: {summary['model_total']*100:.2f}%")
    md.append(f"- KOSPI: {summary['kospi_total']*100:.2f}%")
    md.append(f"- KOSDAQ: {summary['kosdaq_total']*100:.2f}%")
    return "\n".join(md)


def run(start: str, end: str) -> RunResult:
    model = load_model_proxy()
    kospi = yearly_from_index(start, end, "1001")
    kosdaq = yearly_from_index(start, end, "2001")

    table = make_table(model, kospi, kosdaq)

    model_common = table["모델수익률"].dropna()
    ks_common = table.loc[model_common.index, "코스피"]
    kq_common = table.loc[model_common.index, "코스닥"]

    summary = {
        "model_total": float((1.0 + model_common).prod() - 1.0),
        "kospi_total": float((1.0 + ks_common).prod() - 1.0),
        "kosdaq_total": float((1.0 + kq_common).prod() - 1.0),
    }

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    out_csv = OUT_DIR / f"yearly_compare_{MODEL_ID}_{ts}.csv"
    out_md = OUT_DIR / f"yearly_compare_{MODEL_ID}_{ts}.md"

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_df = table.copy()
    save_df.insert(0, "result_grade", "DRAFT")
    save_df.to_csv(out_csv, encoding="utf-8-sig")

    md = to_markdown(table, summary, start, end)
    out_md.write_text(md, encoding="utf-8")

    return RunResult(table=table, summary=summary, markdown=md, out_csv=out_csv, out_md=out_md)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--start", default=DEFAULT_START)
    p.add_argument("--end", default=DEFAULT_END)
    args = p.parse_args()

    res = run(args.start, args.end)
    print(res.markdown)
    print("\n[OUTPUT]")
    print(res.out_csv)
    print(res.out_md)


if __name__ == "__main__":
    main()
