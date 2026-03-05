#!/usr/bin/env python3
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
HIGH = ROOT / "invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py"
FALLBACK = ROOT / "invest/stages/stage1/scripts/stage01_scrape_telegram_public_fallback.py"


def _has_secret_env() -> bool:
    return bool(os.environ.get("TELEGRAM_API_ID") and os.environ.get("TELEGRAM_API_HASH"))


def _run(path: Path) -> int:
    proc = subprocess.run([sys.executable, str(path)], cwd=str(ROOT))
    return int(proc.returncode)


def main() -> int:
    if _has_secret_env():
        rc = _run(HIGH)
        if rc == 0:
            return 0
        # auth/session 실패 시 fallback을 한 번 수행해 qualitative/text 공백을 방지
        fb = _run(FALLBACK)
        return 0 if fb == 0 else rc

    # launchd 환경에 secret이 없으면 public fallback 우선
    return _run(FALLBACK)


if __name__ == "__main__":
    raise SystemExit(main())
