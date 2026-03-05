# OPERATING_GOVERNANCE.md

Last updated: 2026-03-05 00:07 KST
Purpose: 게이트 운영의 고정 기준(임계치 버전, 실행 SOP, 보고 SLA, Git 규칙)을 단일 문서로 관리

## 1) Gate Threshold Version (고정)
- 현재 운영 버전: `gate_threshold_v1_20260218`
- 기준 원문: `invest/docs/RULEBOOK_MASTER.md` 11장(11-1/11-2/11-3)
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
- Push 타이밍/예외 정책의 단일 소스(SSOT): `CONTRIBUTING.md`의 `2-1) Push 타이밍 정책`
  - `main` 직접 push 금지
  - 커밋 후 작업 브랜치 즉시 push 원칙

## 5) 모델 운용 모드 선택 원칙 (신규)
- 일반 운영/대량 반복: 기본 모드(속도 우선)
- 중요 의사결정/검수/최종 판정: 정밀 모드(정확성 우선)
- 동일 작업에서 모드 변경 시 보고문에 변경 이유 1줄 기록

## 6) 임시 복구 팁 취급 원칙 (신규)
- 커뮤니티 우회 팁(예: 제한 해제 요청)은 `임시 대응`으로만 취급한다.
- 공식/재현 검증 전에는 표준 SOP에 고정 반영 금지.
- 적용 시 반드시 `케이스 한정`으로 사용하고, 실패 시 즉시 원복/대체 경로로 전환.

## 7) 운영 경고 등급 (MUST/SHOULD/CAN)
- MUST (즉시 경고/강제)
  - 복구불가 손실/보안/외부영향 위험
  - 보고 약속(SLA) 초과
  - health-state stale/missing
  - pendingMessages 임계치 초과
- SHOULD (다음 heartbeat 1회 권고)
  - 품질 저하 가능성 항목
  - 지표/문서 경미한 누락
- CAN (무경고)
  - 편의성/정리성 개선 항목
- 소음 통제
  - 동일 경고 4시간 이내 재전송 금지
  - 야간(22:00~09:00)은 실제 장애만 경고

## 8) 정리/이관 작업 프로토콜 (Archive-first)
1. 후보 목록 확정 + 미참조 증거 확보
2. 불확실 항목은 삭제 금지(`HOLD`)
3. 물리 삭제보다 archive 격리 우선
4. 최종 검증: 경로일치/참조무결성/오삭제 없음

## 9) 충돌 시 우선순위
1. `invest/docs/RULEBOOK_MASTER.md`
2. `docs/openclaw/OPERATING_GOVERNANCE.md`
3. `invest/docs/OPERATIONS_SOP.md`
4. `CONTRIBUTING.md`
