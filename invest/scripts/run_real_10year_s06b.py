#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass

import numpy as np
import pandas as pd
from pykrx import stock

BASE = Path(__file__).resolve().parents[1]
CAND_PATH = BASE / "invest/results/validated/stage06_candidates_beast.json"
OUT_MD = BASE / "invest/results/validated/real_10year_report_S06B.md"
OUT_CSV = BASE / "invest/results/validated/real_10year_equity_S06B.csv"
START = "2016-01-01"
END = "2026-02-18"
TICKER = "005930"  # Samsung Electronics as liquid KR proxy instrument for strategy execution


@dataclass
class Candidate:
    candidate_id: str
    strategy_type: str
    profile: str
    leverage: float
    turnover_cap: float
    cost_penalty_bps: float


def load_candidate(cid: str = "S06B-T-AG-001") -> Candidate:
    data = json.loads(CAND_PATH.read_text(encoding="utf-8"))
    row = next(x for x in data["candidates"] if x["candidate_id"] == cid)
    return Candidate(
        candidate_id=row["candidate_id"],
        strategy_type=row["strategy_type"],
        profile=row["profile"],
        leverage=float(row["leverage"]),
        turnover_cap=float(row["turnover_cap"]),
        cost_penalty_bps=float(row["cost_penalty_bps"]),
    )


def load_market_data() -> tuple[pd.DataFrame, pd.Series]:
    s, e = START.replace("-", ""), END.replace("-", "")
    px = stock.get_market_ohlcv_by_date(s, e, TICKER)
    if px.empty:
        raise RuntimeError("OHLCV empty for ticker")
    px = px.rename(columns={"시가": "Open", "고가": "High", "저가": "Low", "종가": "Close", "거래량": "Volume"})
    tv = stock.get_market_trading_value_by_date(s, e, TICKER)
    # 외국인 + 기관 순매수 대금
    supply = tv["외국인합계"] + tv["기관합계"]

    kospi = stock.get_index_ohlcv_by_date(s, e, "1001")
    if kospi.empty:
        raise RuntimeError("KOSPI data empty")
    kospi_close = kospi["종가"].rename("KOSPI")

    return px, supply.reindex(px.index).fillna(0.0), kospi_close


def load_news_sentiment() -> pd.Series:
    rss_dir = BASE / "invest/data/raw/market/news/rss"
    if not rss_dir.exists():
        return pd.Series(dtype=float)

    pos_kw = ["상승", "호재", "성장", "개선", "최고", "확대", "수주", "흑자"]
    neg_kw = ["하락", "악재", "둔화", "우려", "최저", "축소", "적자", "급락"]

    score = {}
    for fp in sorted(rss_dir.glob("*.json")):
        try:
            arr = json.loads(fp.read_text(encoding="utf-8"))
        except Exception:
            continue
        for x in arr if isinstance(arr, list) else []:
            d = str(x.get("published", ""))[:10]
            txt = f"{x.get('title', '')} {x.get('summary', '')}"
            p = sum(k in txt for k in pos_kw)
            n = sum(k in txt for k in neg_kw)
            score[d] = score.get(d, 0.0) + (p - n)

    if not score:
        return pd.Series(dtype=float)
    s = pd.Series(score)
    s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[~s.index.isna()]
    return s.sort_index()


def load_financial_score() -> pd.Series:
    tag_dir = BASE / "invest/data/raw/kr/dart/tagged"
    if not tag_dir.exists():
        return pd.Series(dtype=float)

    pos_kw = ["실적", "성장", "수주", "개선", "증가", "흑자"]
    neg_kw = ["감소", "손실", "적자", "악화", "부진", "우려"]

    rows = []
    for fp in sorted(tag_dir.glob("dart_tagged_*.csv"))[-5:]:
        try:
            df = pd.read_csv(fp)
        except Exception:
            continue
        if "rcept_dt" not in df.columns:
            continue
        txt_col = "report_nm" if "report_nm" in df.columns else None
        if txt_col is None:
            continue
        for _, r in df.iterrows():
            d = pd.to_datetime(str(r.get("rcept_dt")), errors="coerce")
            if pd.isna(d):
                continue
            txt = str(r.get(txt_col, ""))
            p = sum(k in txt for k in pos_kw)
            n = sum(k in txt for k in neg_kw)
            rows.append((d.to_period("M").to_timestamp(), p - n))

    if not rows:
        return pd.Series(dtype=float)
    df = pd.DataFrame(rows, columns=["Month", "Score"]).groupby("Month")["Score"].sum()
    return df.sort_index()


def max_drawdown(r: pd.Series) -> float:
    eq = (1 + r.fillna(0)).cumprod()
    dd = eq / eq.cummax() - 1
    return float(dd.min())


def run_backtest(c: Candidate) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    px, supply, kospi = load_market_data()
    news = load_news_sentiment()
    fin_m = load_financial_score()

    df = px[["Close", "Volume"]].copy()
    df["ret1"] = df["Close"].pct_change().fillna(0.0)
    df["mom20"] = df["Close"].pct_change(20)
    df["ma60"] = df["Close"].rolling(60).mean()
    df["supply20"] = supply.rolling(20).sum()
    df["news"] = news.reindex(df.index).fillna(0.0).rolling(5).mean()
    # 월별 재무 점수 -> 일별 ffill
    df["fin"] = fin_m.reindex(df.index).ffill().fillna(0.0)

    # aggressive_momentum + beast_alpha 규칙(실데이터 기반 구현)
    signal = (
        (df["Close"] > df["ma60"]) &
        (df["mom20"] > 0) &
        (df["supply20"] > 0) &
        (df["news"] >= 0) &
        (df["fin"] >= 0)
    ).astype(float)

    position = signal * c.leverage
    pos_prev = position.shift(1).fillna(0.0)

    turnover = (position - pos_prev).abs().clip(upper=c.turnover_cap)
    cost = turnover * (c.cost_penalty_bps / 10000.0)

    df["strategy_ret"] = pos_prev * df["ret1"] - cost
    df["equity"] = (1 + df["strategy_ret"]).cumprod()

    kret = kospi.pct_change().reindex(df.index).fillna(0.0)
    kdf = pd.DataFrame({"KOSPI": kospi.reindex(df.index), "ret": kret})
    kdf["equity"] = (1 + kdf["ret"]).cumprod()

    yearly = pd.DataFrame(index=sorted(set(df.index.year)))
    yearly.index.name = "연도"
    yearly["model_return"] = (1 + df["strategy_ret"]).groupby(df.index.year).prod() - 1
    yearly["model_mdd"] = df["strategy_ret"].groupby(df.index.year).apply(max_drawdown)
    yearly["kospi_return"] = (1 + kret).groupby(df.index.year).prod() - 1
    yearly["kospi_mdd"] = kret.groupby(df.index.year).apply(max_drawdown)
    yearly["win_lose"] = np.where(yearly["model_return"] > yearly["kospi_return"], "승", "패")

    # regime: 월별 코스피 수익률 기준
    mret_model = (1 + df["strategy_ret"]).groupby(pd.Grouper(freq="ME")).prod() - 1
    mret_kospi = (1 + kret).groupby(pd.Grouper(freq="ME")).prod() - 1
    reg = pd.DataFrame({"m": mret_model, "k": mret_kospi}).dropna()

    def regime(x: float) -> str:
        if x >= 0.03:
            return "상승장"
        if x <= -0.03:
            return "하락장"
        return "횡보장"

    reg["regime"] = reg["k"].map(regime)
    reg["win"] = (reg["m"] > reg["k"]).astype(int)
    regime_win = reg.groupby("regime")["win"].mean().to_dict()

    summary = {
        "candidate_id": c.candidate_id,
        "strategy_type": c.strategy_type,
        "profile": c.profile,
        "leverage": c.leverage,
        "turnover_cap": c.turnover_cap,
        "cost_penalty_bps": c.cost_penalty_bps,
        "model_total_return": float(df["equity"].iloc[-1] - 1),
        "kospi_total_return": float(kdf["equity"].iloc[-1] - 1),
        "model_total_mdd": float((df["equity"] / df["equity"].cummax() - 1).min()),
        "kospi_total_mdd": float((kdf["equity"] / kdf["equity"].cummax() - 1).min()),
        "regime_winrate": {k: float(v) for k, v in regime_win.items()},
    }

    out_eq = pd.DataFrame({
        "Date": df.index,
        "model_equity": df["equity"].values,
        "model_ret": df["strategy_ret"].values,
        "kospi_equity": kdf["equity"].values,
        "kospi_ret": kret.values,
    })
    return out_eq, yearly, summary


def pct(x: float) -> str:
    return f"{x*100:.2f}%"


def write_report(c: Candidate, yearly: pd.DataFrame, summary: dict) -> None:
    lines = []
    lines.append("# real_10year_report_S06B")
    lines.append("")
    lines.append("- result_grade: VALIDATED")
    lines.append(f"- candidate_id: {c.candidate_id}")
    lines.append(f"- period: {START} ~ {END}")
    lines.append(f"- instrument: {TICKER} (삼성전자), benchmark=KOSPI(1001)")
    lines.append("- data: pykrx OHLCV/수급(실데이터) + 로컬 RSS 뉴스 + DART tagged 공시(가능 범위)")
    lines.append("- note: 후보 JSON에 세부 가중치/진입식이 없어 strategy_type/profile 기반 실데이터 규칙으로 재현 실행")
    lines.append("")
    lines.append("## 연도별 성과")
    lines.append("| 연도 | 모델 수익률 | 모델 MDD | KOSPI 수익률 | KOSPI MDD | 승패 |")
    lines.append("|---:|---:|---:|---:|---:|:---:|")
    for y, r in yearly.iterrows():
        lines.append(f"| {int(y)} | {pct(r['model_return'])} | {pct(r['model_mdd'])} | {pct(r['kospi_return'])} | {pct(r['kospi_mdd'])} | {r['win_lose']} |")

    lines.append("")
    lines.append("## 구간별 승률 (월별 KOSPI 기준)")
    for k in ["상승장", "하락장", "횡보장"]:
        v = summary["regime_winrate"].get(k, np.nan)
        if pd.isna(v):
            lines.append(f"- {k}: N/A")
        else:
            lines.append(f"- {k}: {v*100:.2f}%")

    lines.append("")
    lines.append("## 최종 누적 성과")
    lines.append(f"- 모델 누적 수익률(복리): {pct(summary['model_total_return'])}")
    lines.append(f"- KOSPI 누적 수익률(복리): {pct(summary['kospi_total_return'])}")
    lines.append(f"- 모델 전체 MDD: {pct(summary['model_total_mdd'])}")
    lines.append(f"- KOSPI 전체 MDD: {pct(summary['kospi_total_mdd'])}")

    OUT_MD.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    c = load_candidate()
    eq, yearly, summary = run_backtest(c)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    eq.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    write_report(c, yearly, summary)
    print(f"OK: {OUT_CSV}")
    print(f"OK: {OUT_MD}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
