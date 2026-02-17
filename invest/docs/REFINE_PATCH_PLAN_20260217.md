# [2026-02-17] 데이터 정제 및 검증 로직 즉시 보완안

## 1. 구체 규칙 (Refinement Rules)

### A. `onepass_refine_full.py` 추가 규칙
- **노이즈 스킵**: `pd.read_csv(..., comment='#', skip_blank_lines=True)` 적용으로 불완전한 헤더/주석 처리.
- **날짜 무결성**: 
  - `Date` 컬럼의 '0000-00-00' 또는 빈 문자열을 즉시 격리(Quarantine).
  - 미래 날짜(Today + 1) 레코드 자동 격리.
- **OHLC 정밀화**: 
  - `Volume`이 0인데 `Close`가 변동한 경우 '데이터 의심' 플래그 (또는 격리).
  - 수정주가(Adj Close)가 Close보다 큰 경우 역전 현상 체크.

### B. `validate_refine_independent.py` 강화
- **Missing Row Detection**: 
  - `kr/ohlcv`, `us/ohlcv` 대상 영업일(Business Day) 기준 누락 구간 탐지.
  - 5거래일 연속 누락 시 `FAIL` 판정.
- **Distribution Check**:
  - 특정 폴더 내 전체 파일의 평균 레코드 수 대비 +/- 50% 편차 발생 시 `WARN`.

---

## 2. 재실행 플랜 (Rerun Plan)

1.  **Stage 1: 코드 반영 (ETA: 10m)**
    - `onepass_refine_full.py` 내 `_normalize_columns` 및 `sanitize_ohlcv` 함수 업데이트.
    - `validate_refine_independent.py` 내 `_check_record_preservation` 로직 보강.
2.  **Stage 2: 전체 재정제 (ETA: 20m)**
    - `python3 invest/scripts/onepass_refine_full.py` 실행.
    - `invest/data/clean/production` 갱신 확인.
3.  **Stage 3: 독립 검증 (ETA: 10m)**
    - `python3 invest/scripts/validate_refine_independent.py` 실행.
    - `reports/qc/verdict_*.json` 최종 확인.

---

## 3. 주인님 보고 포맷 (Short Report)

> **[데이터 정제/검증 완료 보고]**
> - **작업**: OHLCV 날짜 무결성 강화 및 영업일 누락 탐지 반영
> - **결과**: `PASS: N / WARN: M / FAIL: K` (검증 리포트 참조)
> - **조치**: FAIL 항목 원천 데이터 재수집 또는 Quarantine 유지
> - **경로**: `reports/qc/VALIDATION_INDEPENDENT_{TS}.md`
