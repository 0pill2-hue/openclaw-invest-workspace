# DOC_TEMPLATES.md

Last updated: 2026-02-18 08:02 KST
Purpose: 브레인스토밍 기반 문서 표준 확정안 (재현성 우선, 과문서화 방지)

## 1) 표준 원칙 (5)
1. **실행 재현 우선**: 문서만 보고 동일 실행/판정을 재현 가능해야 함.
2. **최소 충분 원칙**: 필수 필드만 강제, 설명성 문장은 선택.
3. **증빙 경로 의무화**: 모든 완료/판정은 파일 경로 proof 필수.
4. **버전/기준 단일화**: 기준 충돌 시 최신 canonical 1개만 유지.
5. **실패 분기 명시**: 실패 시 다음 행동(중단/재시도/롤백)을 문서에 고정.

## 2) 문서 유형별 필드 표준

### A. Stage 문서 (`invest/reports/stage_updates/stage*.md`)
- **필수**: `purpose`, `inputs`, `run_command|process`, `outputs`, `quality_gate(s)`, `failure_policy|gate_fail_protocol`, `proof`
- **선택**: `owner`, `expected_duration`, `notes`

### B. 운영 문서 (`docs/openclaw/*.md` 중 운영 기준)
- **필수**: `scope`, `trigger`, `procedure`, `exception`, `SLA`, `proof`
- **선택**: `escalation`, `rollback`, `faq`

### C. 실행 리포트 (`reports/**/*.md|json`)
- **필수**: `execution_summary`, `changes`, `result_table`, `judgment(PASS|FAIL)`, `risk`, `next_action`, `proof_paths`, `grade`
- **선택**: `appendix`, `raw_log_excerpt`, `review_comment`

## 3) 금지 패턴
- 의미 불명 상태값만 기록: `잘됨`, `문제없음` (근거/수치 없이)
- 실행 명령 없이 결과만 보고
- `proof` 없는 완료 처리
- 구버전 기준과 신버전 기준 동시 IN_PROGRESS 유지
- 우회 팁을 검증 없이 SOP 표준으로 승격

## 4) 도입 순서 (저위험)
1. 신규 문서부터 본 템플릿 즉시 적용
2. Stage 01~11 순차 보강(필수 필드 누락만 우선 보정)
3. 운영 문서 보강(`SLA/exception/proof` 누락분)
4. 리포트 템플릿 적용 및 자동 점검 스크립트 연동

## 5) 완료 판정
- 필수 필드 1개라도 누락 시 `IN_PROGRESS`
- `proof` 확인 후에만 `DONE`
