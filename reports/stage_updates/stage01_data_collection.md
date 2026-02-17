status: CANONICAL
updated_at: 2026-02-18 05:56 KST
stage: 01
name: data_collection
description: 원천 데이터 수집(가격/수급/텍스트) 및 raw 보존
objective:
  - 재현 가능한 동일 입력셋 확보
  - 이후 단계(정제/검증)에서 추적 가능한 수집 로그 고정
scope:
  market: KR
  data_domains:
    - ohlcv
    - supply
    - text(telegram/blog/rss)
  period_policy:
    - 기본: 증분 수집
    - 필요 시: full backfill 실행
sources:
  ohlcv:
    primary: KRX/Naver 수집 경로(invest/scripts/fetch_ohlcv.py)
    full: invest/scripts/full_fetch_ohlcv.py
  supply:
    primary: invest/scripts/fetch_supply.py
    full: invest/scripts/full_fetch_supply.py
  text:
    telegram: invest/scripts/full_scrape_telegram.py
    blog: invest/scripts/scrape_all_posts_v2.py
    rss: invest/scripts/fetch_news_rss.py
run_profile:
  mode_default: incremental
  command_incremental:
    - python3 invest/scripts/daily_update.py
  command_full:
    - python3 invest/scripts/run_full_collection.py
    - python3 invest/scripts/full_fetch_ohlcv.py
    - python3 invest/scripts/full_fetch_supply.py
outputs:
  raw_root: invest/data/raw/
  health_state: memory/health-state.json
  collection_log: reports/stage_updates/logs/
  lineage_manifest: invest/reports/data_quality/manifest_*.json
quality_gates:
  - id: QG-01-01 (Process Exit)
    check: "수집 스크립트 비정상 종료 없음(exit code 0)"
  - id: QG-01-02 (Health State)
    check: "health-state 갱신 성공"
  - id: QG-01-03 (Raw Freshness)
    check: "raw 산출 경로에 당일 타임스탬프 파일 생성"
  - id: QG-01-04 (Fail Isolation)
    check: "실패 건은 clean 투입 금지(2단계 quarantine 처리)"
failure_policy:
  retry:
    max_attempts: 3
    backoff: exponential
  escalation:
    - 연속 실패/큐 적체 발생 시 watchdog 경고
    - 원인 로그와 실패 구간을 stage log에 기록
repro_checklist:
  - 동일 스크립트/동일 모드(incremental/full) 사용
  - 동일 기간/심볼 범위 확인
  - 실행 후 manifest 해시 비교
next: stage02_data_cleaning.md