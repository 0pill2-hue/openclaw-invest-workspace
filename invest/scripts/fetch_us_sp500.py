import io
import urllib.request

import pandas as pd

SP500_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
FALLBACK_CSV_URL = "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv"


def _fetch_html(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
        charset = resp.headers.get_content_charset() or "utf-8"
        return raw.decode(charset, errors="replace")


def _normalize_symbol(symbol_series):
    return symbol_series.astype(str).str.replace('.', '-', regex=False)


def _shape_output(df: pd.DataFrame) -> pd.DataFrame:
    if 'Symbol' not in df.columns:
        raise ValueError("Missing Symbol column")

    if 'Security' not in df.columns:
        if 'Name' in df.columns:
            df['Security'] = df['Name']
        else:
            df['Security'] = ''

    if 'GICS Sector' not in df.columns:
        if 'Sector' in df.columns:
            df['GICS Sector'] = df['Sector']
        else:
            df['GICS Sector'] = ''

    df['Symbol'] = _normalize_symbol(df['Symbol'])
    df = df[['Symbol', 'Security', 'GICS Sector']].dropna(subset=['Symbol'])
    return df.drop_duplicates(subset=['Symbol']).reset_index(drop=True)


def _fetch_from_wikipedia_html() -> pd.DataFrame:
    html = _fetch_html(SP500_URL)
    tables = pd.read_html(html)
    if not tables:
        raise ValueError("No tables parsed from Wikipedia HTML")
    return _shape_output(tables[0])


def _fetch_from_wikipedia_direct() -> pd.DataFrame:
    tables = pd.read_html(SP500_URL)
    if not tables:
        raise ValueError("No tables parsed from Wikipedia URL")
    return _shape_output(tables[0])


def _fetch_from_fallback_csv() -> pd.DataFrame:
    req = urllib.request.Request(
        FALLBACK_CSV_URL,
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        raw = resp.read()
    df = pd.read_csv(io.BytesIO(raw))
    return _shape_output(df)


def fetch_sp500_list():
    errors = []
    for fn in (_fetch_from_wikipedia_html, _fetch_from_wikipedia_direct, _fetch_from_fallback_csv):
        try:
            df = fn()
            if not df.empty:
                return df
            errors.append(f"{fn.__name__}: empty dataframe")
        except Exception as e:
            errors.append(f"{fn.__name__}: {e}")
    raise RuntimeError("Failed to fetch S&P500 list via all paths: " + " | ".join(errors))


if __name__ == "__main__":
    df = fetch_sp500_list()
    print(f"S&P 500 tickers: {len(df)}")
    print(df.head())
