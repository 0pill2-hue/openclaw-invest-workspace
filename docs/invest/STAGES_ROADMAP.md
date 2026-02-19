# Investment 12-Stage Roadmap

Version: 2026-02-19 (Trust-Rebuild)
Scope: Rulebook V3.3 aligned lifecycle

## Stage 01 — Data Collection
- 정량/정성 데이터 수집 파이프라인 구축
- 소스별 스키마 고정, raw 보관

## Stage 02 — Data Cleaning
- 결측/중복/이상치 정제
- 룰 기반 정합성 오류 제거

## Stage 03 — Cleaning Validation
- 정제 결과 품질 검증
- 데이터 lineage 및 재현성 체크

## Stage 04 — Feature / Value Build
- 모델 입력 피처/점수 산출
- 규칙 기반 신호 준비

## Stage 05 — Rulebook V3.3 Backtest Engine
- Survival / Quality-Keyword / Focus 1-6 / Trend-Trailing / Hybrid Crisis 하드 적용
- 베이스라인 성능 및 동작 검증
- 코드-문서 동기화 증거 고정

## Stage 06 — Candidate Generation
- 후보 전략/파라미터 생성
- 규칙 위반 후보 자동 제외

## Stage 07 — Cost / Turnover / Risk Cut
- 거래비용/회전율/리스크 컷오프
- 실거래 가능성 기준 선별

## Stage 08 — Purged CV / OOS Validation
- 시간누수 방지 검증
- Out-of-sample 일관성 확인

## Stage 09 — Cross Review / Auditor Gate
- 다중 감사자 교차 검토
- 논리/일관성/품질 게이트 통과

## Stage 10 — Final Strategy Freeze (Pre-GoLive Gate)
- 채택 전략 동결(모델/파라미터/데이터 버전 해시 고정)
- 프로덕션 설정 초안 확정
- **Stage 11 진입 허용 조건**
  1) Stage09 APPROVE 증빙
  2) 실패 정책(runbook) + kill switch 책임자/승인권자 지정
  3) 롤백 기준선(성능/리스크/운영) 수치화

## Stage 11 — Paper Trading / Shadow Deployment (Safety Rehearsal Gate)
- 브로커/주문/체결/포지션 연동 완료(모의/섀도우 모드)
- 주문 상태 머신(NEW/PARTIAL/FILLED/CANCELED/REJECTED) 리허설 검증
- **모니터링/알림/서킷브레이커를 이 단계에서 먼저 활성화**
  - PnL, DD, 체결지연, 데이터 지연, API 오류율 실시간 관측
  - DD/데이터결손/신호버스트/오류율 임계치 테스트(강제 트립 포함)
- 소규모 드라이런(제한 종목·제한 주문수·제한 노출)으로 운영 리스크 점검
- **Stage 12 승격 허용 조건 (10→11→12 전환 핵심 안전게이트)**
  1) 연속 N일(권장 10~20영업일) 운영 안정
  2) 실행 품질(슬리피지/체결지연) 허용 범위 충족
  3) kill switch 및 복구 runbook 실제 리허설 PASS
  4) 장애 재현 1회 이상 + 복구 시간(SLA) 충족

## Stage 12 — Controlled Live Rollout & Continuous Monitoring
- 실거래는 단계적 증설(노출 5% → 25% → 50% → 100%) 원칙
- 각 증설 단계마다 중간 승인 게이트(성과/리스크/운영) 통과 필요
- 상시 서킷브레이커 운영:
  - DD 임계치 초과 시 신규진입 중단
  - 데이터 결손 연속 발생 시 해당 심볼 차단
  - 신호 과밀(버스트) 시 일시 홀드
  - 리포트 SLA 위반 시 즉시 알림
- 운영 안전장치:
  - kill switch (수동/자동)
  - 복구 절차(runbook) 및 재기동 체크리스트
  - 감사 로그/사후 포렌식 보존
- 롤백 정책:
  - 임계치 위반/운영 장애 발생 시 이전 노출 단계로 즉시 복귀
  - 재발/중대 장애 시 Stage 11(섀도우)로 강등 후 재검증

---

## Stage Exit Rule
각 Stage는 다음 3가지 증거가 있어야 다음 단계로 이동:
1. 산출물 파일(문서/코드/리포트)
2. 검증 로그(실행/테스트/체크 결과)
3. 실패 정책(failure policy) 및 대응 기록

## Final Decision Labels
- PASS: 게이트 전부 충족, 다음 Stage 진행 가능
- CONDITIONAL: 핵심은 충족했으나 보완 항목 존재(보완 후 진행)
- FAIL: 핵심 게이트 미충족, 진행 금지
