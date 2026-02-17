# STAGE05_RECOVERY_CHAIN_20260218

- 실행시각(KST): 2026-02-18 01:09~01:17
- 실행 원칙: clean-only 기준 재실행 (2~5단계)
- 중단 규칙: 단계 실패 시 즉시 중단/원인 기록 (본 실행에서는 중단 조건 미발생)

## 단계별 실행 결과

### 1) 정제 검수 재실행 (Stage2)
- 명령: `.venv/bin/python3 invest/scripts/validate_refine_independent.py`
- 상태: **SUCCESS (스크립트 실행 성공, 판정 내 FAIL 포함)**
- 핵심 로그: `reports/logs/STAGE02_VALIDATE_REFINE_20260218.log`
- 최신 산출물:
  - `reports/qc/VALIDATION_INDEPENDENT_20260218_011721.md`
  - `reports/qc/VALIDATION_INDEPENDENT_20260218_011721.json`
  - `reports/qc/verdict_20260218_011721.json`
- 판정 요약: PASS 8 / WARN 2 / FAIL 2 (kr/dart, text/blog FAIL)

### 2) 밸류 추출 재실행 (Stage3)
- 명령: `.venv/bin/python3 scripts/calculate_stage3_values.py`
- 상태: **SUCCESS**
- 핵심 로그: `reports/logs/STAGE03_VALUE_RUN_20260218.log`
- 최신 산출물:
  - `reports/stage_updates/STAGE3_VALUE_RUN_20260218_011716.json`
- 요약: processed=3382, skipped=4, errors=0

### 3) 하드닝 3항목 점검 재실행 (Stage4)
- 명령: `.venv/bin/python3 scripts/stage4_hardening_3items.py`
- 상태: **SUCCESS**
- 핵심 로그: `reports/logs/STAGE04_HARDENING_3ITEMS_20260218.log`
- 최신 산출물:
  - `reports/qc/STAGE4_HARDENING_3ITEMS_20260218.md`
  - `reports/qc/STAGE4_HARDENING_3ITEMS_20260218.json`

### 4) 5단계(베이스라인 3트랙) 재실행 (Stage5)
- 명령: `.venv/bin/python3 -m scripts.stage5_baseline_fixed_run_20260218`
- 상태: **SUCCESS**
- 핵심 로그: `reports/logs/STAGE05_BASELINE_FIXED_RUN_20260218.log`
- 최신 산출물:
  - `reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.md`
  - `reports/stage_updates/STAGE05_BASELINE_FIXED_RUN_20260218.json`
- 필수 문구 검증:
  - `DRAFT (TEST ONLY)` 확인
  - `7단계(Purged CV/OOS) 전 채택 금지` 확인

## manifest(lineage) 생성/갱신 확인
- 본 2~5단계 재실행에서 단계별 신규 manifest/lineage 파일은 **직접 생성 확인되지 않음**.
- 관련 lineage 파일 존재 확인:
  - `reports/qc/FULL_AUDIT_GOV_LINEAGE_20260218.md` (mtime: 2026-02-18 01:11:04)
- 기록 결론: **lineage 파일은 존재하나, 본 체인(2~5) 실행의 신규 생성 산출물로는 확인되지 않음**.

## 판정 요약 5줄
1. Stage2 정제 검수는 실행 성공했으나 도메인 판정은 PASS 8 / WARN 2 / FAIL 2로 GR1 FAIL 항목 잔존.
2. Stage3 밸류 재계산은 errors=0으로 완료되어 수치 최신화 반영.
3. Stage4 하드닝 3항목 점검 결과 KR 연속성 WARN 비중이 높고(2078/2883), US는 WARN 0/503.
4. Stage5 3트랙 결과는 Quant/Text/Hybrid 모두 drop_criteria_v1 기준 **탈락**이며 공식 채택 불가 상태.
5. Stage5 산출물의 `DRAFT(TEST ONLY)` 및 `7단계 전 채택 금지` 게이트 문구는 정상 유지됨.
