# INVEST_STRUCTURE_POLICY.md

Last updated: 2026-03-07 19:00 KST  
Purpose: 투자 산출물/코드/룰북 경로 정합성 고정 정책

## 단일 기준 위치 (Single Source of Truth)

### 1) 전략/규칙

- Canonical Rulebook: `docs/invest/RULEBOOK_MASTER.md`
- Legacy 파일은 참조/리다이렉트만 허용, 운영 기준 사용 금지.

### 2) Stage 문서 템플릿

- `README.md`: 사람용 진입 인덱스/개요만 유지
- `STAGE{번호}_RULEBOOK_AND_REPRO.md`: stage 계약의 canonical entry
- `RUNBOOK.md`: 운영 복잡도가 높은 stage에서만 두는 operations SSOT 보조문서
- source map/appendix 문서: collector/output 카탈로그용 reference only
- `TODO.md`: 미해결 이슈 추적용 backlog only
- 동일 규칙을 여러 문서에 분산 복제하지 말고, 역할별 owner 문서 1곳만 갱신한다.
- Stage1은 위 템플릿을 확정 적용한다:
  - index: `docs/invest/stage1/README.md`
  - operations SSOT: `docs/invest/stage1/RUNBOOK.md`
  - stage contract entry: `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
  - source appendix: `docs/invest/stage1/stage01_data_collection.md`
  - backlog: `docs/invest/stage1/TODO.md`

### 3) 스테이지 산출물

- 루트(공유): `invest/stages/stage1/outputs/reports/stage_updates/`
- 스테이지별 Rule/Repro(운영 표준): `docs/invest/stage{번호}/` (historical `stage_updates`는 reference로만 유지)
- 스테이지별 실행 리포트/업데이트: `invest/stages/stage{1..11}/outputs/reports/stage_updates/`
- 버전 산출물: `invest/stages/stage6/outputs/reports/stage_updates/v*/`
- 로그(공유): `invest/stages/stage1/outputs/logs/`
- 차트: `invest/stages/stage6/outputs/reports/stage_updates/v*/charts/`

### 4) 결과 데이터

- test: `invest/stages/stage6/outputs/results/test_history/`
- validated: `invest/stages/stage6/outputs/results/validated_history/`
- prod: `invest/stages/stage6/outputs/results/prod_history/`

### 5) 실행 스크립트

- 단계 스크립트: `invest/stages/stage{1..5}/scripts/*.py`
- Stage3 스크립트: `invest/stages/stage3/scripts/*.py`
- 레거시/미사용 스크립트: stage별 scripts 내부 비운영 파일은 삭제 또는 주석 처리

## 강제 규칙

1. 새 보고서/산출물은 반드시 해당 stage/version 폴더에 저장.
2. 코드/문서 경로는 stage/version canonical 경로만 참조.
3. `invest/stages/stage6/outputs/reports/stage_updates_*.md` 같은 루트 직파일 출력 금지.
4. Stage06는 baseline cardinality 가드 통과 전 결과 무효.
5. Stage 문서 신규 추가 전, 기존 템플릿 역할(`README`/`RULEBOOK_AND_REPRO`/`RUNBOOK`/appendix/`TODO`)로 흡수 가능한지 먼저 확인.

## 마이그레이션 체크

- [ ] 구경로 참조 grep 0건
- [ ] 깨진 경로/링크 0건
- [ ] Rulebook 단일 기준 참조만 남김
- [ ] Stage 실행 스크립트 출력 경로 stage/version 고정
