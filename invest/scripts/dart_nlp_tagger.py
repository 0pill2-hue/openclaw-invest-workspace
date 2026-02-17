import argparse
import glob
import json
import os
from datetime import datetime

import pandas as pd

DART_DIR = "invest/data/raw/kr/dart"
OUT_DIR = "invest/data/raw/kr/dart/tagged"

RISK_RULES = {
    "governance_high": ["최대주주", "경영권", "유상증자", "전환사채", "BW", "CB", "지분", "소송"],
    "capital_event": ["유상증자", "무상증자", "감자", "전환청구", "신주"],
    "operation_event": ["영업정지", "횡령", "배임", "부도", "회생"],
}


def _latest_csv():
    files = sorted(glob.glob(os.path.join(DART_DIR, "dart_list_*.csv")))
    return files[-1] if files else None


def _tag_text(text: str):
    text = str(text or "")
    hits = []
    for tag, kws in RISK_RULES.items():
        if any(k in text for k in kws):
            hits.append(tag)
    if not hits:
        hits = ["normal"]
    return hits


def run(in_csv=None):
    in_csv = in_csv or _latest_csv()
    if not in_csv or not os.path.exists(in_csv):
        print("no dart csv found")
        return None

    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(in_csv)
    title_col = "report_nm" if "report_nm" in df.columns else ("rcept_no" if "rcept_no" in df.columns else df.columns[0])

    tags = []
    for _, row in df.iterrows():
        t = str(row.get(title_col, ""))
        tags.append(_tag_text(t))

    out = df.copy()
    out["risk_tags"] = [",".join(x) for x in tags]
    out["tagged_at"] = datetime.now().isoformat()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_csv = os.path.join(OUT_DIR, f"dart_tagged_{ts}.csv")
    out_json = os.path.join(OUT_DIR, f"dart_tag_summary_{ts}.json")
    out.to_csv(out_csv, index=False)

    summary = {
        "source": in_csv,
        "rows": int(len(out)),
        "tag_counts": out["risk_tags"].value_counts().to_dict(),
    }
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"saved: {out_csv}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return out_csv


def main():
    ap = argparse.ArgumentParser(description="Rule-based DART disclosure tagging")
    ap.add_argument("--input", default=None)
    args = ap.parse_args()
    run(args.input)


if __name__ == "__main__":
    main()
