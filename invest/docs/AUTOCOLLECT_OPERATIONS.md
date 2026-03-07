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
5. 이미지/OCR 후처리 및 검증을 어디서 fail-close 할지
6. 검증 절차를 어떤 순서로 실행할지

---

## 2. 운영 원칙

- **원칙 1 — 수집과 검증을 분리하지 않는다.**
  - Stage1 수집 후 `checkpoint_gate` + `post_collection_validate` + `ocr_postprocess_validate`를 붙여 fail-close 한다.
- **원칙 2 — 주기별 책임을 나눈다.**
  - 일일 메인 체인, 자주 도는 OCR/수리 잡, 저빈도 backfill/repair 잡을 분리한다.
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
  4. `stage01_run_images_ocr_rolling.py`
  5. `stage01_ocr_postprocess_validate.py`
  6. Stage2 auto gate
  7. `stage03_build_input_jsonl.py`
  8. `stage03_attention_gate_local_brain.py`
  9. `calculate_stage4_values.py`
  10. `stage05_feature_engineer.py`
- fail-close 지점:
  - checkpoint 실패
  - post-collection 실패
  - OCR postprocess validate 실패
  - stage2 gate 실패

### 3.2 보조 job
- OCR rolling: `invest/stages/stage1/scripts/launchd/launchd_stage01_images_ocr_rolling.sh`
- RSS/Telegram 날짜 복구: `invest/stages/stage1/scripts/launchd/launchd_rss_telegram_date_fix.sh`
- 수급 autorepair: `invest/stages/stage1/scripts/launchd/launchd_supply_autorepair.sh`
- DART backfill autopilot: `invest/stages/stage1/scripts/launchd/launchd_dart_backfill_autopilot.sh`

---

## 4. 데이터별 운영 주기

권장 기본 주기다. 실제 launchd 등록값은 `invest/ops/launchd/jobs.registry.json`과 plist 예시를 따른다.

| job | 대상 | 권장 주기 | 이유 |
|---|---|---:|---|
| `invest.stage12345.daily` | KR/US 시세, 수급, 매크로, RSS, 뉴스, DART, Stage2~5 | 평일 19:10 KST | 장 종료 후 국내 데이터 반영, 이후 체인 수행 |
| `invest.stage1.ocr.rolling` | 이미지 OCR 큐 소진 | 30분 | 첨부 이미지가 비동기 유입되므로 자주 소진 |
| `invest.stage1.repair.datefix` | RSS/Telegram 날짜 보정 | 2시간 | 소규모 보정, 메인 체인과 분리 |
| `invest.stage1.repair.supply` | 수급 누락 자동 보정 | 평일 20:40 KST | 일일 수집 후 누락 보정 |
| `invest.stage1.backfill.dart` | DART 장기 누락 자동 메움 | 1일 1회 03:40 KST | 장중 부담 없이 저빈도 점검 |
| `invest.stage1.backfill.10y` | 10년 backfill 초기 적재 | 수동/임시 등록 | 평시 상시 등록 금지 |

### 주기 분리 근거
- KR OHLCV/수급/일일 DART/뉴스는 하루 1회 main chain이면 충분하다.
- OCR은 텔레그램 첨부나 이미지 링크가 뒤늦게 도착할 수 있어 rolling이 유리하다.
- autorepair 류는 실패 복구 성격이라 메인체인과 분리해야 blast radius가 작다.

---

## 5. 10년 backfill → incremental 전환 기준

### 5.1 초기 bootstrap 단계
초기 환경 또는 대규모 누락 시 아래를 한 번 수행한다.

```bash
python3 invest/stages/stage1/scripts/stage01_backfill_10y.py --years 10
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
python3 invest/stages/stage1/scripts/stage01_run_images_ocr_rolling.py --batch-size 200 --max-scan 10000
python3 invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py
```

### 5.2 전환 조건
아래가 만족되면 운영 모드를 incremental로 본다.

- `invest/stages/stage1/outputs/runtime/stage01_backfill_10y_status.json` 존재
- `stage01_checkpoint_status.json` 통과
- `post_collection_validate.json` 통과
- OCR 큐가 최근 성공 기준을 만족
- 이후부터는 `stage01_daily_update.py`와 `stage01_dart_backfill_incremental.py` 중심으로 운용

### 5.3 운영 단계
- 평시: main chain + OCR rolling + autorepair
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
- `STAGE01_OCR_ROLLING_BATCH`
- `STAGE01_OCR_ROLLING_SCAN`
- `STAGE01_OCR_VALIDATE_*`
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
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.ocr.rolling.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.repair.datefix.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.repair.supply.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage1.backfill.dart.plist
```

### 재적용

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage12345.daily.plist || true
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.jobiseu.invest.stage12345.daily.plist
launchctl kickstart -k gui/$(id -u)/com.jobiseu.invest.stage12345.daily
```

---

## 8. OCR / postprocess 검증 구조

이번 보강으로 OCR 후처리 검증 경로를 명시적으로 추가했다.

### 수집/후처리
- rolling OCR: `stage01_run_images_ocr_rolling.py`
- 상태 파일:
  - checkpoint: `invest/stages/stage1/outputs/runtime/stage01_images_ocr_rolling_checkpoint.json`
  - latest stats: `invest/stages/stage1/outputs/runtime/stage01_images_ocr_rolling_latest.json`

### 검증
- validator: `stage01_ocr_postprocess_validate.py`
- 결과: `invest/stages/stage1/outputs/runtime/stage01_ocr_postprocess_validate.json`
- 검증 항목:
  - 최근 성공 건수 최소 기준
  - 최근 실패 건수 상한
  - OCR 산출 txt 실존 여부
  - txt 최소 길이
  - 최신 txt 신선도

### fail-close 반영
- `run_stage1234_chain.sh`에서 OCR rolling 직후 validator를 실행한다.
- validator 실패 시 Stage2 이후를 막는다.
- `stage01_post_collection_validate.py`도 validator 결과 파일을 읽도록 연결했다.

---

## 9. 운영 검증 절차

### 9.1 단건 수동 검증

```bash
python3 invest/stages/stage1/scripts/stage01_daily_update.py
python3 invest/stages/stage1/scripts/stage01_checkpoint_gate.py
python3 invest/stages/stage1/scripts/stage01_post_collection_validate.py
python3 invest/stages/stage1/scripts/stage01_run_images_ocr_rolling.py --batch-size 20 --max-scan 500
python3 invest/stages/stage1/scripts/stage01_ocr_postprocess_validate.py
bash invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh
```

### 9.2 산출물 확인 포인트
- `invest/stages/stage1/outputs/runtime/daily_update_status.json`
- `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
- `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- `invest/stages/stage1/outputs/runtime/stage01_images_ocr_rolling_checkpoint.json`
- `invest/stages/stage1/outputs/runtime/stage01_images_ocr_rolling_latest.json`
- `invest/stages/stage1/outputs/runtime/stage01_ocr_postprocess_validate.json`
- `invest/stages/stage2/outputs/runtime/stage02_auto_state.json`
- `invest/stages/stage1/outputs/runtime/stage1234_chain_state.json`

### 9.3 launchd 등록 후 검증

```bash
launchctl print gui/$(id -u)/com.jobiseu.invest.stage12345.daily
launchctl print gui/$(id -u)/com.jobiseu.invest.stage1.ocr.rolling
launchctl kickstart -k gui/$(id -u)/com.jobiseu.invest.stage1.ocr.rolling
```

로그 확인:
- `invest/stages/stage1/outputs/logs/runtime/launchd_stage1234_chain.log`
- `invest/stages/stage1/outputs/logs/runtime/launchd_stage01_images_ocr_rolling.log`
- `invest/stages/stage2/outputs/logs/runtime/launchd_stage02_auto.log`

---

## 10. 복구 가이드

### 메인 체인 실패
1. `launchd_stage1234_chain.log` 확인
2. checkpoint / post_collection / OCR validator 중 어디서 fail-close 되었는지 확인
3. 원천 데이터 누락이면 해당 수집기 단독 재실행
4. 복구 후 `launchctl kickstart -k ...stage12345.daily`

### OCR validator 실패
1. `stage01_ocr_postprocess_validate.json`의 `errors` 확인
2. tesseract 설치/권한/언어팩 확인
3. `stage01_run_images_ocr_rolling.py --batch-size 50 --max-scan 1000` 재실행
4. validator 재실행

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
   - 근거: OCR/repair/backfill은 일일 체인과 failure domain이 다름.
3. **10년 backfill은 상시가 아니라 bootstrap/repair 전용**
   - 근거: 운영비용이 크고, daily/incremental 스크립트가 이미 존재.
4. **OCR는 rolling + postprocess validate로 운영**
   - 근거: 이미지 유입 시점이 비동기이고, 단순 파일 존재만으로는 downstream 신뢰도를 보장하기 어려움.
5. **post_collection_validate가 OCR validator 결과를 참조**
   - 근거: Stage1 전체 품질 보고서에서 OCR 품질이 빠지면 운영 판단이 분리되어 누락되기 쉬움.
