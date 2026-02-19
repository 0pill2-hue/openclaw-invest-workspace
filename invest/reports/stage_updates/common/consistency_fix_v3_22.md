# consistency_fix_v3_22

## 이슈 요약
사용자 지적사항:
- "12개 모델로 돌리기로 했는데 왜 안 지켰냐"
- "정합성 안 깨지게 해"

핵심 문제:
1) Stage05 12-baseline(3/3/3/3) 강제가 소프트 처리되어 FAIL_STOP이 보장되지 않음
2) `reports/stage_updates/stageXX_...` 구경로 참조가 남아 경로 구조 정합성 혼재
3) 일부 문서/링크가 신규 폴더형 구조와 불일치

---

## 조치 내역
### A) 12-baseline 강제 가드
- 공용 가드 모듈 추가: `invest/scripts/stage05_baseline_guard.py`
- 적용 스크립트:
  - `invest/scripts/stage05_incremental_external_v3_20_kr.py`
  - `invest/scripts/stage05_incremental_external_v3_21_kr.py`
  - `invest/scripts/stage05_full_recompute_v3_22_kr.py`
- 강제 정책:
  - `track_counts != {numeric:3, qualitative:3, hybrid:3, external-pretrained:3}` → **FAIL_STOP**
  - 결과 JSON 필수 기록:
    - `protocol_enforced=true`
    - `track_counts_assertion=pass/fail`

### B) Rulebook 재명시
- `invest/strategy/RULEBOOK_V1_20260218.md` 섹션 16 보강
  - 12-baseline 하드체크 + FAIL_STOP + 필수 JSON 필드 명시

### C) 경로 전수 동기화
- 구형 참조 `reports/stage_updates/stageNN_...` 전수 치환
  - → `reports/stage_updates/stageNN/stageNN_...`
- 대상 범위: `invest/scripts/`, `docs/`, `invest/strategy/`, `reports` 문서/템플릿
- canonical 문서 경로 보정 + 누락 링크 placeholder 2건 보완

---

## 검증 결과
### 1) 구경로 잔존
- `git grep -n -E "reports/stage_updates/stage[0-9]{2}_" -- scripts docs invest/strategy reports/stage_updates`
- 결과: **0건**

### 2) Stage05 최소 실행
- `python3 invest/scripts/stage05_incremental_external_v3_20_kr.py` → PASS
  - 출력: `reports/stage_updates/stage05/stage05_result_v3_20_kr.md` 등
- `python3 invest/scripts/stage05_incremental_external_v3_21_kr.py` → PASS
  - 출력: `reports/stage_updates/stage05/stage05_result_v3_21_kr.md` 등

### 3) 12-baseline 가드 검증
- v3_20/v3_21 결과 JSON 필드 확인:
  - `protocol_enforced=true`
  - `track_counts_assertion=pass`
- 실패 프로브 확인:
  - `invest/results/test/stage05_baseline_guard_failstop_probe.json`
  - `status=FAIL_STOP`, `track_counts_assertion=fail`

### 4) 링크/출력 경로 검증
- scope 내 참조 134건 중 미존재 7건은
  - 템플릿 placeholder 또는 실행 시 생성되는 동적 산출물로 허용목록 처리
- 허용목록 외 깨진 링크: **0건**

---

## 재발방지 가드
1. 공용 코드 가드(실행 시점): `enforce_track_counts_or_fail_stop`
2. 규정 가드(문서 시점): Rulebook 섹션 16 하드조항
3. 구조 가드(경로 시점): stageNN 폴더형 경로 고정 + grep 검증

## 최종 판정
- **정합성 복구 핫픽스: PASS**
- 상세 근거:
  - `reports/stage_updates/common/baseline12_guard_report_v3_22.md`
  - `reports/stage_updates/common/path_migration_report_v3_22.md`
