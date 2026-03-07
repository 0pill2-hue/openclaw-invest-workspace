# INVEST_STRUCTURE_POLICY.md

Last updated: 2026-03-05 08:18 KST  
Purpose: 투자 산출물/코드/룰북 경로 정합성 고정 정책

## 단일 기준 위치 (Single Source of Truth)

### 1) 전략/규칙

- Canonical Rulebook: `docs/invest/RULEBOOK_MASTER.md`
- Legacy 파일은 참조/리다이렉트만 허용, 운영 기준 사용 금지.

### 2) 스테이지 산출물

- 루트(공유): `invest/stages/stage1/outputs/reports/stage_updates/`
- 스테이지별 Rule/Repro(운영 표준): `invest/stages/stage{1..11}/docs/` (stage_updates 사용 금지)
- 스테이지별 실행 리포트/업데이트: `invest/stages/stage{1..11}/outputs/reports/stage_updates/`
- 버전 산출물: `invest/stages/stage6/outputs/reports/stage_updates/v*/`
- 로그(공유): `invest/stages/stage1/outputs/logs/`
- 차트: `invest/stages/stage6/outputs/reports/stage_updates/v*/charts/`

### 3) 결과 데이터

- test: `invest/stages/stage6/outputs/results/test_history/`
- validated: `invest/stages/stage6/outputs/results/validated_history/`
- prod: `invest/stages/stage6/outputs/results/prod_history/`

### 4) 실행 스크립트

- 단계 스크립트: `invest/stages/stage{1..5}/scripts/*.py`
- Stage3 스크립트: `invest/stages/stage3/scripts/*.py`
- 레거시/미사용 스크립트: stage별 scripts 내부 비운영 파일은 삭제 또는 주석 처리

## 강제 규칙

1. 새 보고서/산출물은 반드시 해당 stage/version 폴더에 저장.
2. 코드/문서 경로는 stage/version canonical 경로만 참조.
3. `invest/stages/stage6/outputs/reports/stage_updates_*.md` 같은 루트 직파일 출력 금지.
4. Stage06는 baseline cardinality 가드 통과 전 결과 무효.

## 마이그레이션 체크

- [ ] 구경로 참조 grep 0건
- [ ] 깨진 경로/링크 0건
- [ ] Rulebook 단일 기준 참조만 남김
- [ ] Stage 실행 스크립트 출력 경로 stage/version 고정
