import argparse
import os
from datetime import datetime

import pandas as pd

OUT_DIR = "invest/reports/charts"


def _safe_import_matplotlib():
    try:
        import matplotlib.pyplot as plt
        return plt
    except Exception as e:
        print(f"matplotlib unavailable: {e}")
        return None


def _load_close_series(code: str):
    path = f"invest/data/raw/kr/ohlcv/{code}.csv"
    if not os.path.exists(path):
        return None
    df = pd.read_csv(path)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date")
    return df[["Date", "Close"]]


def make_price_chart(code: str, days: int = 365):
    plt = _safe_import_matplotlib()
    if plt is None:
        return None

    data = _load_close_series(code)
    if data is None or data.empty:
        print(f"missing ohlcv: {code}")
        return None

    cutoff = pd.Timestamp.now() - pd.Timedelta(days=days)
    data = data[data["Date"] >= cutoff]
    if data.empty:
        print(f"no rows in period: {code}")
        return None

    os.makedirs(OUT_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = os.path.join(OUT_DIR, f"price_{code}_{ts}.png")

    plt.figure(figsize=(10, 4))
    plt.plot(data["Date"], data["Close"], label=f"{code} Close")
    plt.title(f"{code} Close ({days}d)")
    plt.xlabel("Date")
    plt.ylabel("Price")
    plt.grid(alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out, dpi=130)
    plt.close()
    return out


def main():
    ap = argparse.ArgumentParser(description="Generate quick market charts")
    ap.add_argument("--code", default="005930")
    ap.add_argument("--days", type=int, default=365)
    args = ap.parse_args()

    out = make_price_chart(args.code, args.days)
    if out:
        print(f"saved: {out}")


if __name__ == "__main__":
    main()
