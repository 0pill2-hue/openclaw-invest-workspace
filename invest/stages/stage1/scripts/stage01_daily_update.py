#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from pipeline_logger import append_pipeline_event

ROOT_DIR = Path(__file__).resolve().parents[4]
STATUS_PATH = ROOT_DIR / "invest/stages/stage1/outputs/runtime/daily_update_status.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_script(script_path: str, retries: int = 3) -> tuple[bool, str]:
    """Run script with retry and return (ok, error_message)."""
    python_bin = os.environ.get("INVEST_PYTHON_BIN", "").strip()
    if not python_bin:
        python_bin = sys.executable

    abs_script = ROOT_DIR / script_path
    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            result = subprocess.run([python_bin, str(abs_script)], capture_output=True, text=True)
            if result.returncode == 0:
                return True, ""
            last_err = (result.stderr or result.stdout or "unknown error").strip()
        except Exception as exc:
            last_err = str(exc)

        if attempt < retries:
            time.sleep(1 + attempt)

    return False, (last_err or "failed")


def run_with_fallbacks(script_path: str) -> tuple[bool, str, str]:
    """Run primary collector, then fallback collectors on failure."""
    fallback_map = {
        "invest/stages/stage1/scripts/stage01_fetch_ohlcv.py": [
            "invest/stages/stage1/scripts/stage01_full_fetch_ohlcv.py"
        ],
        "invest/stages/stage1/scripts/stage01_fetch_supply.py": [
            "invest/stages/stage1/scripts/stage01_full_fetch_supply.py"
        ],
        "invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py": [
            "invest/stages/stage1/scripts/stage01_full_fetch_us_ohlcv.py"
        ],
        "invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py": [
            "invest/stages/stage1/scripts/stage01_full_fetch_dart_disclosures.py"
        ],
    }

    ok, err = run_script(script_path)
    if ok:
        return True, "", script_path

    fallbacks = [
        p for p in fallback_map.get(script_path, []) if (ROOT_DIR / p).exists()
    ]
    last_err = err
    for fb in fallbacks:
        ok_fb, err_fb = run_script(fb)
        if ok_fb:
            return True, f"primary_failed_fallback_ok:{script_path}->{fb}", fb
        last_err = f"primary:{err} | fallback:{fb}:{err_fb}"

    return False, (last_err or err), script_path


def _build_script_list() -> list[str]:
    scripts = [
        "invest/stages/stage1/scripts/stage01_fetch_stock_list.py",
        "invest/stages/stage1/scripts/stage01_fetch_ohlcv.py",
        "invest/stages/stage1/scripts/stage01_fetch_supply.py",
    ]

    optional_scripts = [
        "invest/stages/stage1/scripts/stage01_fetch_macro_fred.py",
        "invest/stages/stage1/scripts/stage01_fetch_global_macro.py",
        "invest/stages/stage1/scripts/stage01_fetch_news_rss.py",
        "invest/stages/stage1/scripts/stage01_build_news_url_index.py",
        "invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py",
        "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py",
        "invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py",
        "invest/stages/stage1/scripts/stage01_image_harvester.py",
        "invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py",
        "invest/stages/stage1/scripts/stage01_collect_premium_startale_channel_auth.py",
    ]
    scripts.extend([s for s in optional_scripts if (ROOT_DIR / s).exists()])

    run_us_in_daily = os.environ.get("RUN_US_OHLCV_IN_DAILY", "0").strip().lower() in (
        "1",
        "true",
        "yes",
    )
    us_script = "invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py"
    if run_us_in_daily and (ROOT_DIR / us_script).exists():
        scripts.append(us_script)

    return scripts


def main() -> int:
    print(f"[{datetime.now()}] Starting Daily Data Update Pipeline...")

    scripts = _build_script_list()
    failures: list[dict] = []
    fallbacks_used: list[dict] = []
    results: list[dict] = []

    for script in scripts:
        ok, err, executed = run_with_fallbacks(script)
        results.append(
            {
                "script": script,
                "executed": executed,
                "ok": bool(ok),
                "error": err if not ok else "",
                "fallback_note": err if ok and err else "",
            }
        )
        if not ok:
            failures.append({"script": script, "error": err})
        elif err:
            fallbacks_used.append(
                {"script": script, "note": err, "executed": executed}
            )
        time.sleep(1)

    STATUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    status = {
        "timestamp": _now_iso(),
        "ok": len(failures) == 0,
        "total_scripts": len(scripts),
        "failed_count": len(failures),
        "failures": failures,
        "fallbacks_used": fallbacks_used,
        "results": results,
    }
    STATUS_PATH.write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding="utf-8")

    if failures:
        summary = "; ".join(f"{f['script']}: {f['error']}" for f in failures[:10])
        print(f"[{datetime.now()}] Daily update FAILED: {summary}")
    else:
        print(f"[{datetime.now()}] Daily update OK")

    append_pipeline_event(
        source="stage01_daily_update",
        status="FAIL" if failures else "OK",
        count=len(scripts) - len(failures),
        errors=[f"{f['script']}: {f['error']}" for f in failures],
        note=f"status={STATUS_PATH.relative_to(ROOT_DIR)}",
    )

    print(f"[{datetime.now()}] Daily Data Update Pipeline Completed. status={STATUS_PATH}")
    if failures:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
