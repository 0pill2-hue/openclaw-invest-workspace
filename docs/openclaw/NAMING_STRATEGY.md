# NAMING_STRATEGY.md

Last updated: 2026-02-18 06:46 KST
Purpose: 코드/게이트/리포트/매니페스트 네이밍을 일관화하여 재현성·탐색성·운영 안정성을 유지

## 1) 공통 원칙
- 코드 파일: `snake_case` 고정
- 리포트 파일: `STAGE` 대문자 prefix 허용
- 금지 suffix: `final`, `fixed`, `new2`, `tmp2` (의미 불명)
- 동일 목적 파일은 `latest pointer 1개 + timestamp 실행산출` 구조 유지

## 2) 스크립트 네이밍
형식:
- `stage<nn>_<domain>_<action>.py`
- `gate_stage<start>to<end>_check.py`

예시:
- `stage04_value_calculate.py`
- `stage05_baseline_run.py`
- `gate_stage01to04_check.py`

## 3) 리포트 네이밍
형식:
- `STAGE<NN>_<TOPIC>_<RUN|RESULT>_<YYYYMMDD_HHMMSS>.<json|md>`

예시:
- `STAGE05_BASELINE_RESULT_20260218_063854.json`

## 4) 매니페스트 네이밍
형식:
- `manifest_stage<nn>_<topic>_<YYYYMMDD_HHMMSS>.json`

예시:
- `manifest_stage05_baseline_20260218_063854.json`

## 5) 마이그레이션 원칙
- 리네이밍은 게이트 안정화(4/5 통과) 이후 수행
- 리네이밍 시 import/경로 참조 동시 갱신
- 변경 후 즉시 스모크 실행(해당 stage run + gate check) 필수
