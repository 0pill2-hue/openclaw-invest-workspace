import subprocess
import os
import time
import json
from datetime import datetime
from pathlib import Path

ROOT_DIR = str(Path(__file__).resolve().parents[4])


def run_script(script_path, retries=3):
    """
    
        Role: 지정된 파이썬 스크립트를 하위 프로세스로 실행하고 재시도 로직을 수행한다.
        Input: script_path (실행할 스크립트 경로), retries (실패 시 최대 재시도 횟수)
        Output: (success: bool, error_message: str)
        Author: 조비스 (Flash)
        Date: 2026-02-18
        
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Updated: 2026-02-18
    """
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

def run_with_fallbacks(script_path):
    """Run primary collector, and if it fails try predefined fallback collectors."""
    fallback_map = {
        'invest/stages/stage1/scripts/stage01_fetch_ohlcv.py': ['invest/stages/stage1/scripts/stage01_full_fetch_ohlcv.py'],
        'invest/stages/stage1/scripts/stage01_fetch_supply.py': ['invest/stages/stage1/scripts/stage01_full_fetch_supply.py'],
        'invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py': ['invest/stages/stage1/scripts/stage01_full_fetch_us_ohlcv.py'],
        'invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py': ['invest/stages/stage1/scripts/stage01_full_fetch_dart_disclosures.py'],
    }

    ok, err = run_script(script_path)
    if ok:
        return True, "", script_path

    fallbacks = [p for p in fallback_map.get(script_path, []) if os.path.exists(os.path.join(ROOT_DIR, p))]
    last_err = err
    for fb in fallbacks:
        print(f"[{datetime.now()}] Primary failed, trying fallback: {fb}")
        ok_fb, err_fb = run_script(fb)
        if ok_fb:
            return True, f"primary_failed_fallback_ok:{script_path}->{fb}", fb
        last_err = f"primary:{err} | fallback:{fb}:{err_fb}"

    return False, (last_err or err), script_path


def main():
    """
    Role: main 함수 역할 설명
    Input: 입력 타입/의미 명시
    Output: 반환 타입/의미 명시
    Side effect: 파일 저장/외부 호출/상태 변경 여부
    Author: 조비스
    Updated: 2026-02-18
    """
    print(f"[{datetime.now()}] Starting Daily Data Update Pipeline...")
    
    scripts = [
        'invest/stages/stage1/scripts/stage01_fetch_stock_list.py',
        'invest/stages/stage1/scripts/stage01_fetch_ohlcv.py',
        'invest/stages/stage1/scripts/stage01_fetch_supply.py',
    ]

    # Auto-include additional data streams if present
    optional_scripts = [
        'invest/stages/stage1/scripts/stage01_fetch_macro_fred.py',
        'invest/stages/stage1/scripts/stage01_fetch_global_macro.py',  # VIX, SOX, DXY for regime detection
        'invest/stages/stage1/scripts/stage01_fetch_news_rss.py',
        'invest/stages/stage1/scripts/stage01_build_news_url_index.py',
        'invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py',
        'invest/stages/stage1/scripts/stage01_image_harvester.py',
        'invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py',
        'invest/stages/stage1/scripts/stage01_collect_premium_startale_channel_auth.py',
    ]
    for s in optional_scripts:
        if os.path.exists(os.path.join(ROOT_DIR, s)):
            scripts.append(s)

    # US OHLCV is scheduled separately once per day by cron.
    # Keep opt-in support for manual integrated runs only.
    run_us_in_daily = os.environ.get('RUN_US_OHLCV_IN_DAILY', '0').strip().lower() in ('1', 'true', 'yes')
    us_script = 'invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py'
    if run_us_in_daily and os.path.exists(os.path.join(ROOT_DIR, us_script)):
        scripts.append(us_script)
    
    failures = []
    fallbacks_used = []
    for script in scripts:
        ok, err, executed = run_with_fallbacks(script)
        if not ok:
            failures.append({"script": script, "error": err})
        elif err:
            fallbacks_used.append({"script": script, "note": err, "executed": executed})
        time.sleep(2) # Brief cooling period

    status_dir = 'invest/stages/stage1/outputs/runtime'
    os.makedirs(status_dir, exist_ok=True)
    status_path = os.path.join(status_dir, 'daily_update_status.json')
    status = {
        "timestamp": datetime.now().isoformat(),
        "total_scripts": len(scripts),
        "failed_count": len(failures),
        "failures": failures,
        "fallbacks_used": fallbacks_used,
    }
    with open(status_path, 'w', encoding='utf-8') as f:
        json.dump(status, f, ensure_ascii=False, indent=2)

    print(f"[{datetime.now()}] Daily Data Update Pipeline Completed. status={status_path}")

if __name__ == "__main__":
    main()
