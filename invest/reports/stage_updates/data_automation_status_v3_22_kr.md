# Data Automation Status v3.22 (KR)

- 작성시각: 2026-02-19 14:07 KST
- 기준: 남은 3이슈 자동화 상태 / 트리거 / 실패정책 / 재현성

## 1) 남은 3이슈 상태표

| 이슈 | 자동화 상태 | 트리거 주기 | 실패 정책 | 현재 확인값 |
|---|---|---|---|---|
| 1) kr/supply 1종목 누락 자동복구 | **ON** (`stage01_supply_autorepair.py`) | cron 템플릿 `*/30 * * * *` | 실패 시 `cron_notify_on_failure.sh`가 Telegram 경보, 성공 시 무소음 | `missing_after=[]`, `ok=true` |
| 2) 백필 완료 시 자동 종료/전환 (DART) | **ON** (`stage01_dart_backfill_autopilot.py`) | cron 템플릿 `15 * * * *` + monitor 내부 24h throttle | incremental 실패(rc!=0) 시 크론 경보, 완료 시 monitor 모드 자동전환 | 현재 `mode=backfill` (결손 월 남아있어 진행중) |
| 3) RSS 파싱 예외 + Telegram undated 보정 | **ON** (`stage01_rss_date_repair.py`, `stage01_telegram_undated_repair.py`) | cron 템플릿 `25 */3 * * *` | 단계 실패 시 크론 경보, 성공 시 무소음 | RSS `ok=true`, Telegram `undated_after=0` |

> 참고: 본 패치에서는 **crontab 템플릿/러너 반영**까지 완료. 실제 시스템 crontab 적용은 `install_data_automation_cron.sh apply` 1회 실행으로 마무리 가능.

---

## 2) 재현 명령

```bash
# 0) 크론 블록 확인
bash invest/scripts/cron/install_data_automation_cron.sh print

# 1) 이슈별 단독 실행
.venv/bin/python3 invest/scripts/stage01_supply_autorepair.py --dry-run --max-repair 3
.venv/bin/python3 invest/scripts/stage01_dart_backfill_autopilot.py
.venv/bin/python3 invest/scripts/stage01_rss_date_repair.py
.venv/bin/python3 invest/scripts/stage01_telegram_undated_repair.py

# 2) 크론 래퍼(알림정책 포함) 실행
bash invest/scripts/cron/cron_supply_autorepair.sh
bash invest/scripts/cron/cron_dart_backfill_autopilot.sh
bash invest/scripts/cron/cron_rss_telegram_date_fix.sh
```

---

## 3) 증빙 경로

### 상태 JSON
- `invest/data/runtime/supply_autorepair_status.json`
- `invest/data/runtime/dart_backfill_autopilot_state.json`
- `invest/data/runtime/rss_date_repair_status.json`
- `invest/data/runtime/telegram_date_index.json`

### 크론 실행 로그
- `invest/reports/stage_updates/logs/cron/kr_supply_autorepair_20260219_140113.log`
- `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_20260219_140123.log`
- `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_force_monitor_1.log`
- `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_force_monitor_2.log`
- `invest/reports/stage_updates/logs/cron/rss_telegram_date_fix_20260219_140251.log`

### 핵심 결과
- Supply: 누락/빈파일 0건 유지 확인
- DART: 201905~201908 월 백필 자동 진행 확인(남은 결손 지속 추적)
- Telegram undated: `invest/reports/stage_updates/data_backfill_metrics_pre_20260219.json` 기준 19건 → `invest/data/runtime/telegram_date_index.json` 기준 0건
- RSS date 파싱: 기존 파일 정규화 완료, 재실행 시 idempotent(추가 수정 0) (`invest/data/runtime/rss_date_repair_status.json`)
