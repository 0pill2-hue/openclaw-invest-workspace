# Strategy V1 Replication Spec (2026-02-17)

> 목적: **이 문서만으로 동일 파이프라인/동일 산출물을 재현**할 수 있도록 고정 스펙 제공.

---

## A. 환경 고정
- OS: macOS (Darwin arm64)
- Python: 3.14.x
- 작업 루트: `/Users/jobiseu/.openclaw/workspace`
- 가상환경: `.venv`

### 실행 공통
```bash
cd /Users/jobiseu/.openclaw/workspace
source .venv/bin/activate
```

---

## B. 데이터 스냅샷 고정
### B-1. 입력 Raw 루트
- `invest/data/raw/**`

### B-2. 검증 통과 스냅샷 (현재 기준)
- `invest/data/validated/snapshots/20260217_231426/production`
- 파일수: 33,915

### B-3. 재현시 필수
- 학습/산출 입력은 반드시 위 스냅샷만 사용
- raw 증분 수집분은 다음 스냅샷으로 분리

---

## C. 단계별 고정 절차 (11단계)
1) 수집
2) 정제
3) 정제검증
4) VALIDATED 밸류 산출
5) 3트랙 고정(정량/텍스트/혼합)
6) 후보군 1차 생성
7) 후보군 컷
8) Purged CV+OOS
9) 비용/턴오버/리스크
10) 교차리뷰
11) 채택/보류/승격

---

## D. 정제 스펙 (2단계)
스크립트: `invest/scripts/onepass_refine_full.py`

### D-1. OHLCV 규칙
- Date 파싱 실패 격리
- Close 결측/<=0 격리
- OHLC 논리 위반 격리
  - High < Low
  - High < Close
  - Low > Close
- `Volume>0 & Open/High/Low<=0` 격리
- Date 정렬 + 중복 Date keep=last
- 수익률 outlier는 정제단계 즉시 삭제 금지 (검증/PENDING 단계로 이관)

### D-2. Supply 규칙
- 컬럼 표준화(Date/Inst/Corp/Indiv/Foreign/Total)
- Date invalid 및 전체 수치결측 행 격리
- Date 정렬 + 중복 제거

### D-3. Text/JSON
- 짧은/빈 텍스트 격리(reason 기록)
- JSON 파싱 실패 격리(reason 기록)

### D-4. 중복 정제 방지
- 인덱스 파일: `invest/data/clean/production/_processed_index.json`
- 입력 파일 시그니처(크기+mtime+path 해시) 동일 시 스킵

---

## E. 정제검증 스펙 (3단계)
스크립트: `invest/scripts/validate_refine_independent.py`

### E-1. Guardrails
- GR-1 보존법칙: raw vs clean+quarantine
- GR-2 verdict/evidence 분리
- GR-3 L3 cap 20%

### E-2. outlier 정책
- `return_outlier`는 즉시 오류 확정 금지
- PENDING으로 분리 후 이벤트/웹 교차검증

### E-3. 통과 기준
- FAIL=0 필수
- WARN은 원인 명시 + PENDING/정상확정 분기

---

## F. 4단계 밸류 산출 스펙 (핵심)
스크립트: `invest/scripts/calculate_stage3_values.py`
출력 루트: `invest/data/value/stage3/{kr|us}/ohlcv/*.csv`

### F-1. 팩터 정의
- `VAL_MOM_20`: Close 20일 모멘텀 스무딩(EMA 20, adaptive)
- `VAL_FLOW_10`: 일수익률 proxy -> Median(5) -> EMA(10)
- `VAL_LIQ_WIN`: Turnover(=Close*Volume) Winsor(2.5%, 97.5%)
- `VAL_RISK_10`: ATR20 Winsor(1%,99%) -> EMA(10), 점수 계산 시 역부호

### F-2. 정규화/결합
- 롤링 Z-score(window=120, min_periods=20)
- 결합식:
  - Momentum 0.35
  - Flow 0.25
  - Liquidity 0.20
  - RiskAdj 0.20
- `VALUE_SCORE_RAW = 0.35*Z(MOM)+0.25*Z(FLOW)+0.20*Z(LIQ)+0.20*Z(RISK_ADJ)`
- `VALUE_SCORE = adaptive_ema(VALUE_SCORE_RAW, span=10)`

### F-3. Adaptive rule
- 변동성 비율(vol/baseline)
  - >1.5 : span 축소(빠르게)
  - <0.7 : span 확대(느리게)
  - else: 기본 span 유지
- 스무딩 단계 최대 2회 제한

---

## G. 불균형(imbalance) 스펙
- 보정 적용 전 필수 게이트:
  1) TimeSeries 분리 후 보정(분리 전 보정 금지)
  2) 유동성/거래가능성 필터 선행
  3) 소형주 비중 하드캡
  4) Calibration 검증 통과
- 금융 시계열에서 SMOTE 과보정 금지(합성비율 상한 운영)

---

## H. 검증/채택 스펙
- 4단계 산출물은 DRAFT
- 채택은 8~10단계 검증 완료 후 11단계에서만
- 7단계(Purged CV+OOS)는 **필수 게이트**

---

## I. 실행 명령어 (재현 순서)
```bash
# 1) 정제
.venv/bin/python3 invest/scripts/onepass_refine_full.py

# 2) 정제검증
.venv/bin/python3 invest/scripts/validate_refine_independent.py

# 3) 4단계 밸류 산출
.venv/bin/python3 invest/scripts/calculate_stage3_values.py
```

---

## J. 산출물 체크포인트
- 정제 리포트: `reports/qc/FULL_REFINE_REPORT_*.md`
- 검증 리포트: `reports/qc/VALIDATION_INDEPENDENT_*.md`
- 밸류 실행 리포트(JSON): `reports/stage_updates/STAGE3_VALUE_RUN_*.json`

필수 확인:
- FAIL = 0
- VALUE 산출 errors = 0
- 스냅샷 기준 입력 사용 여부 확인

---

## K. 변경관리 규칙
파라미터/가중치/게이트 변경 시 아래 3개 동시 업데이트 필수:
1) 본 문서
2) `reports/stage_updates/stage03/stage03_cleaning_validation.md`
3) `memory/YYYY-MM-DD.md`

변경 기록 형식:
- what changed
- why changed
- proof path (리포트/로그/파일)
