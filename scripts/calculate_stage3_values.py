import json
from pathlib import Path

import numpy as np
import pandas as pd

SRC_BASE = Path("invest/data/clean/production")
DST_BASE = Path("invest/data/value/stage3")
REPORT_DIR = Path("reports/stage_updates")


def winsorize_series(s: pd.Series, lower_q=0.01, upper_q=0.99) -> pd.Series:
    if s.dropna().empty:
        return s
    lo = s.quantile(lower_q)
    hi = s.quantile(upper_q)
    return s.clip(lower=lo, upper=hi)


def adaptive_ema(series: pd.Series, base_span=20, vol_window=20) -> pd.Series:
    # 변동성 비율 기반 단순 adaptive span
    ret = series.pct_change(fill_method=None).abs()
    vol = ret.rolling(vol_window, min_periods=5).mean()
    baseline = vol.rolling(120, min_periods=20).mean()

    out = []
    prev = np.nan
    for i, x in enumerate(series.values):
        if np.isnan(x):
            out.append(prev)
            continue

        v = vol.iloc[i]
        b = baseline.iloc[i]
        ratio = 1.0 if (pd.isna(v) or pd.isna(b) or b == 0) else float(v / b)

        # 고변동(>1.5)면 빠르게(span 축소), 저변동(<0.7)이면 느리게(span 확대)
        if ratio > 1.5:
            span = max(8, int(base_span * 0.6))
        elif ratio < 0.7:
            span = min(40, int(base_span * 1.6))
        else:
            span = base_span

        alpha = 2.0 / (span + 1.0)
        prev = x if np.isnan(prev) else (alpha * x + (1 - alpha) * prev)
        out.append(prev)

    return pd.Series(out, index=series.index)


def calc_value_factors(df: pd.DataFrame) -> pd.DataFrame:
    x = df.copy()
    x.columns = [str(c).strip() for c in x.columns]

    if "Date" not in x.columns:
        if "date" in x.columns:
            x = x.rename(columns={"date": "Date"})
        elif "날짜" in x.columns:
            x = x.rename(columns={"날짜": "Date"})

    for c in ["Open", "High", "Low", "Close", "Volume"]:
        if c in x.columns:
            x[c] = pd.to_numeric(x[c], errors="coerce")

    x["Date"] = pd.to_datetime(x["Date"], errors="coerce")
    x = x.dropna(subset=["Date", "Close"]).sort_values("Date").reset_index(drop=True)

    # 1) Momentum: raw -> EMA(20 adaptive)
    mom_raw = x["Close"].pct_change(20, fill_method=None)
    x["VAL_MOM_20"] = adaptive_ema(mom_raw, base_span=20)

    # 2) Supply proxy(가격기반 대체): 일일수익률 절대치 역점수 + median(5)+ema(10)
    ret1 = x["Close"].pct_change(fill_method=None)
    flow_proxy = ret1.replace([np.inf, -np.inf], np.nan)
    flow_med = flow_proxy.rolling(5, min_periods=3).median()
    x["VAL_FLOW_10"] = flow_med.ewm(span=10, adjust=False).mean()

    # 3) Liquidity: turnover winsor
    x["VAL_TURNOVER"] = x["Close"] * x.get("Volume", 0)
    x["VAL_LIQ_WIN"] = winsorize_series(x["VAL_TURNOVER"], 0.025, 0.975)

    # 4) Risk: ATR20 winsor + EMA10 (낮을수록 좋음)
    hl = x["High"] - x["Low"] if "High" in x.columns and "Low" in x.columns else pd.Series(np.nan, index=x.index)
    hc = (x["High"] - x["Close"].shift(1)).abs() if "High" in x.columns else pd.Series(np.nan, index=x.index)
    lc = (x["Low"] - x["Close"].shift(1)).abs() if "Low" in x.columns else pd.Series(np.nan, index=x.index)
    tr = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    atr20 = tr.rolling(20, min_periods=10).mean()
    atr20_w = winsorize_series(atr20, 0.01, 0.99)
    x["VAL_RISK_10"] = atr20_w.ewm(span=10, adjust=False).mean()

    # z-score normalize (rolling)
    def zroll(s, w=120):
        mu = s.rolling(w, min_periods=20).mean()
        sd = s.rolling(w, min_periods=20).std()
        return (s - mu) / sd.replace(0, np.nan)

    z_m = zroll(x["VAL_MOM_20"])
    z_f = zroll(x["VAL_FLOW_10"])
    z_l = zroll(x["VAL_LIQ_WIN"])
    z_r = zroll(x["VAL_RISK_10"]) * -1.0

    # 통합 스코어
    x["VALUE_SCORE_RAW"] = 0.35 * z_m + 0.25 * z_f + 0.20 * z_l + 0.20 * z_r
    x["VALUE_SCORE"] = adaptive_ema(x["VALUE_SCORE_RAW"], base_span=10)

    return x


def run_value_pipeline():
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    summary = {"processed": 0, "skipped": 0, "errors": 0, "markets": {}}

    for market in ["kr", "us"]:
        src = SRC_BASE / market / "ohlcv"
        dst = DST_BASE / market / "ohlcv"
        dst.mkdir(parents=True, exist_ok=True)

        if not src.exists():
            summary["markets"][market] = {"processed": 0, "skipped": 0, "errors": 0}
            continue

        p = s = e = 0
        for f in src.glob("*.csv"):
            try:
                df = pd.read_csv(f)
                if len(df) < 30:
                    s += 1
                    continue
                out = calc_value_factors(df)
                cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume", "VAL_MOM_20", "VAL_FLOW_10", "VAL_LIQ_WIN", "VAL_RISK_10", "VALUE_SCORE_RAW", "VALUE_SCORE"] if c in out.columns]
                out[cols].to_csv(dst / f.name, index=False)
                p += 1
            except Exception:
                e += 1

        summary["markets"][market] = {"processed": p, "skipped": s, "errors": e}
        summary["processed"] += p
        summary["skipped"] += s
        summary["errors"] += e

    ts = pd.Timestamp.now().strftime("%Y%m%d_%H%M%S")
    report = REPORT_DIR / f"STAGE3_VALUE_RUN_{ts}.json"
    report.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"STAGE3_DONE report={report}")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    run_value_pipeline()
