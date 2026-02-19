# Data Backfill Progress (2026-02-19, 중간)

- Updated: 2026-02-19 10:34 KST
- 기준 진단 리포트: `reports/stage_updates/data_gap_audit_20260219.md`
- 기준 메트릭: `reports/stage_updates/data_backfill_metrics_pre_20260219.json`

## 1) 백필 배치 실행 상태 (백그라운드)

| Job | Session ID | Status | Log |
|---|---|---|---|
| DART missing-month batch (52 windows) | `gentle-lagoon` | RUNNING | `reports/stage_updates/logs/backfill_dart_20260219.log` |
| Blog full-cycle backfill (6 passes) | `mellow-meadow` | RUNNING | `reports/stage_updates/logs/backfill_blog_20260219.log` |
| Telegram full-history backfill | `mellow-willow` | RUNNING | `reports/stage_updates/logs/backfill_telegram_20260219.log` |
| Stage01 기타 소스 재수집 | `plaid-orbit` | RUNNING | `reports/stage_updates/logs/backfill_stage01_missing_20260219.log` |

## 2) 현재까지 확인된 진행

- DART
  - 시작 완료, 52개 누락 월 윈도우 중 1번 윈도우(2016-11) 처리 진행 중.
- Blog
  - pass 1/6 완료 (`processed 120 buddies`, `SAVED=7`, `ERRORS=0`)
  - pass 2/6 시작됨.
- Telegram
  - FULL 모드 진입 확인 (`MODE: FULL_1Y` 로그 표기, 스크립트 내부는 10년 컷오프 로직 사용)
  - 채널 스캔 시작 확인.
- Stage01 기타 소스
  - `stage01_fetch_stock_list` 완료
  - `stage01_fetch_ohlcv` 실행 중

## 3) 실패/재시도 정책 (적용 중)

- DART: 월별 윈도우 단위, `max_attempts=3`, 지수 backoff(2s/4s/8s)
- Blog: pass 단위, `max_attempts=3`, 지수 backoff
- Telegram: 전체 런 `max_attempts=2`, 선형 backoff(5s, 10s)
- Stage01 기타: 소스별 `max_attempts=2`, 지수 backoff

## 4) 다음 단계

1. 4개 백그라운드 배치 완료 대기
2. 완료 후 post-validation 실행 (`invest/scripts/stage01_post_collection_validate.py`)
3. post-metrics 수집 (`data_backfill_metrics_post_20260219.json`)
4. 전/후 커버리지 비교 포함 최종 완료 리포트 작성
