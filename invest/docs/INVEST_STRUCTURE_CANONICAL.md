# INVEST_STRUCTURE_CANONICAL.md

Last updated: 2026-02-19 15:07 KST
Purpose: 투자 관련 파일의 단일 경로 기준(정합성 기준)

## 원칙
- 투자 관련 파일은 **모두 `invest/` 하위**에 둔다.
- `docs/openclaw/`는 OpenClaw 시스템 운영 문서만 둔다.
- 투자 리포트를 루트 `reports/`에 두지 않는다.

## Canonical Paths (투자)
- 전략 문서: `invest/docs/strategy/`
- 투자 일반 문서: `invest/docs/`
- 실행 스크립트: `invest/scripts/`
- 데이터 품질/스테이지 리포트: `invest/reports/`
- 정기 보고: `invest/reports/regular/{hourly,daily,weekly}/`
- 결과물: `invest/results/{test,validated,prod}/`
- 데이터: `invest/data/`

## 금지 경로 (투자 용도)
- `docs/invest/`
- `reports/invest/`
- `reports/daily|hourly|weekly/`

## 점검 규칙
1. 투자 문서/리포트/스크립트 추가 시 경로가 `invest/` 하위인지 먼저 확인
2. PR/커밋 전 아래 문자열이 남아있는지 검색
   - `docs/invest/`
   - `reports/invest/`
   - `reports/daily/`, `reports/hourly/`, `reports/weekly/`
3. 발견 시 즉시 canonical 경로로 수정 후 커밋
