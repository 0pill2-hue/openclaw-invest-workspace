import os
import glob
import pandas as pd
import json

BASE_DATA = '/Users/jobiseu/.openclaw/workspace/invest/data'
CLEAN_PROD = os.path.join(BASE_DATA, 'clean/production')
REPORT_DIR = '/Users/jobiseu/.openclaw/workspace/reports/qc'

def verify_production():
    checks = []
    folders = [f for f in os.listdir(CLEAN_PROD) if os.path.isdir(os.path.join(CLEAN_PROD, f))]
    
    for root_f in folders:
        sub_path = os.path.join(CLEAN_PROD, root_f)
        for sub_f in os.listdir(sub_path):
            p = os.path.join(sub_path, sub_f)
            if os.path.isdir(p):
                files = glob.glob(os.path.join(p, '*'))
                if not files:
                    checks.append(f"EMPTY_DIR: {root_f}/{sub_f}")
                else:
                    # sample one file
                    sample = files[0]
                    ext = os.path.splitext(sample)[1].lower()
                    try:
                        if ext == '.csv':
                            df = pd.read_csv(sample)
                            if df.empty: checks.append(f"EMPTY_CSV: {sample}")
                        elif ext == '.json':
                            with open(sample, 'r') as f: json.load(f)
                    except Exception as e:
                        checks.append(f"CORRUPT_FILE: {sample} ({str(e)})")

    report_path = os.path.join(REPORT_DIR, 'PROD_VERIFY_REPORT.md')
    with open(report_path, 'w') as f:
        f.write("# Production Data Verification Report\n\n")
        if not checks:
            f.write("✅ All sampled production data directories and files passed basic integrity checks.\n")
        else:
            f.write("⚠️ Issues found:\n")
            for c in checks:
                f.write(f"- {c}\n")
    
    return report_path

if __name__ == "__main__":
    print(f"Verification report saved: {verify_production()}")
