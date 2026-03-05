# Stage1 Docs

## Canonical 문서
- 운영 규칙/재현: `invest/stages/stage1/docs/STAGE1_RULEBOOK_AND_REPRO.md`
- 수집 스펙(도메인/경로): `invest/stages/stage1/docs/stage01_data_collection.md`

## 실행 진입점
- Stage1 메인: `invest/stages/stage1/scripts/stage01_daily_update.py`
  - 뉴스는 2단계 직렬 실행: `stage01_build_news_url_index.py` → `stage01_collect_selected_news_articles.py`
- Stage1 10년 백필(텔레/뉴스/DART/블로그): `python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10`
  - 빠른 실동작 점검: `python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10 --smoke`
- 체인(launchd): `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 보조 launchd 잡:
  - `invest/stages/stage1/scripts/launchd/launchd_dart_backfill_autopilot.sh`
  - `invest/stages/stage1/scripts/launchd/launchd_rss_telegram_date_fix.sh`
  - `invest/stages/stage1/scripts/launchd/launchd_supply_autorepair.sh`
  - `com.jobiseu.openclaw.invest.stage01.blog` → `stage01_scrape_all_posts_v2.py`
  - `com.jobiseu.openclaw.invest.stage01.telegram` → `stage01_scrape_telegram_launchd.py`

## 디렉토리
- scripts: `invest/stages/stage1/scripts/`
- inputs: `invest/stages/stage1/inputs/`
- outputs: `invest/stages/stage1/outputs/`
