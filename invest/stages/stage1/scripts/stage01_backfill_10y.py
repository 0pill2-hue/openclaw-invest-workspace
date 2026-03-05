#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PY = sys.executable
RUNTIME_DIR = ROOT / "invest/stages/stage1/outputs/runtime"
STATUS_PATH = RUNTIME_DIR / "stage01_backfill_10y_status.json"


def _target_date(years: int) -> str:
    y = max(1, int(years))
    return (datetime.now(timezone.utc) - timedelta(days=365 * y)).date().isoformat()


def _run_step(name: str, cmd: list[str], env_overrides: dict[str, str]) -> dict:
    env = os.environ.copy()
    env.update({k: str(v) for k, v in env_overrides.items() if v is not None})

    print(f"\n[BACKFILL] START {name}")
    print(f"[BACKFILL] CMD   {' '.join(cmd)}")
    started = time.time()
    rc = subprocess.call(cmd, cwd=str(ROOT), env=env)
    ended = time.time()
    elapsed = round(ended - started, 2)
    status = "OK" if rc == 0 else "FAIL"
    print(f"[BACKFILL] END   {name} status={status} rc={rc} elapsed={elapsed}s")

    return {
        "step": name,
        "status": status,
        "rc": rc,
        "elapsed_sec": elapsed,
        "started_at": datetime.fromtimestamp(started, tz=timezone.utc).isoformat(),
        "ended_at": datetime.fromtimestamp(ended, tz=timezone.utc).isoformat(),
        "command": cmd,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Stage1 qualitative/source backfill runner (10y default)")
    ap.add_argument("--years", type=int, default=int(os.environ.get("STAGE1_BACKFILL_YEARS", "10")))
    ap.add_argument("--smoke", action="store_true", help="빠른 실동작 점검용 제한 실행")

    ap.add_argument("--skip-telegram", action="store_true")
    ap.add_argument("--skip-news", action="store_true")
    ap.add_argument("--skip-dart", action="store_true")
    ap.add_argument("--skip-blog", action="store_true")

    ap.add_argument("--rss-max-pages", type=int, default=int(os.environ.get("RSS_BACKFILL_MAX_PAGES", "300")))
    ap.add_argument("--rss-max-empty-pages", type=int, default=int(os.environ.get("RSS_BACKFILL_MAX_EMPTY_PAGES", "2")))
    ap.add_argument("--rss-disable-keyword-filter", action="store_true")
    ap.add_argument("--news-index-rss-pages", type=int, default=int(os.environ.get("NEWS_INDEX_RSS_MAX_PAGES", "80")))
    ap.add_argument("--news-index-max-sitemaps", type=int, default=int(os.environ.get("NEWS_INDEX_MAX_SITEMAPS", "220")))
    ap.add_argument("--news-selected-max-articles", type=int, default=int(os.environ.get("NEWS_SELECTED_MAX_ARTICLES", "160")))
    ap.add_argument("--news-selected-min-keyword-hits", type=int, default=int(os.environ.get("NEWS_SELECTED_MIN_KEYWORD_HITS", "1")))

    ap.add_argument("--telegram-force-full", action="store_true", default=True)
    ap.add_argument("--telegram-global-timeout-sec", type=int, default=int(os.environ.get("TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC", "7200")))
    ap.add_argument("--telegram-per-channel-timeout-sec", type=int, default=int(os.environ.get("TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC", "600")))
    ap.add_argument("--telegram-max-messages-per-channel", type=int, default=int(os.environ.get("TELEGRAM_MAX_MESSAGES_PER_CHANNEL", "0")))
    ap.add_argument("--telegram-public-limit", type=int, default=int(os.environ.get("TG_PUBLIC_FALLBACK_LIMIT", "200")))
    ap.add_argument("--telegram-public-max-msgs", type=int, default=int(os.environ.get("TG_PUBLIC_FALLBACK_MAX_MSGS", "20000")))
    ap.add_argument("--telegram-public-max-pages", type=int, default=int(os.environ.get("TG_PUBLIC_FALLBACK_MAX_PAGES", "1200")))

    ap.add_argument("--dart-step-months", type=int, default=int(os.environ.get("DART_FULL_STEP_MONTHS", "1")))
    ap.add_argument("--dart-max-chunks", type=int, default=int(os.environ.get("DART_FULL_MAX_CHUNKS", "0")))
    ap.add_argument("--dart-max-pages", type=int, default=int(os.environ.get("DART_MAX_PAGES", "1000")))

    ap.add_argument("--blog-limit-buddies", type=int, default=int(os.environ.get("BLOG_LIMIT_BUDDIES", "200")))
    ap.add_argument("--blog-max-posts-per-buddy", type=int, default=int(os.environ.get("BLOG_MAX_POSTS_PER_BUDDY", "1200")))
    ap.add_argument("--blog-max-pages-per-buddy", type=int, default=int(os.environ.get("BLOG_MAX_PAGES_PER_BUDDY", "360")))
    ap.add_argument("--blog-sleep", type=float, default=float(os.environ.get("BLOG_FETCH_SLEEP_SEC", "0.15")))

    args = ap.parse_args()

    if args.smoke:
        args.rss_max_pages = min(args.rss_max_pages, 40)
        args.news_index_rss_pages = min(args.news_index_rss_pages, 25)
        args.news_index_max_sitemaps = min(args.news_index_max_sitemaps, 80)
        args.news_selected_max_articles = min(args.news_selected_max_articles, 35)
        args.telegram_global_timeout_sec = min(args.telegram_global_timeout_sec, 900)
        args.telegram_per_channel_timeout_sec = min(args.telegram_per_channel_timeout_sec, 180)
        args.telegram_max_messages_per_channel = args.telegram_max_messages_per_channel or 300
        args.telegram_public_limit = min(args.telegram_public_limit, 5)
        args.telegram_public_max_msgs = min(args.telegram_public_max_msgs, 800)
        args.telegram_public_max_pages = min(args.telegram_public_max_pages, 80)
        args.dart_max_chunks = args.dart_max_chunks or 2
        args.blog_limit_buddies = min(args.blog_limit_buddies, 5)
        args.blog_max_posts_per_buddy = min(args.blog_max_posts_per_buddy, 120)
        args.blog_max_pages_per_buddy = min(args.blog_max_pages_per_buddy, 20)

    years = max(1, int(args.years))
    target_date = _target_date(years)

    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []

    if not args.skip_news:
        steps.append(
            _run_step(
                "news_rss",
                [PY, "invest/stages/stage1/scripts/stage01_fetch_news_rss.py"],
                {
                    "RSS_ENABLE_PAGED_BACKFILL": "1",
                    "RSS_BACKFILL_TARGET_YEARS": str(years),
                    "RSS_BACKFILL_TARGET_DATE": target_date,
                    "RSS_BACKFILL_MAX_PAGES": str(max(1, args.rss_max_pages)),
                    "RSS_BACKFILL_MAX_EMPTY_PAGES": str(max(1, args.rss_max_empty_pages)),
                    "RSS_DISABLE_KEYWORD_FILTER": "1" if args.rss_disable_keyword_filter else os.environ.get("RSS_DISABLE_KEYWORD_FILTER", "0"),
                },
            )
        )
        steps.append(
            _run_step(
                "news_url_index",
                [PY, "invest/stages/stage1/scripts/stage01_build_news_url_index.py"],
                {
                    "NEWS_INDEX_TARGET_DATE": target_date,
                    "NEWS_INDEX_RSS_MAX_PAGES": str(max(1, args.news_index_rss_pages)),
                    "NEWS_INDEX_MAX_SITEMAPS": str(max(1, args.news_index_max_sitemaps)),
                },
            )
        )
        steps.append(
            _run_step(
                "news_selected_articles",
                [PY, "invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py"],
                {
                    "NEWS_SELECTED_MAX_ARTICLES": str(max(1, args.news_selected_max_articles)),
                    "NEWS_SELECTED_MIN_KEYWORD_HITS": str(max(0, args.news_selected_min_keyword_hits)),
                },
            )
        )

    if not args.skip_telegram:
        steps.append(
            _run_step(
                "telegram",
                [PY, "invest/stages/stage1/scripts/stage01_scrape_telegram_launchd.py"],
                {
                    "TELEGRAM_TARGET_YEARS": str(years),
                    "TELEGRAM_BOOTSTRAP_LOOKBACK_DAYS": str(365 * years),
                    "TELEGRAM_FORCE_FULL_BACKFILL": "1" if args.telegram_force_full else "0",
                    "TELEGRAM_INCREMENTAL_ONLY": "1",
                    "TELEGRAM_MAX_MESSAGES_PER_CHANNEL": str(max(0, args.telegram_max_messages_per_channel)),
                    "TELEGRAM_SCRAPE_GLOBAL_TIMEOUT_SEC": str(max(60, args.telegram_global_timeout_sec)),
                    "TELEGRAM_SCRAPE_PER_CHANNEL_TIMEOUT_SEC": str(max(30, args.telegram_per_channel_timeout_sec)),
                    "TG_PUBLIC_FALLBACK_TARGET_YEARS": str(years),
                    "TG_PUBLIC_FALLBACK_TARGET_DATE": target_date,
                    "TG_PUBLIC_FALLBACK_LIMIT": str(max(1, args.telegram_public_limit)),
                    "TG_PUBLIC_FALLBACK_MAX_MSGS": str(max(1, args.telegram_public_max_msgs)),
                    "TG_PUBLIC_FALLBACK_MAX_PAGES": str(max(1, args.telegram_public_max_pages)),
                },
            )
        )

    if not args.skip_dart:
        steps.append(
            _run_step(
                "dart",
                [PY, "invest/stages/stage1/scripts/stage01_full_fetch_dart_disclosures.py"],
                {
                    "DART_FULL_TARGET_YEARS": str(years),
                    "DART_FULL_START_DATE": target_date,
                    "DART_FULL_STEP_MONTHS": str(max(1, args.dart_step_months)),
                    "DART_FULL_MAX_CHUNKS": str(max(0, args.dart_max_chunks)),
                    "DART_MAX_PAGES": str(max(1, args.dart_max_pages)),
                },
            )
        )

    if not args.skip_blog:
        steps.append(
            _run_step(
                "blog",
                [
                    PY,
                    "invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py",
                    "--limit-buddies",
                    str(max(0, args.blog_limit_buddies)),
                    "--max-posts-per-buddy",
                    str(max(1, args.blog_max_posts_per_buddy)),
                    "--max-pages-per-buddy",
                    str(max(1, args.blog_max_pages_per_buddy)),
                    "--sleep",
                    str(max(0.0, args.blog_sleep)),
                    "--target-years",
                    str(years),
                    "--target-date",
                    target_date,
                ],
                {
                    "BLOG_TARGET_YEARS": str(years),
                    "BLOG_TARGET_DATE": target_date,
                },
            )
        )

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "years": years,
        "target_date": target_date,
        "smoke": bool(args.smoke),
        "steps": steps,
    }
    summary["ok"] = all(s.get("rc", 1) == 0 for s in steps)

    STATUS_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[BACKFILL] STATUS -> {STATUS_PATH}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
