# STRUCTURE_POLICY.md

## 목적
산출물/코드/룰북이 여러 위치로 흩어져 정합성이 깨지는 문제를 방지하기 위한 고정 구조 정책.

## 단일 기준 위치 (Single Source of Truth)

### 1) 전략/규칙
- Canonical Rulebook: `invest/docs/strategy/RULEBOOK_V3.md`
- Legacy 파일은 참조/리다이렉트만 허용, 운영 기준으로 사용 금지.

### 2) 스테이지 산출물
- 루트: `invest/reports/stage_updates/`
- 스테이지별: `invest/reports/stage_updates/stage01/` ... `stage11/`
- 공통: `invest/reports/stage_updates/common/`
- 로그: `invest/reports/stage_updates/logs/`
- 차트: `invest/reports/stage_updates/charts/` (필요시 `stageXX/charts/`)

### 3) 결과 데이터
- test: `invest/results/test/`
- validated: `invest/results/validated/`
- prod: `invest/results/prod/`

### 4) 실행 스크립트
- 단계 스크립트는 `invest/scripts/stageXX_*.py` 네이밍으로 고정.

## 강제 규칙
1. 새 보고서/산출물은 반드시 해당 stage 폴더에 저장.
2. 코드/문서 경로는 stage 폴더 기준으로만 참조.
3. `invest/reports/stage_updates/stage05_*.md` 같은 루트 직파일 출력 금지.
4. Stage05는 12-baseline(3/3/3/3) 가드 통과 전 결과 무효.

## 마이그레이션 체크
- [ ] 구경로 참조 grep 0건
- [ ] 깨진 경로/링크 0건
- [ ] Rulebook 단일 기준 참조만 남김
- [ ] Stage 실행 스크립트 출력 경로 stageXX로 고정
