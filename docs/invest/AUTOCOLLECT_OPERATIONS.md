# invest 자동수집 운영 설계 / 실행 문서

상태: DRAFT  
범위: Stage1 수집 + Stage2~5 체인 자동화 + launchd 운영 기준  
기준 저장소: `invest/` 하위 실제 스크립트 / 출력 경로

## 1. 목표

이 문서는 아래를 재현 가능하게 고정한다.

1. 어떤 job을 어떤 주기로 돌릴지
2. launchd에 어떤 plist를 등록할지
3. 공통 env / job registry를 어떻게 관리할지
4. 10년 backfill에서 incremental 운영으로 어떻게 전환할지
5. 수집 검증을 어디서 fail-close 할지
6. 검증 절차를 어떤 순서로 실행할지

---

## 2. 운영 원칙

- **원칙 1 — 수집과 검증을 분리하지 않는다.**
  - Stage1 수집 후 `checkpoint_gate` + `post_collection_validate`를 붙여 fail-close 한다.
- **원칙 2 — 주기별 책임을 나눈다.**
  - 일일 메인 체인, 자주 도는 수리 잡, 저빈도 backfill/repair 잡을 분리한다.
- **원칙 3 — backfill은 언젠가 끝나는 작업이고, 운영은 incremental이어야 한다.**
  - 10년 수집은 초기 적재/누락 복구용이다.
  - 평시 운영은 incremental 잡이 기본이며, backfill은 상태 파일/coverage 확인 시에만 다시 호출한다.
- **원칙 4 — launchd에는 스케줄만 두고, 실제 로직은 repo 스크립트가 가진다.**
  - plist는 thin wrapper.
  - 실행/락/timeout/fail-close/상태 기록은 repo 스크립트가 담당.
- **원칙 5 — DB/source별 coverage manifest를 SSOT로 유지한다.**
  - 원천 raw 파일만 보고 수집 범위를 판단하지 않는다.
  - 각 DB/source 디렉토리에는 `coverage_summary.json`을 두고, 수집 직후 자동 갱신한다.
  - 운영 보고/누락 판단/추가 수집 판단은 manifest 기준으로 한다.

---

## 3. 실제 엔트리포인트

### 3.1 메인 daily chain
- 스크립트: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 내부 순서:
  1. `stage01_daily_update.py`
  2. `stage01_checkpoint_gate.py`
  3. `stage01_post_collection_validate.py`
  4. Stage2 auto gate
  5. `stage03_build_input_jsonl.py`
  6. `stage03_attention_gate_local_brain.py`
  7. `calculate_stage4_values.py`
  8. `stage05_feature_engineer.py`
- fail-close 지점:
  - checkpoint 실패
  - post-collection 실패
  - stage2 gate 실패

### 3.2 보조 job
- RSS/Telegram 날짜 복구: `invest/stages/stage1/scripts/launchd/launchd_rss_telegram_date_fix.sh`
- 수급 autorepair: `invest/stages/stage1/scripts/launchd/launchd_supply_autorepair.sh`
- DART backfill autopilot: `invest/stages/stage1/scripts/launchd/launchd_dart_backfill_autopilot.sh`
- selected articles 백필: `invest/stages/stage1/scripts/launchd/launchd_stage01_profile.sh news_backfill`

---

## 4. 데이터별 운영 주기

권장 기본 주기다. 실제 launchd 등록값은 `invest/ops/launchd/jobs.registry.json`과 plist 예시를 따른다.

| job | 대상 | 권장 주기 | 이유 |
|---|---|---:|---|
| `invest.stage12345.daily` | KR/US 시세, 수급, 매크로, RSS, 뉴스, DART, Stage2~5 | 평일 19:10 KST | 장 종료 후 국내 데이터 반영, 이후 체인 수행 |
| `invest.stage1.repair.datefix` | RSS/Telegram 날짜 보정 | 2시간 | 소규모 보정, 메인 체인과 분리 |
| `invest.stage1.repair.supply` | 수급 누락 자동 보정 | 평일 20:40 KST | 일일 수집 후 누락 보정 |
| `invest.stage1.backfill.dart` | DART 장기 누락 자동 메움 | 1일 1회 03:40 KST | 장중 부담 없이 저빈도 점검 |
| `invest.stage1.backfill.news` | selected_articles 2016 coverage 백필 | 30분 | 미수집 backlog를 점진 소진하고 이미 수집 성공한 URL은 건너뜀 |
| `invest.stage1.backfill.10y.manual` | 10년 backfill 초기 적재 | 수동/임시 등록 | 평시 상시 등록 금지 |

### 주기 분리 근거
- KR OHLCV/수급/일일 DART/뉴스는 하루 1회 main chain이면 충분하다.
- autorepair 류는 실패 복구 성격이라 메인체인과 분리해야 blast radius가 작다.

---

## 5. 10년 backfill → incremental 전환 기준

### 5.1 초기 bootstrap 단계
초기 환경 또는 대규모 누락 시 아래를 한 번 수행한다.

```bash
python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
```

### 5.2 전환 조건
아래가 만족되면 운영 모드를 incremental로 본다.

- `invest/stages/stage1/outputs/runtime/stage01_backfill_10y_status.json` 존재
- `stage01_checkpoint_status.json` 통과
- `post_collection_validate.json` 통과
- 이후부터는 `stage01_daily_update.py`와 `stage01_dart_backfill_incremental.py` 중심으로 운용

### 5.3 운영 단계
- 평시: main chain + autorepair
- 누락 탐지 시:
  - DART 누락: `stage01_dart_backfill_autopilot.py` / `stage01_dart_backfill_incremental.py`
  - 광범위 누락: 필요한 자산만 backfill 재실행
- 전체 10년 backfill은 상시 스케줄 등록하지 않는다.

---

## 6. env 설계

공통 env 파일 예시는 `invest/ops/launchd/env/invest_autocollect.env.example`.

핵심 변수:
- `INVEST_ROOT`
- `INVEST_PYTHON_BIN`
- `RUN_US_OHLCV_IN_DAILY`
- `STAGE1234_LOCK_TTL_SEC`
- `TELEGRAM_API_ID`, `TELEGRAM_API_HASH`
- `DART_API_KEY`

원칙:
- 비밀값은 Git에 넣지 않는다.
- launchd plist에는 비밀값을 직접 하드코딩하지 않는다.
- 실제 운영 파일은 예: `~/.config/invest/invest_autocollect.env` 로 두고 plist에서 `EnvironmentVariables` 또는 wrapper sourcing 방식으로 주입한다.

---

## 7. launchd 구조

권장 디렉토리:

- registry: `invest/ops/launchd/jobs.registry.json`
- plist 예시: `invest/ops/launchd/plists/*.plist`
- env 예시: `invest/ops/launchd/env/invest_autocollect.env.example`

### 등록 예시

```bash
mkdir -p ~/Library/LaunchAgents
cp invest/ops/launchd/plists/*.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage12345.daily.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.repair.datefix.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.repair.supply.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.backfill.dart.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.backfill.news.plist
```

### 재적용

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage12345.daily.plist || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage12345.daily.plist
launchctl kickstart -k gui/$(id -u)/com.jobiseu.invest.stage12345.daily
```

---

## 8. 수집 검증 구조

현재 Stage1 메인 검증은 아래 두 단계만 fail-close로 유지한다.

- `stage01_checkpoint_gate.py`
- `stage01_post_collection_validate.py`

참고:
- Stage1 이미지 OCR/image_map 수집 경로는 제거되었다.
- `run_stage1234_chain.sh`는 post-collection 검증 통과 후 바로 Stage2로 진입한다.

---

## 9. 운영 검증 절차

### 9.1 단건 수동 검증

```bash
python3 invest/stages/stage1/scripts/stage01_daily_update.py
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

### 9.2 산출물 확인 포인트
- `invest/stages/stage1/outputs/runtime/daily_update_status.json`
- `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
- `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- `invest/stages/stage2/outputs/runtime/stage02_auto_state.json`
- `invest/stages/stage1/outputs/runtime/stage1234_chain_state.json`

### 9.3 launchd 등록 후 검증

```bash
launchctl print gui/$(id -u)/com.jobiseu.invest.stage12345.daily
launchctl kickstart -k gui/$(id -u)/com.jobiseu.invest.stage12345.daily
```

로그 확인:
- `invest/stages/stage1/outputs/logs/runtime/launchd_stage1234_chain.log`
- `invest/stages/stage2/outputs/logs/runtime/launchd_stage02_auto.log`

---

## 10. 복구 가이드

### 메인 체인 실패
1. `launchd_stage1234_chain.log` 확인
2. checkpoint / post_collection 중 어디서 fail-close 되었는지 확인
3. 원천 데이터 누락이면 해당 수집기 단독 재실행
4. 복구 후 `launchctl kickstart -k ...stage12345.daily`

### DART 장기 누락
1. `launchd_dart_backfill_autopilot.sh` 로그 확인
2. `invest/stages/stage1/outputs/raw/source_coverage_index.json`와 `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json`에서 `missing_months_between_range`, `latest_date`, `needs_incremental_update` 먼저 확인
3. 필요 시 `stage01_dart_backfill_incremental.py` 수동 실행
4. 광범위 누락이면 `stage01_backfill_10y.py --years 10`을 임시 수행
5. 수집 후 manifest가 갱신됐는지 확인하고, 운영 보고도 manifest 기준으로 작성

---

## 11. 중요한 결정 요약

1. **메인 체인은 Stage1~5 단일 진입점 유지**
   - 근거: 이미 `run_stage1234_chain.sh`가 락, timeout, retry, fail-close를 구현하고 있어 재사용 가치가 큼.
2. **주기 다른 job은 launchd에서 분리**
   - 근거: repair/backfill은 일일 체인과 failure domain이 다름.
3. **10년 backfill은 상시가 아니라 bootstrap/repair 전용**
   - 근거: 운영비용이 크고, daily/incremental 스크립트가 이미 존재.
4. **Stage1 이미지는 메타데이터만 남기고 수집/OCR는 비활성화**
   - 근거: image_map/OCR 산출 경로를 제거해 Stage1 raw를 텍스트 중심으로 단순화했다.
5. **Stage1 검증은 checkpoint + post_collection로 단순화**
   - 근거: 제거된 이미지 OCR 경로를 fail-close 체인에서 제외해 운영 경로를 코드와 일치시켰다.
