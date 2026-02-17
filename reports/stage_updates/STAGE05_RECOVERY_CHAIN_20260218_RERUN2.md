# STAGE05 RECOVERY CHAIN 2026-02-18 (RERUN2)

## 0) 실행 목적
- 목표: 동시 수집 영향 제거 + 거버넌스 지적사항 반영 + Stage2~5 재실행
- 실행시각: 2026-02-18 01:22~01:30 KST
- 결과등급: **DRAFT / TEST ONLY** (7단계 전 채택 금지)

## 1) 수집 freeze (검증 체인 동안)
- freeze 시작: **2026-02-18 01:23:01 KST**
- 중지 대상 PID
  - 86628 (`collector-loop bash while true ...`)
  - 86633 (`invest/scripts/full_fetch_dart_disclosures.py`)
  - 90996 (`invest/scripts/fetch_dart_disclosures.py`)
- 중지 확인: `stopped:86628, stopped:86633, stopped:90996`
- 체인 종료 시점 재확인(01:30:03 KST): 수집 관련 프로세스 미동작

## 2) 즉시조치(최소 침습)
### 2-1. raw 직접참조 HARD 우선 패치
- `invest/backtest_compare.py`
  - 입력 경로를 raw → clean/production으로 전환
  - matplotlib 미설치 환경에서도 동작하도록 optional import 처리(핵심 계산 로직 유지)
- `invest/scripts/generate_feature_comparison.py`
  - 입력 경로를 raw → clean/production으로 전환
  - 출력 DRAFT 문구 + 7단계 전 채택 금지 문구 유지
  - manifest 기록 추가
- `invest/scripts/alert_trigger.py`
  - VIX 입력 경로 raw → clean/production 전환

### 2-2. lineage/manifest 보강 (2~5단계 경로)
- `invest/scripts/validate_refine_independent.py` (Stage2) manifest 추가
- `scripts/calculate_stage3_values.py` (Stage3) manifest 추가
- `scripts/stage4_hardening_3items.py` (Stage4) manifest 추가
- `scripts/stage5_baseline_fixed_run_20260218.py` (Stage5) manifest 추가

### 2-3. Stage5 보고 문구 오해 제거
- `scripts/stage5_baseline_fixed_run_20260218.py`
  - `operate/monitor` → `operate_candidate/monitor_candidate`로 변경
  - “확정 운영” 오해 방지를 위해 후보/주의 문구 강화
  - 7단계 전 채택 금지 문구 일관 유지

## 3) 2~5단계 재실행 결과
### Stage2: validate_refine_independent
- 실행 로그: `reports/stage_updates/logs/rerun2_stage2_validate_refine_independent.log`
- 결과: **PASS 7 / WARN 2 / FAIL 3**
- 산출물
  - `reports/qc/VALIDATION_INDEPENDENT_20260218_012504.md`
  - `reports/qc/VALIDATION_INDEPENDENT_20260218_012504.json`
  - `reports/qc/verdict_20260218_012504.json`
  - `invest/reports/data_quality/manifest_stage2_validate_20260218_012504.json`

### Stage3: calculate_stage3_values
- 실행 로그: `reports/stage_updates/logs/rerun2_stage3_calculate_stage3_values.log`
- 결과: processed=3382, skipped=4, errors=0
- 산출물
  - `reports/stage_updates/STAGE3_VALUE_RUN_20260218_012813.json`
  - `invest/reports/data_quality/manifest_stage3_value_20260218_012813.json`

### Stage4: stage4_hardening_3items
- 실행 로그: `reports/stage_updates/logs/rerun2_stage4_hardening_3items.log`
- 산출물
  - `reports/qc/STAGE4_HARDENING_3ITEMS_20260218.md`
  - `reports/qc/STAGE4_HARDENING_3ITEMS_20260218.json`
  - `invest/reports/data_quality/manifest_stage4_hardening_20260218_012849.json`

### Stage5: stage5_baseline_fixed_run_20260218
- 실행 로그: `reports/stage_updates/logs/rerun2_stage5_baseline_fixed_run.log`
- 산출물
  - `reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.md`
  - `reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json`
  - `invest/reports/data_quality/manifest_stage5_baseline_20260218_012944.json`

## 4) PASS 기준 점검 (Stage2 FAIL=0 목표)
- 목표 달성 여부: **미달 (FAIL=3)**
- 정확 원인(파일/카운트)
  1. `kr/dart` GR-1 위반: raw=236, preserved=218 (부족 18)
     - evidence: `reports/qc/evidence/evidence_kr_dart_20260218_012504.json`
  2. `market/news/rss` GR-1 위반: raw=47, preserved=46 (부족 1)
     - evidence: `reports/qc/evidence/evidence_market_news_rss_20260218_012504.json`
  3. `text/blog` GR-1 위반: raw=27377, preserved=27374 (부족 3)
     - evidence: `reports/qc/evidence/evidence_text_blog_20260218_012504.json`

### 재시도안
1) raw-clean diff 추출(3개 폴더) → 누락 파일명 목록 생성
2) 해당 파일만 clean 또는 quarantine으로 보존 복구(backfill/copy) 후 GR-1 재검증
3) Stage2 단독 재실행하여 FAIL=0 확인

## 5) 이번 변경 파일 목록(본 작업 범위)
- `invest/backtest_compare.py`
- `invest/scripts/generate_feature_comparison.py`
- `invest/scripts/alert_trigger.py`
- `invest/scripts/validate_refine_independent.py`
- `scripts/calculate_stage3_values.py`
- `scripts/stage4_hardening_3items.py`
- `scripts/stage5_baseline_fixed_run_20260218.py`

## 6) 수집 resume 정책
- 상태: **자동 재개하지 않음 (사용자 승인 대기)**
- 이유: Stage2 FAIL=0 기준 미달 상태에서 재수집 재개 시 raw-clean 격차를 다시 확대할 수 있어, GR-1 복구 후 재개하는 것이 안전함.
