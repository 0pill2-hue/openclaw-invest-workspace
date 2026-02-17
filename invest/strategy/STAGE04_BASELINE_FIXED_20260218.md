# STAGE04 BASELINE FIXED (2026-02-18 00:23 KST)

## 목적
3트랙(정량/텍스트/혼합)을 동일 조건으로 비교해 5단계 진입용 베이스라인을 고정한다.

## 트랙 정의
1. Quant Track: 가격/수급 중심
2. Text Track: 블로그/텔레 중심(초기 저가중치)
3. Hybrid Track: Quant + Text 결합

## 입력/전처리 고정
- 입력: validated snapshot 기준 데이터만 사용
- 3단계 밸류 점수 사용 (스무딩 포함)
- 이상치/누락: 즉시삭제 금지, PENDING 정책 유지
- 유동성/거래가능성 필터 선행

## 비용/교체 규칙(고정)
- 왕복 비용 패널티: 3~4%
- 교체 임계치: 기존 대비 +15% 우위일 때만 교체

## 비교 조건(고정)
- 동일 기간
- 동일 유니버스
- 동일 비용/리스크 패널티
- 동일 리밸런싱 주기

## 평가 기준(고정)
- 수익 70% + 리스크효율 30%
- 리스크효율: MDD/손익비/샤프 중심
- Turnover 과다 시 감점

## 출력/판정
- 트랙별 성능표 1개
- 우선순위 1~3위
- 통과 트랙만 5단계로 전달

## 거버넌스
- 본 단계 결과 등급: DRAFT
- 7단계(Purged CV + OOS) 통과 전 채택 금지

## 변경 규칙
- 본 문서 변경 시 반드시 아래 동시 업데이트
  1) invest/strategy/strategy_v1_replication_spec_20260217.md
  2) reports/stage_updates/stage04_baseline_3track.md
  3) memory/2026-02-18.md (what/why/next)
