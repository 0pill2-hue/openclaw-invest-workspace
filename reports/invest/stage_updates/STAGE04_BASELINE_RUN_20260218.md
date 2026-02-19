# STAGE04 BASELINE RUN (2026-02-18)
> RESULT_GRADE: **DRAFT**  
> TEST ONLY  
> **7단계(Purged CV/OOS) 통과 전 채택 금지**

## 실행 상태
- 상태: **실행 실패 (DRAFT 실패보고)**
- 원인: 월말 리밸런싱 인덱스(`ME`)와 실제 거래일 인덱스 불일치로 `KeyError(Timestamp month-end)` 발생
- 추가 원인: 기존 엔트리포인트(`invest/backtest_compare.py`)는 2트랙(내지표/이웃지표) 중심이라, 3트랙(Quant/Text/Hybrid) 동일조건 성능지표(수익/MDD/Sharpe/Turnover/비용잠식률) 직접 산출 로직이 부족

## 1) 트랙별 성능 비교표 (실패로 미산출)
| Track | 수익 | MDD | Sharpe | Turnover | 비용잠식률 |
|---|---:|---:|---:|---:|---:|
| Quant | N/A | N/A | N/A | N/A | N/A |
| Text | N/A | N/A | N/A | N/A | N/A |
| Hybrid | N/A | N/A | N/A | N/A | N/A |

## 2) 상태 판정(유지/보류/탈락) + hard/soft 근거
- Quant: 보류 (근거 데이터 미산출)
- Text: 보류 (근거 데이터 미산출)
- Hybrid: 보류 (근거 데이터 미산출)
- hard/soft 적용 상태: **drop_criteria_v1 적용 시도했으나 입력 지표 미산출로 판정 유예**

## 3) 운영 1개 + 감시 2개 역할 확정 (임시)
- 운영(임시): Hybrid
- 감시(임시): Quant, Text
- 비고: 성능표 재산출 전까지 임시 배정이며, 채택/승격 아님

## 4) 재시도 계획
1. 리밸런싱 날짜를 `resample('ME').last()`의 **실제 거래일 값**으로 강제 치환
2. 기존 `invest/backtest_compare.py` 신호 계산부 재사용, 트랙 래퍼(Quant/Text/Hybrid)만 최소 추가
3. 동일 조건(기간/유니버스/비용/리스크/리밸런싱) 재실행 후 성능표/판정/역할 확정 재작성
4. 결과는 계속 **DRAFT(TEST ONLY)**로 유지

---
본 문서는 실패 원인 및 재시도 계획을 포함한 DRAFT 실패보고입니다.
