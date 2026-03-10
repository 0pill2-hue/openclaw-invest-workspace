from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT_PATH = Path(__file__).resolve().parents[4]
ROOT_DIR = str(ROOT_PATH)
RUNTIME_DIR = ROOT_PATH / 'invest/stages/stage1/outputs/runtime'
TARGET_DATE_2016 = '2016-01-01'

FALLBACK_MAP = {
    'invest/stages/stage1/scripts/stage01_fetch_ohlcv.py': ['invest/stages/stage1/scripts/stage01_full_fetch_ohlcv.py'],
    'invest/stages/stage1/scripts/stage01_fetch_supply.py': ['invest/stages/stage1/scripts/stage01_full_fetch_supply.py'],
    'invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py': ['invest/stages/stage1/scripts/stage01_full_fetch_us_ohlcv.py'],
    'invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py': ['invest/stages/stage1/scripts/stage01_full_fetch_dart_disclosures.py'],
}

PROFILE_CHOICES = [
    'daily_full',
    'rss_fast',
    'telegram_fast',
    'blog_fast',
    'kr_ohlcv_intraday',
    'kr_supply_intraday',
    'us_ohlcv_daily',
    'dart_fast',
    'news_backfill',
]


def _env_enabled(name: str, default: str = '0') -> bool:
    return os.environ.get(name, default).strip().lower() in ('1', 'true', 'yes')


def _select_python_bin() -> str:
    env_python = os.environ.get('INVEST_PYTHON_BIN', '').strip()
    workspace_python = ROOT_PATH / '.venv/bin/python3'
    if env_python and Path(env_python).is_file() and os.access(env_python, os.X_OK):
        return env_python
    if workspace_python.is_file() and os.access(workspace_python, os.X_OK):
        return str(workspace_python)
    return sys.executable


def _status_path(profile: str) -> Path:
    if profile == 'daily_full':
        return RUNTIME_DIR / 'daily_update_status.json'
    safe = profile.replace('-', '_')
    return RUNTIME_DIR / f'daily_update_{safe}_status.json'


def _spec(script: str, *, retries: int = 3, env: dict[str, str] | None = None, use_fallbacks: bool = True) -> dict[str, Any]:
    return {
        'script': script,
        'retries': retries,
        'env': dict(env or {}),
        'use_fallbacks': use_fallbacks,
    }


def _exists(script: str) -> bool:
    return (ROOT_PATH / script).exists()


def build_profile_specs(profile: str) -> list[dict[str, Any]]:
    profiles: dict[str, list[dict[str, Any]]] = {
        'daily_full': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_stock_list.py'),
            _spec('invest/stages/stage1/scripts/stage01_fetch_ohlcv.py'),
            _spec('invest/stages/stage1/scripts/stage01_fetch_supply.py'),
            _spec('invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py'),
            _spec('invest/stages/stage1/scripts/stage01_fetch_macro_fred.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_fetch_global_macro.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_fetch_news_rss.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_build_news_url_index.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py'),
            _spec('invest/stages/stage1/scripts/stage01_collect_premium_startale_channel_auth.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_collect_link_sidecars.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'rss_fast': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_news_rss.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'telegram_fast': [
            _spec('invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_collect_link_sidecars.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'blog_fast': [
            _spec('invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_collect_link_sidecars.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'kr_ohlcv_intraday': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_ohlcv.py'),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'kr_supply_intraday': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_supply.py'),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'us_ohlcv_daily': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_us_ohlcv.py'),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'dart_fast': [
            _spec('invest/stages/stage1/scripts/stage01_fetch_dart_disclosures.py'),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
        'news_backfill': [
            _spec(
                'invest/stages/stage1/scripts/stage01_fetch_news_rss.py',
                use_fallbacks=False,
                env={
                    'RSS_ENABLE_PAGED_BACKFILL': '1',
                    'RSS_BACKFILL_TARGET_DATE': TARGET_DATE_2016,
                    'RSS_BACKFILL_TARGET_YEARS': '10',
                    'RSS_BACKFILL_MAX_PAGES': os.environ.get('RSS_BACKFILL_MAX_PAGES', '400'),
                    'RSS_BACKFILL_MAX_EMPTY_PAGES': os.environ.get('RSS_BACKFILL_MAX_EMPTY_PAGES', '3'),
                    'RSS_DISABLE_KEYWORD_FILTER': '1',
                },
            ),
            _spec(
                'invest/stages/stage1/scripts/stage01_build_news_url_index.py',
                use_fallbacks=False,
                env={
                    'NEWS_INDEX_TARGET_DATE': TARGET_DATE_2016,
                    'NEWS_INDEX_RSS_MAX_PAGES': os.environ.get('NEWS_INDEX_RSS_MAX_PAGES', '120'),
                    'NEWS_INDEX_MAX_SITEMAPS': os.environ.get('NEWS_INDEX_MAX_SITEMAPS', '300'),
                    'GUARDIAN_ENABLE': os.environ.get('GUARDIAN_ENABLE', '1'),
                    'GUARDIAN_END_DATE': os.environ.get('GUARDIAN_END_DATE', '2019-12-31'),
                    'GUARDIAN_MAX_MONTHS': os.environ.get('GUARDIAN_MAX_MONTHS', '48'),
                    'GUARDIAN_MAX_PAGES_PER_SLICE': os.environ.get('GUARDIAN_MAX_PAGES_PER_SLICE', '1'),
                    'GUARDIAN_PAGE_SIZE': os.environ.get('GUARDIAN_PAGE_SIZE', '50'),
                },
            ),
            _spec(
                'invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py',
                use_fallbacks=False,
                env={
                    'NEWS_SELECTED_TARGET_DATE': TARGET_DATE_2016,
                    'NEWS_SELECTED_MIN_KEYWORD_HITS': os.environ.get('NEWS_SELECTED_MIN_KEYWORD_HITS', '0'),
                    'NEWS_SELECTED_MAX_ARTICLES': os.environ.get('NEWS_SELECTED_MAX_ARTICLES', '600'),
                    'NEWS_SELECTED_MAX_ATTEMPTS': os.environ.get('NEWS_SELECTED_MAX_ATTEMPTS', '5000'),
                    'NEWS_SELECTED_YEARLY_QUOTA': os.environ.get('NEWS_SELECTED_YEARLY_QUOTA', '50'),
                    'NEWS_SELECTED_SKIP_EXISTING': os.environ.get('NEWS_SELECTED_SKIP_EXISTING', '1'),
                    'NEWS_SELECTED_EXCLUDED_DOMAINS': os.environ.get('NEWS_SELECTED_EXCLUDED_DOMAINS', 'bloomberg.com,wsj.com'),
                    'NEWS_SELECTED_EXCLUDED_URL_PATTERNS': os.environ.get('NEWS_SELECTED_EXCLUDED_URL_PATTERNS', '/graphics/,/video/'),
                },
            ),
            _spec('invest/stages/stage1/scripts/stage01_sync_raw_to_db.py', use_fallbacks=False),
            _spec('invest/stages/stage1/scripts/stage01_update_coverage_manifest.py', use_fallbacks=False),
        ],
    }

    specs = list(profiles[profile])
    return [spec for spec in specs if _exists(str(spec['script']))]


def run_script(script_path: str, retries: int = 3, env_overrides: dict[str, str] | None = None):
    print(f"[{datetime.now()}] Running {script_path}...")
    python_bin = _select_python_bin()
    abs_script = ROOT_PATH / script_path
    last_err = None
    env = os.environ.copy()
    env.update({k: str(v) for k, v in (env_overrides or {}).items() if v is not None})

    for i in range(retries):
        try:
            result = subprocess.run(
                [python_bin, str(abs_script)],
                capture_output=True,
                text=True,
                cwd=ROOT_DIR,
                env=env,
            )
            if result.returncode == 0:
                print(f"[{datetime.now()}] Successfully finished {script_path}")
                return True, ""
            last_err = (result.stderr or result.stdout or 'unknown error').strip()
            print(f"[{datetime.now()}] Retry {i+1}/{retries} failed in {script_path}: {last_err}")
        except Exception as e:
            last_err = str(e)
            print(f"[{datetime.now()}] Exception on retry {i+1}/{retries} while running {script_path}: {e}")

        time.sleep(1 + i)

    return False, (last_err or 'failed')


def run_with_fallbacks(script_path: str, retries: int = 3, env_overrides: dict[str, str] | None = None):
    ok, err = run_script(script_path, retries=retries, env_overrides=env_overrides)
    if ok:
        return True, '', script_path

    fallbacks = [p for p in FALLBACK_MAP.get(script_path, []) if _exists(p)]
    last_err = err
    for fb in fallbacks:
        print(f"[{datetime.now()}] Primary failed, trying fallback: {fb}")
        ok_fb, err_fb = run_script(fb, retries=retries, env_overrides=env_overrides)
        if ok_fb:
            return True, f'primary_failed_fallback_ok:{script_path}->{fb}', fb
        last_err = f'primary:{err} | fallback:{fb}:{err_fb}'

    return False, (last_err or err), script_path


def _scheduler_origin() -> str:
    raw = os.environ.get('SCHEDULER_ORIGIN', '').strip()
    if raw:
        return raw
    if os.environ.get('LAUNCHD_JOB_LABEL'):
        return 'launchd'
    return 'manual'


def _build_stage1_run_id() -> str:
    existing = os.environ.get('STAGE1_RUN_ID', '').strip()
    if existing:
        return existing
    return datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')


def run_profile(profile: str) -> dict[str, Any]:
    specs = build_profile_specs(profile)
    failures = []
    fallbacks_used = []
    executed_scripts = []
    started_at = datetime.now(timezone.utc)
    python_bin = _select_python_bin()
    run_id = _build_stage1_run_id()
    scheduler_origin = _scheduler_origin()
    launchd_job_label = os.environ.get('LAUNCHD_JOB_LABEL', '').strip()
    shared_env = {
        'STAGE1_RUN_ID': run_id,
        'STAGE1_PROFILE': profile,
        'SCHEDULER_ORIGIN': scheduler_origin,
        'STAGE1_PARENT_SCRIPT': 'invest/stages/stage1/scripts/stage01_daily_update.py',
    }
    if launchd_job_label:
        shared_env['LAUNCHD_JOB_LABEL'] = launchd_job_label

    for spec in specs:
        script = str(spec['script'])
        env = dict(shared_env)
        env.update(dict(spec.get('env') or {}))
        retries = int(spec.get('retries') or 3)
        use_fallbacks = bool(spec.get('use_fallbacks', True))

        if use_fallbacks:
            ok, err, executed = run_with_fallbacks(script, retries=retries, env_overrides=env)
        else:
            ok, err = run_script(script, retries=retries, env_overrides=env)
            executed = script

        executed_scripts.append({
            'requested': script,
            'executed': executed,
            'env_overrides': env,
            'use_fallbacks': use_fallbacks,
        })

        if not ok:
            failures.append({'script': script, 'error': err})
        elif err:
            fallbacks_used.append({'script': script, 'note': err, 'executed': executed})
        time.sleep(2)

    finished_at = datetime.now(timezone.utc)
    duration_sec = max(0.0, (finished_at - started_at).total_seconds())
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    status = {
        'timestamp': finished_at.isoformat(),
        'started_at': started_at.isoformat(),
        'finished_at': finished_at.isoformat(),
        'duration_sec': round(duration_sec, 3),
        'run_id': run_id,
        'profile': profile,
        'scheduler_origin': scheduler_origin,
        'launchd_job_label': launchd_job_label,
        'host': socket.gethostname(),
        'python_bin': python_bin,
        'repo_root': ROOT_DIR,
        'status_path': str(_status_path(profile)),
        'total_scripts': len(specs),
        'executed_scripts': executed_scripts,
        'failed_count': len(failures),
        'failures': failures,
        'fallbacks_used': fallbacks_used,
        'run_us_in_daily': _env_enabled('RUN_US_OHLCV_IN_DAILY'),
    }
    _status_path(profile).write_text(json.dumps(status, ensure_ascii=False, indent=2), encoding='utf-8')
    return status


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Stage1 profile-based orchestrator')
    parser.add_argument('--profile', choices=PROFILE_CHOICES, default=os.environ.get('STAGE1_DAILY_PROFILE', 'daily_full'))
    return parser.parse_args()


def main():
    args = parse_args()
    print(f"[{datetime.now()}] Starting Stage1 orchestrator profile={args.profile}...")
    status = run_profile(args.profile)
    print(f"[{datetime.now()}] Stage1 orchestrator completed. status={_status_path(args.profile)}")
    if status['failed_count'] > 0:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
