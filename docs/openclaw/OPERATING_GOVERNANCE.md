# OPERATING_GOVERNANCE.md

Last updated: 2026-02-18 06:50 KST
Purpose: 게이트 운영의 고정 기준(임계치 버전, 실행 SOP, 보고 SLA, Git 규칙)을 단일 문서로 관리

## 1) Gate Threshold Version (고정)
- 현재 운영 버전: `gate_threshold_v1_20260218`
- 기준 원문: `invest/strategy/RULEBOOK_V1_20260218.md` 11장(11-1/11-2/11-3)
- 변경 원칙:
  - 임계치 변경은 버전 증가(`v2_...`) 없이는 금지
  - 변경 시 stage 문서 + RULEBOOK + 본 문서 동시 갱신

## 2) 실행 SOP (고정 순서)
1. stage 실행(run)
2. stage gate check
3. PASS면 다음 stage 진행
4. FAIL이면 `gate_fail_protocol` 분기로 복귀
5. 재실행 후 동일 gate 재검증

- 우회 금지: FAIL 상태에서 downstream 진입 금지
- 최소 증빙: 실행 로그 1개 + 결과 리포트 1개 + manifest 1개

## 3) Report SLA (고정)
- 짧은 작업(<=10분): 시작/완료 2점 보고
- 긴 작업(>10분) 또는 중요 작업: 시작/중간/완료 3점 보고
- SLA 위반: 약속 시각 +15분 초과 시 즉시 지연 알림(RP-01)

## 4) Git 운영 규칙 (고정)
- 4/5 게이트 통과 후: `Git 업데이트(커밋/푸시)`를 리팩토링보다 먼저 수행
- 커밋 전 필수 체크:
  1) 민감정보 포함 여부
  2) 실행/문법/게이트 검증 통과 여부
  3) TASKS.md + memory/YYYY-MM-DD.md 업데이트 여부
- 커밋 메시지:
  - 기본: 한 줄 요약
  - 긴급 수정: `hotfix:` 접두어

## 5) 충돌 시 우선순위
1. `invest/strategy/RULEBOOK_V1_20260218.md`
2. `docs/openclaw/OPERATING_GOVERNANCE.md`
3. `OPERATIONS_SOP.md`
