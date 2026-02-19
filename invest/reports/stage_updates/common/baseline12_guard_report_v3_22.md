# baseline12_guard_report_v3_22

## 무엇이 깨져 있었는가
- Stage05 v3_20/v3_21 실행 로직은 `track_counts`를 계산했지만,
  - `3/3/3/3` 불일치 시 즉시 중단(FAIL_STOP)하는 하드가드가 없었고
  - 결과 JSON에 `protocol_enforced`, `track_counts_assertion` 필수 필드가 강제되지 않았음.
- 이 상태에서는 12-baseline 합의 위반이 소프트 실패(REDESIGN 분기)로 흘러가 정합성 리스크가 있었음.

## 무엇을 고쳤는가
### 1) 공용 가드 모듈 추가
- 파일: `invest/scripts/stage05_baseline_guard.py`
- 추가 내용:
  - `EXPECTED_TRACK_COUNTS_12_BASELINE = {numeric:3, qualitative:3, hybrid:3, external-pretrained:3}`
  - `enforce_track_counts_or_fail_stop(...)`
    - 불일치 시: FAIL_STOP 예외 + 실패 JSON 기록(`status=FAIL_STOP`, `protocol_enforced=true`, `track_counts_assertion=fail`)
    - 일치 시: `protocol_enforced=true`, `track_counts_assertion=pass` 메타 반환

### 2) Stage05 실행 스크립트 적용
- `invest/scripts/stage05_incremental_external_v3_20_kr.py`
- `invest/scripts/stage05_incremental_external_v3_21_kr.py`
- `invest/scripts/stage05_full_recompute_v3_22_kr.py` (후속 공용 적용)

적용 방식:
- `track_counts` 계산 직후 `enforce_track_counts_or_fail_stop(...)` 호출
- payload/log에 아래 필드 기록:
  - `protocol_enforced`
  - `track_counts_assertion`
  - `expected_track_counts`

### 3) Rulebook 재명시
- 파일: `invest/docs/strategy/RULEBOOK_V1_20260218.md` (섹션 16)
- 추가 조항:
  - 12-baseline 하드체크(`track_counts 3/3/3/3`) 불일치 시 FAIL_STOP
  - 결과 JSON 필수 필드(`protocol_enforced`, `track_counts_assertion`)

## 검증
### A. 컴파일 검증
- `python3 -m py_compile invest/scripts/stage05_baseline_guard.py invest/scripts/stage05_incremental_external_v3_20_kr.py invest/scripts/stage05_incremental_external_v3_21_kr.py invest/scripts/stage05_full_recompute_v3_22_kr.py`
- 결과: PASS

### B. 최소 실행 검증(Stage05)
- `python3 invest/scripts/stage05_incremental_external_v3_20_kr.py`
  - 출력 경로: `invest/reports/stage_updates/stage05/stage05_result_v3_20_kr.md` 등
  - gate1: PASS
- `python3 invest/scripts/stage05_incremental_external_v3_21_kr.py`
  - 출력 경로: `invest/reports/stage_updates/stage05/stage05_result_v3_21_kr.md` 등
  - gate1: PASS

### C. JSON 필드 검증
- `invest/results/validated/stage05_baselines_v3_20_kr.json`
  - `protocol_enforced=true`
  - `track_counts_assertion=pass`
- `invest/results/validated/stage05_baselines_v3_21_kr.json`
  - `protocol_enforced=true`
  - `track_counts_assertion=pass`

### D. FAIL_STOP 동작 검증(프로브)
- 실행: `enforce_track_counts_or_fail_stop({'numeric':3,'qualitative':2,'hybrid':3,'external-pretrained':3}, ...)`
- 결과:
  - RuntimeError: `FAIL_STOP: 12-baseline protocol violation ...`
  - 실패 JSON 생성: `invest/results/test/stage05_baseline_guard_failstop_probe.json`
  - 필드: `status=FAIL_STOP`, `protocol_enforced=true`, `track_counts_assertion=fail`

## 재발방지 가드
- 실행 스크립트 레벨 하드가드 + Rulebook 문서 규범을 이중 적용.
- 후속 Stage05 계열(v3_22 포함)도 동일 공용가드 모듈 재사용하도록 정착.

## 최종 정합성 체크 결과
- **PASS**
