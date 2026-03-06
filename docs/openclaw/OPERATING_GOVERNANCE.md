# OPERATING_GOVERNANCE.md

Last updated: 2026-03-06 KST  
Purpose: 게이트 운영의 고정 기준(임계치 버전, 실행 SOP, 보고 SLA, Git 규칙)을 단일 문서로 관리

## 1) Gate Threshold Version (고정)
- 현재 운영 버전: `gate_threshold_v1_20260218`
- 기준 원문: `invest/docs/RULEBOOK_MASTER.md` 11장(11-1/11-2/11-3)
- 임계치 변경은 버전 증가 없이는 금지

## 2) 실행 SOP (고정 순서)
1. stage 실행(run)
2. stage gate check
3. PASS면 다음 stage 진행
4. FAIL이면 `gate_fail_protocol` 분기로 복귀
5. 재실행 후 동일 gate 재검증

- FAIL 상태 우회 금지
- 최소 증빙: 실행 로그 1개 + 결과 리포트 1개 + manifest 1개

## 3) Report SLA
- 짧은 작업(<=10분): 시작/완료 보고
- 긴 작업(>10분) 또는 중요 작업: 시작/중간/완료 보고
- SLA 위반 시 즉시 지연 알림

## 4) Git 운영 규칙
- 4/5 게이트 통과 후 커밋/푸시를 우선 수행
- 커밋 전 필수 체크:
  1) 민감정보 포함 여부
  2) 실행/문법/게이트 검증 통과 여부
  3) TASKS + memory/YYYY-MM-DD.md 업데이트 필요 여부
- Push 타이밍 SSOT: `CONTRIBUTING.md`의 `2-1) Push 타이밍 정책`

## 5) 모델 운용 원칙
- 1번 뇌(GPT-5.4): 기본 실행, 설계, 판단, 검증, 최종 결정
- 2번 뇌(로컬뇌): 폴백, 요약/압축, 크롤링/수집, 배치/반복, 단순 지원
- 기본은 메인이 직접 수행한다.
- 예외적으로만 위임/보조를 사용한다: 장시간, 반복, 대량, 크롤링, 배치, 비동기 작업.

## 6) 교차검토 원칙
- 모든 작업의 의무가 아니라 중요 변경에서만 1회 적용
- 중요 변경 = 전략/게이트/운영크론/데이터오염/외부영향 관련

## 7) 운영 경고 등급
- MUST: 복구불가 손실/보안/외부영향 위험, SLA 초과, health-state 이상
- SHOULD: 품질 저하 가능성, 지표/문서 경미한 누락
- CAN: 편의성 개선 항목
- 동일 경고 4시간 이내 재전송 금지
- 야간(22:00~09:00)은 실제 장애만 경고

## 8) 정리/이관 작업 프로토콜
1. 후보 목록 확정 + 미참조 증거 확보
2. 불확실 항목은 삭제 금지(`HOLD`)
3. 물리 삭제보다 archive 격리 우선
4. 최종 검증: 경로일치/참조무결성/오삭제 없음

## 9) 충돌 시 우선순위
1. `invest/docs/RULEBOOK_MASTER.md`
2. `docs/openclaw/OPERATING_GOVERNANCE.md`
3. `invest/docs/OPERATIONS_SOP.md`
4. `CONTRIBUTING.md`
