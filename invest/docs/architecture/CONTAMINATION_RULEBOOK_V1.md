# CONTAMINATION_RULEBOOK_V1

기준 시각: 2026-02-16 (UTC 저장 / KST 보고)

## 목적
- 오염 데이터를 **즉시 분리(quarantine)**하고, 정상 급변 데이터는 **검수 후 복구**하기 위한 판정 기준 고정
- 자동 배치(`organize_existing_data.py`, 수집기 sanitize 단계)와 동일 기준으로 운영

## 공통 원칙
1. **raw 불변**: 원본은 절대 수정하지 않음
2. **자동 제외 금지**: 범위 초과는 즉시 삭제하지 않고 `quarantine + reason`으로 보존
3. **정상 급변 가능성 분리**: 급등락/거래급증은 맥락(공시/뉴스/거래대금) 검수 후 복구 가능
4. **판정 우선순위**: 구조오류 > 물리불가능 > 저유동 왜곡 > 급변 검수

---

## 판정 코드 및 기준

### A. OHLCV_NONPOS_PRICE
- 조건: `open<=0 OR high<=0 OR low<=0 OR close<=0`
- 판정: **오염 확정**
- 조치: 즉시 quarantine
- 복구: 불가 (원천 재수집만 허용)

### B. OHLCV_ZERO_CANDLE
- 조건: `open=high=low=close=0`
- 판정: **오염 확정**
- 조치: 즉시 quarantine
- 복구: 불가 (원천 재수집만 허용)

### C. OHLCV_LOW_VOLUME
- 조건: `volume < 10`
- 판정: **신호 입력 금지 데이터**
- 조치: quarantine (분석 입력 제외)
- 예외 복구: 없음 (단, 장중/비정규 거래 구간 별도 feed가 있으면 source 분리 후 재판정)

### D. OHLCV_RET_SPIKE
- 조건: `abs(close.pct_change()) > 0.35`
- 1차 판정: **검수 필요(보류)**
- 자동 조치: quarantine + reason=`OHLCV_RET_SPIKE_PENDING_REVIEW`
- 수동 검수 통과 조건(모두 충족 시 clean 복귀 가능):
  1) 당일 거래대금 `>= 1e8`
  2) 동일 일자 공시/뉴스 이벤트 근거 존재
  3) 인접 3영업일 가격 연속성(역분할/액면변경 제외)

### E. SUPPLY_INST_EXTREME
- 조건: `inst/net` 계열 지표에서 분모 왜곡으로 비정상 급등 (예: 극단치)
- 1차 판정: **검수 필요(보류)**
- 자동 조치: quarantine + reason=`SUPPLY_INST_EXTREME_PENDING_REVIEW`
- 수동 검수 통과 조건:
  1) 분모(거래대금/거래량) 최소 임계치 충족
  2) 동일 일자 타 지표와 방향 일관성
  3) 단일 레코드 고립 이상치가 아님

---

## 자동 운영 매핑
- `확정 오염`: NONPOS_PRICE, ZERO_CANDLE, LOW_VOLUME
  - 즉시 quarantine, clean 입력 금지
- `검수 보류`: RET_SPIKE, SUPPLY_INST_EXTREME
  - quarantine에 두고 audit에 근거 기록 후 복구 여부 판정

## 리포트 기준
- 시간별 보고 항목:
  1) 신규 quarantine 건수(코드별)
  2) 보류 건수(PENDING_REVIEW)
  3) 검수 후 복귀 건수(restore)
- 일간 보고 항목:
  1) 오염률(신규/누적)
  2) 보류→복구 전환율
  3) 소스별 재발 상위 10

## 현재 스캔 분포(참고)
- `SUPPLY_INST_EXTREME`: 3,636
- `OHLCV_LOW_VOLUME`: 2,866
- `OHLCV_NONPOS_PRICE`: 2,324
- `OHLCV_ZERO_CANDLE`: 2,323
- `OHLCV_RET_SPIKE`: 89

## 다음 버전(v1.1) 예정
- 검수 보류 항목(RET_SPIKE, SUPPLY_INST_EXTREME)에 대한 반자동 복귀 스크립트 추가
- reason code를 `config/schemas`와 동기화
