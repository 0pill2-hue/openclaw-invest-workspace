# Stage1 Docs

Stage1 문서 정책/템플릿은 아래 5개 역할로 고정한다.
기존의 "두 파일만 유지" 표현은 폐기한다.

## 문서 역할 고정 템플릿
| 파일 | 상태 | 역할 | 업데이트 규칙 |
| --- | --- | --- | --- |
| `README.md` | canonical index | Stage1 개요/빠른 진입/문서 역할 안내 | 요약/링크만 유지, 상세 규칙 중복 금지 |
| `RUNBOOK.md` | canonical operations SSOT | 실행 명령, 환경변수, fallback, coverage 보고, 운영 절차 | 운영 동작이 바뀌면 먼저 여기 반영 |
| `STAGE1_RULEBOOK_AND_REPRO.md` | canonical stage contract | cross-stage 인덱스가 참조하는 Stage1 규칙/입출력/재현 요약 | stage 범위/입출력/검증 계약이 바뀌면 여기 반영 |
| `stage01_data_collection.md` | reference appendix | collector ↔ output path/source map 보조 카탈로그 | 수집기/산출 경로 매핑 변경 시 반영 |
| `TODO.md` | tracked backlog | 미해결 운영 이슈와 후속 점검 목록 | 해결 전/후 상태만 추적, 실행 SSOT 금지 |

## 문서 충돌 해소 규칙
- 실행 명령/환경변수/폴백/coverage 보고 기준 충돌 시 `RUNBOOK.md`를 우선한다.
- Stage 전체 계약(범위/입력/출력/검증) 요약은 `STAGE1_RULEBOOK_AND_REPRO.md`를 기준으로 본다.
- collector별 세부 입출력 매핑은 `stage01_data_collection.md`를 본다.
- 미해결 이슈/추가 점검은 `TODO.md`에만 남긴다.
- 새 Stage1 문서는 원칙적으로 추가하지 않고, 위 5개 역할 안에 흡수한다.

## Stage1 요약
- 역할: 외부 원천 수집과 raw/master/runtime 기준선 생성
- 범위: Stage2 정제 이전의 데이터 수집과 1차 게이트
- 메인 진입점: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 체인 진입점: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 필수 검증: checkpoint gate, post-collection validate
- 핵심 출력: `outputs/master`, `outputs/raw`, `outputs/runtime`, `outputs/logs`
- Telegram 인증/폴백, DART, RSS, 뉴스, OCR 수집 규칙은 `RUNBOOK.md`에 통합한다.

## 데이터 수집 종류
### DB / 시계열 계열
- `signal.kr.ohlcv` — 한국 종목 OHLCV
- `signal.kr.supply` — 한국 종목 수급
- `signal.us.ohlcv` — 미국 종목 OHLCV
- `signal.market.macro` — 매크로 시계열(FRED/글로벌 매크로)
- `qualitative.kr.dart` — DART 공시 메타

### 정성 / 텍스트 계열
- `qualitative.market.rss` — RSS 피드 기사 메타
- `qualitative.market.news_url_index` — 뉴스 URL 인덱스
- `qualitative.market.news_selected_articles` — 선별 뉴스 본문
- `qualitative.text.telegram` — 텔레그램 채널 수집
- `qualitative.text.blog` — 블로그 본문 수집 (기본 coverage 창: 최근 10년)
- `qualitative.text.premium` — 프리미엄/유료 채널 수집
- `qualitative.text.image_map` — 이미지-텍스트 매핑 산출
- `qualitative.text.images_ocr` — OCR 텍스트 산출

## 구조 확인
- 수집 종류/범위/상태 SSOT: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- raw 전체 폴더 구조: 같은 파일의 `raw_tree`
- 운영 재현/실행 명령은 `RUNBOOK.md` 기준으로만 유지한다.
- Stage1 운영 변경은 기본적으로 `RUNBOOK.md`에 반영한다.
- 공통 전략/단계 개요는 `docs/invest/STRATEGY_MASTER.md`, `docs/invest/STAGES_OVERVIEW.md`를 따른다.

## 바로가기
- [RUNBOOK.md](./RUNBOOK.md)
- [STAGE1_RULEBOOK_AND_REPRO.md](./STAGE1_RULEBOOK_AND_REPRO.md)
- [stage01_data_collection.md](./stage01_data_collection.md)
- [TODO.md](./TODO.md)
- raw coverage catalog: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
