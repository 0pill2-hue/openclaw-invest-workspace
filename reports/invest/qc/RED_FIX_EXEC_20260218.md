# RED FIX Execution Report — 2026-02-18

## Scope (긴급 조치 3개)
1. `feature_engineer.py` raw 경로 참조 제거 + raw 참조 가드
2. clean/quarantine 소급 재분리 배치 실행 + 결과 리포트 생성
3. stage5 실행 경로에 manifest(lineage) 생성 의무화 연결 + 실생성 검증

---

## 1) feature_engineer.py 조치

### 변경 사항
- 파일: `invest/scripts/feature_engineer.py`
- 입력 경로를 raw에서 clean/production으로 전면 교체
  - `invest/data/raw/kr/ohlcv/*.csv` -> `invest/data/clean/production/kr/ohlcv/*.csv`
  - `invest/data/raw/kr/supply/*_supply.csv` -> `invest/data/clean/production/kr/supply/*_supply.csv`
- fail-fast 가드 추가:
  - `_guard_no_raw_path()`에서 경로 문자열에 `/raw/` 포함 시 `assert`로 즉시 실패

### 검증
- `grep -n "raw" invest/scripts/feature_engineer.py` 확인: raw는 가드/정책 설명 문맥에서만 존재
- 스모크 실행: `./.venv/bin/python3 invest/scripts/feature_engineer.py` 정상 동작

---

## 2) clean/quarantine 소급 재분리 배치

### 실행
- 명령: `./.venv/bin/python3 invest/scripts/onepass_refine_full.py`
- 산출 리포트: `reports/qc/FULL_REFINE_REPORT_20260218_010517.md`
- 요청 산출물: `reports/qc/CLEAN_QUARANTINE_BACKFILL_20260218.md`

### 집계
- total: 34,029
- clean: 262
- quarantine: 169
- skipped: 33,766

---

## 3) stage5 manifest 의무화 연결

### 변경 사항
- 파일: `invest/backtest_compare.py` (README상 Stage5 실행 경로)
- `run_manifest.py`의 `write_run_manifest(...)` 호출을 Stage5 완료 경로에 연결
- 결과 CSV/PNG 출력 직후 manifest 생성 및 존재 검증 추가
  - 생성 경로: `invest/reports/data_quality/manifest_backtest_stage5_<timestamp>.json`
  - 생성 실패 시 `RuntimeError`로 즉시 실패

### 실생성 확인
- 실행: `./.venv/bin/python3 invest/backtest_compare.py`
- 생성 확인 파일:
  - `invest/reports/data_quality/manifest_backtest_stage5_20260218_010628.json`

---

## 검증 로그

### py_compile
- 명령:
  - `./.venv/bin/python3 -m py_compile invest/scripts/feature_engineer.py invest/backtest_compare.py invest/scripts/run_manifest.py invest/scripts/onepass_refine_full.py`
- 결과: PASS

### 핵심 스모크
- `feature_engineer.py`: PASS
- `backtest_compare.py` (stage5 경로): PASS
  - 결과물: `invest/results/test/annual_returns_comparison_20260218_010620.csv`
  - 결과물: `invest/results/test/annual_returns_comparison_20260218_010620.png`
  - manifest: `invest/reports/data_quality/manifest_backtest_stage5_20260218_010628.json`

---

## 변경 목록(본 작업 범위)
- `invest/scripts/feature_engineer.py`
- `invest/backtest_compare.py`
- `reports/qc/CLEAN_QUARANTINE_BACKFILL_20260218.md`
- `reports/qc/RED_FIX_EXEC_20260218.md`
- `reports/qc/RED_FIX_EXEC_20260218.json`

---

## 실패/위험 잔여 (<=3)
1. `backtest_compare.py`는 현재 입력 데이터가 여전히 raw 기반(기존 설계). 이번 요청 범위는 manifest 의무화 중심으로 반영됨.
2. 소급 재분리 배치는 incremental 인덱스 기반이라, 과거 동일 시그니처 파일은 skip됨(강제 전체 재처리가 필요하면 인덱스 초기화 후 재실행 필요).
3. 저장소에 동시 진행 중 변경이 다수 존재하여(다른 파일들 modified/untracked), 커밋 분리 시 작업 범위 선별(staging) 주의 필요.
