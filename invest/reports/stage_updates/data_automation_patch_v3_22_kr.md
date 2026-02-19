# Data Automation Patch v3.22 (KR)

- 작성시각: 2026-02-19 14:06 KST
- 목적: 남은 3이슈 자동화 반영 내역 + 재현 명령

## 1) 구현 반영 파일

### A. 공급 누락 자동복구
- 신규: `invest/scripts/stage01_supply_autorepair.py`
  - master 종목(6자리 숫자) vs `invest/data/raw/kr/supply/*_supply.csv` 비교
  - 누락/빈파일만 타깃 재수집
  - 상태 출력: `invest/data/runtime/supply_autorepair_status.json`

### B. DART 백필 자동 전환
- 신규: `invest/scripts/stage01_dart_backfill_autopilot.py`
  - missing month 있으면 incremental 1회 실행
  - missing month 없으면 `monitor` 모드 전환
  - monitor 모드에서는 내부 throttle(기본 24h)로 주기 완화
  - 상태 출력: `invest/data/runtime/dart_backfill_autopilot_state.json`

### C. RSS/Telegram 날짜 보정
- 수정: `invest/scripts/stage01_fetch_news_rss.py`
  - published 날짜를 수집 시점에 ISO 표준화
  - `published_raw`, `published_date`, `published_year`, `date_source` 필드 추가
- 신규: `invest/scripts/stage01_rss_date_repair.py`
  - 기존 `rss_*.json` 배치 보정 (파싱 예외 자동 처리)
  - 상태 출력: `invest/data/runtime/rss_date_repair_status.json`
- 신규: `invest/scripts/stage01_telegram_undated_repair.py`
  - `Date:` 없는 telegram md 파일에 자동 보정 헤더 삽입
  - 상태 출력: `invest/data/runtime/telegram_date_index.json`

### D. 크론 + 실패 알림/정상 무소음
- 신규: `invest/scripts/cron/cron_notify_on_failure.sh`
  - 성공: 무메시지(no reply)
  - 실패: Telegram 알림(`openclaw message send --channel telegram`)
- 신규: `invest/scripts/cron/cron_supply_autorepair.sh`
- 신규: `invest/scripts/cron/cron_dart_backfill_autopilot.sh`
- 신규: `invest/scripts/cron/cron_rss_telegram_date_fix.sh`
- 신규: `invest/scripts/cron/install_data_automation_cron.sh`
  - print/apply 모드 지원

---

## 2) 실행/검증 명령 (재현 가능)

### 문법 검증
```bash
python3 -m py_compile \
  invest/scripts/stage01_fetch_news_rss.py \
  invest/scripts/stage01_supply_autorepair.py \
  invest/scripts/stage01_dart_backfill_autopilot.py \
  invest/scripts/stage01_rss_date_repair.py \
  invest/scripts/stage01_telegram_undated_repair.py
```

### 기능 검증(1회 실행)
```bash
.venv/bin/python3 invest/scripts/stage01_supply_autorepair.py --dry-run --max-repair 3
.venv/bin/python3 invest/scripts/stage01_dart_backfill_autopilot.py
# monitor 전환/완화 로직 테스트
.venv/bin/python3 invest/scripts/stage01_dart_backfill_autopilot.py --force-monitor
.venv/bin/python3 invest/scripts/stage01_rss_date_repair.py
.venv/bin/python3 invest/scripts/stage01_telegram_undated_repair.py
```

### 크론 엔트리 템플릿 출력
```bash
bash invest/scripts/cron/install_data_automation_cron.sh print
```

### 크론 래퍼 단독 실행(실패알림/성공무소음 정책 확인)
```bash
bash invest/scripts/cron/cron_supply_autorepair.sh
bash invest/scripts/cron/cron_dart_backfill_autopilot.sh
bash invest/scripts/cron/cron_rss_telegram_date_fix.sh
```

---

## 3) 증빙 경로

- 공급 자동복구 상태: `invest/data/runtime/supply_autorepair_status.json`
- DART 자동전환 상태: `invest/data/runtime/dart_backfill_autopilot_state.json`
- RSS 보정 상태: `invest/data/runtime/rss_date_repair_status.json`
- Telegram undated 보정 상태: `invest/data/runtime/telegram_date_index.json`
- 크론 실행 로그:
  - `invest/reports/stage_updates/logs/cron/kr_supply_autorepair_20260219_140113.log`
  - `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_20260219_140123.log`
  - `invest/reports/stage_updates/logs/cron/rss_telegram_date_fix_20260219_140251.log`
- DART 전환 규칙 테스트 로그:
  - `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_force_monitor_1.log`
  - `invest/reports/stage_updates/logs/cron/dart_backfill_autopilot_force_monitor_2.log`
