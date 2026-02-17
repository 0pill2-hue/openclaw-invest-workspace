# STAGE05 BASELINE FIXED RUN (2026-02-18)

- 등급: DRAFT (TEST ONLY)
- 7단계(Purged CV/OOS) 전 채택 금지

## 1) 날짜 정합 이슈 최소 수정
- 원인: 월말 리밸런싱 인덱스가 달력 월말로 생성되어 실제 거래일 인덱스와 불일치(KeyError).
- 수정: 기존 월별 리밸런싱 로직은 유지하고, 월 그룹의 **실제 마지막 거래일 값**만 사용하도록 최소 교체.

## 2) 3트랙 동일 조건 비교(Quant/Text/Hybrid)

| Track | Return | CAGR | MDD | Sharpe | Turnover | Cost Erosion | r3M Sharpe Min | r3M Alpha Min |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Quant | 31.77% | 20.23% | -12.64% | 1.054 | 0.962 | 0.96% | -0.818 | -15.45% |
| Text | 45.98% | 28.74% | -10.05% | 1.501 | 0.966 | 0.97% | -0.060 | -6.27% |
| Hybrid | 32.76% | 20.83% | -7.50% | 1.071 | 0.948 | 0.95% | -0.990 | -11.23% |

## 3) drop_criteria_v1(보수형) 판정
- Quant: **탈락**
  - hard: Rolling3M Sharpe<-0.2 위반 (-0.818)
- Text: **유지**
- Hybrid: **탈락**
  - hard: Rolling3M Sharpe<-0.1 위반 (-0.990)

## 4) 운영/감시 후보 지정 근거(확정 아님)
- 운영 후보1: Text
- 감시 후보2: ['Quant', 'Hybrid']
- 근거: 후보선정: total_return/sharpe 우선순위 1위 트랙=Text
- 근거: 후보감시: 비선정 트랙 ['Quant', 'Hybrid']를 경고 레이어로 유지(RULEBOOK 3검증1운영)
- 근거: 주의: 본 결과는 DRAFT이며 7단계(Purged CV/OOS) 전 채택/실운영 전환 금지
