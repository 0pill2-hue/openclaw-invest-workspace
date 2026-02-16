import os
import json
import pandas as pd
from datetime import datetime

DATA_OHLCV = "invest/data/ohlcv"
DATA_SUPPLY = "invest/data/supply"
STOCK_LIST = "invest/data/master/kr_stock_list.csv"
QUERY_MAX_CODES = int(os.environ.get("QUERY_MAX_CODES", "800"))


def _load_ohlcv(code):
    path = os.path.join(DATA_OHLCV, f"{code}.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _load_supply(code):
    path = os.path.join(DATA_SUPPLY, f"{code}_supply.csv")
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    # expected columns: 날짜, 기관합계, 기타법인, 개인, 외국인합계
    cols = df.columns.tolist()
    df.columns = ["Date", "Inst", "Corp", "Indiv", "Foreign", "Total"][:len(cols)]
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def _load_stock_list():
    if not os.path.exists(STOCK_LIST):
        return None
    df = pd.read_csv(STOCK_LIST)
    # Standardize code col
    if "Code" in df.columns:
        df["Code"] = df["Code"].astype(str).str.zfill(6)
    return df


def _iter_candidate_codes(data_dir, suffix):
    """
    Avoid full directory scans by capping candidate universe.
    Priority: stock-list order (stable) -> filesystem fallback.
    """
    stock_list = _load_stock_list()
    yielded = 0
    seen = set()

    if stock_list is not None and "Code" in stock_list.columns:
        for code in stock_list["Code"].astype(str):
            code = code.zfill(6)
            path = os.path.join(data_dir, f"{code}{suffix}")
            if os.path.exists(path):
                yield code
                seen.add(code)
                yielded += 1
                if QUERY_MAX_CODES > 0 and yielded >= QUERY_MAX_CODES:
                    return

    # fallback: remaining files from directory
    if os.path.exists(data_dir):
        for fname in os.listdir(data_dir):
            if not fname.endswith(suffix):
                continue
            code = fname[: -len(suffix)]
            if code in seen:
                continue
            yield code
            yielded += 1
            if QUERY_MAX_CODES > 0 and yielded >= QUERY_MAX_CODES:
                return


def query_foreign_net_buy(start, end, top_n=10):
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    results = []
    if not os.path.exists(DATA_SUPPLY):
        return results
    for code in _iter_candidate_codes(DATA_SUPPLY, "_supply.csv"):
        df = _load_supply(code)
        if df is None:
            continue
        m = df[(df["Date"] >= start) & (df["Date"] <= end)]
        if m.empty:
            continue
        net = m["Foreign"].sum()
        results.append({"code": code, "net_foreign": float(net)})
    results.sort(key=lambda x: x["net_foreign"], reverse=True)
    return results[:top_n]


def query_momentum_top(start, end, top_n=10, min_turnover=None):
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    results = []
    if not os.path.exists(DATA_OHLCV):
        return results
    for code in _iter_candidate_codes(DATA_OHLCV, ".csv"):
        df = _load_ohlcv(code)
        if df is None:
            continue
        m = df[(df["Date"] >= start) & (df["Date"] <= end)]
        if m.empty:
            continue
        # liquidity filter by avg turnover
        if min_turnover is not None:
            avg_turnover = (m["Close"] * m["Volume"]).mean()
            if avg_turnover < min_turnover:
                continue
        # simple momentum: end close / start close - 1
        m = m.sort_values("Date")
        start_px = m.iloc[0]["Close"]
        end_px = m.iloc[-1]["Close"]
        if start_px == 0:
            continue
        mom = (end_px / start_px) - 1
        results.append({"code": code, "momentum": float(mom)})
    results.sort(key=lambda x: x["momentum"], reverse=True)
    return results[:top_n]


def query_sector_summary(start, end):
    if not os.path.exists(DATA_OHLCV):
        return []
    stock_list = _load_stock_list()
    if stock_list is None or "Code" not in stock_list.columns:
        return []
    # sector info may be unavailable in KRX listing
    if "Sector" in stock_list.columns:
        sector_col = "Sector"
    elif "Industry" in stock_list.columns:
        sector_col = "Industry"
    else:
        return []
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    rows = []
    for code in _iter_candidate_codes(DATA_OHLCV, ".csv"):
        df = _load_ohlcv(code)
        if df is None:
            continue
        m = df[(df["Date"] >= start) & (df["Date"] <= end)]
        if m.empty:
            continue
        m = m.sort_values("Date")
        start_px = m.iloc[0]["Close"]
        end_px = m.iloc[-1]["Close"]
        if start_px == 0:
            continue
        mom = (end_px / start_px) - 1
        rows.append({"code": code, "momentum": mom})
    mom_df = pd.DataFrame(rows)
    if mom_df.empty:
        return []
    merged = mom_df.merge(stock_list[["Code", sector_col]], left_on="code", right_on="Code", how="left")
    summary = merged.groupby(sector_col)["momentum"].mean().reset_index()
    summary = summary.sort_values("momentum", ascending=False)
    return summary.rename(columns={sector_col: "sector"}).to_dict(orient="records")


def query_regime_summary(start, end):
    # simple regime proxy using market breadth
    if not os.path.exists(DATA_OHLCV):
        return {"up": 0, "down": 0, "ratio": 0}
    start = pd.to_datetime(start)
    end = pd.to_datetime(end)
    up, down = 0, 0
    for code in _iter_candidate_codes(DATA_OHLCV, ".csv"):
        df = _load_ohlcv(code)
        if df is None:
            continue
        m = df[(df["Date"] >= start) & (df["Date"] <= end)]
        if m.empty:
            continue
        m = m.sort_values("Date")
        if m.iloc[-1]["Close"] >= m.iloc[0]["Close"]:
            up += 1
        else:
            down += 1
    total = up + down
    if total == 0:
        return {"up": 0, "down": 0, "ratio": 0}
    return {"up": up, "down": down, "ratio": round(up / total, 4)}


def run_query(start, end, top_n=10, min_turnover=None):
    out = {
        "period": f"{start}~{end}",
        "top_foreign_net_buy": query_foreign_net_buy(start, end, top_n=top_n),
        "momentum_top": query_momentum_top(start, end, top_n=top_n, min_turnover=min_turnover),
        "sector_summary": query_sector_summary(start, end)[:20],
        "regime_summary": query_regime_summary(start, end)
    }
    return out


if __name__ == "__main__":
    result = run_query("2025-11-01", "2026-02-13", top_n=5)
    print(json.dumps(result, ensure_ascii=False, indent=2))
