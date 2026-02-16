import subprocess
import os
import time
import json
from datetime import datetime

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


def run_script(script_path, retries=3):
    print(f"[{datetime.now()}] Running {script_path}...")
    python_bin = os.path.join(ROOT_DIR, 'invest/venv/bin/python')
    last_err = None

    for i in range(retries):
        try:
            abs_script = os.path.join(ROOT_DIR, script_path)
            result = subprocess.run([python_bin, abs_script], capture_output=True, text=True)
            if result.returncode == 0:
                print(f"[{datetime.now()}] Successfully finished {script_path}")
                return True, ""
            last_err = (result.stderr or result.stdout or "unknown error").strip()
            print(f"[{datetime.now()}] Retry {i+1}/{retries} failed in {script_path}: {last_err}")
        except Exception as e:
            last_err = str(e)
            print(f"[{datetime.now()}] Exception on retry {i+1}/{retries} while running {script_path}: {e}")

        time.sleep(1 + i)

    return False, (last_err or "failed")

def main():
    print(f"[{datetime.now()}] Starting Daily Data Update Pipeline...")
    
    scripts = [
        'invest/scripts/fetch_stock_list.py',
        'invest/scripts/fetch_ohlcv.py',
        'invest/scripts/fetch_supply.py',
        'invest/scripts/fetch_trends.py'
    ]

    # Auto-include additional data streams if present
    optional_scripts = [
        'invest/scripts/fetch_us_ohlcv.py',
        'invest/scripts/fetch_macro_fred.py',
        'invest/scripts/fetch_global_macro.py',  # VIX, SOX, DXY for regime detection
        'invest/scripts/fetch_news_rss.py',
        'invest/scripts/image_harvester.py',
        'invest/scripts/fetch_dart_disclosures.py'
    ]
    for s in optional_scripts:
        if os.path.exists(os.path.join(ROOT_DIR, s)):
            scripts.append(s)
    
    failures = []
    for script in scripts:
        ok, err = run_script(script)
        if not ok:
            failures.append({"script": script, "error": err})
        time.sleep(2) # Brief cooling period

    status_dir = 'invest/data/runtime'
    os.makedirs(status_dir, exist_ok=True)
    status_path = os.path.join(status_dir, 'daily_update_status.json')
    status = {
        "timestamp": datetime.now().isoformat(),
        "total_scripts": len(scripts),
        "failed_count": len(failures),
        "failures": failures,
    }
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now()}] Daily Data Update Pipeline Completed. status={status_path}")

if __name__ == "__main__":
    main()
