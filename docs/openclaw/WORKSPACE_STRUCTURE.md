# WORKSPACE_STRUCTURE.md

Last updated: 2026-02-19 15:15 KST
Purpose: invest 안/밖 포함 워크스페이스 구조와 canonical 문서 위치 기준

## Top-level canonical
- `docs/openclaw/` : OpenClaw 시스템/구조/컨텍스트 재로딩 기준 문서
- `invest/` : 알고리즘/데이터/전략/스크립트 본체
- `invest/reports/` : 투자 단계/검증 리포트
- `reports/` : 운영 정기 보고(hourly/daily/weekly/monthly)
- `memory/` : 일자 메모리 + 상태파일 (`memory/README.md` 기준)
- `MEMORY.md` : 장기 메모리
- `DIRECTIVES.md` : 지시사항 추적
- `TASKS.md` : 보고/작업 큐

## Top-level operational (존재 확인됨)
- `.venv/` : 루트 Python 가상환경
- `.openclaw_tmp/` : 임시 작업 디렉터리
- `scripts/` : 외부 호출/운영 호환 wrapper (실체는 invest/scripts)
- `automation/` : 운영 자동화 보조

## invest 내부 canonical
- `invest/docs/strategy/` : 전략 고정 문서(RULEBOOK/PIPELINE/STAGE_STRATEGY)
- `invest/scripts/` : 전략/수집/정제/검증/산출 실행 스크립트
- `invest/data/` : raw/clean/quarantine 데이터 계층
- `invest/reports/data_quality/` : manifest/품질 리포트
- `invest/results/` : 결과물(test/validated/prod 분리)

## stage 문서 canonical
- `invest/reports/stage_updates/stage01/stage01_data_collection.md`
- `invest/reports/stage_updates/stage02/stage02_data_cleaning.md`
- `invest/reports/stage_updates/stage03/stage03_cleaning_validation.md`
- `invest/reports/stage_updates/stage04/stage04_validated_value.md`
- `invest/reports/stage_updates/stage05/stage05_baselines_v3_4_kr.md`
- `invest/reports/stage_updates/stage06/stage06_candidates_v3_4_kr.md`
- `invest/reports/stage_updates/stage07/stage07_cutoff_v3_4_kr.md`
- `invest/reports/stage_updates/stage08/stage08_value_v3_4_kr.md`
- `invest/reports/stage_updates/stage09/stage09_cross_review_v3_4_kr.md`
- `invest/reports/stage_updates/stage11/stage11_adopt_hold_promote.md`
- 단계 인덱스: `invest/reports/stage_updates/README.md`

## 문서 우선순위
1. `invest/docs/strategy/RULEBOOK_MASTER.md`
2. `invest/reports/stage_updates/*.md`
3. 실행 스크립트/보조 문서
