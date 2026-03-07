# Stage1 Docs

Stage1 문서는 이 디렉터리의 두 파일만 유지한다.
상세 실행·재현 SSOT는 반드시 `RUNBOOK.md`를 본다.

- 역할: 외부 원천 수집과 raw/master/runtime 기준선 생성
- 범위: Stage2 정제 이전의 데이터 수집과 1차 게이트
- 메인 진입점: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 체인 진입점: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 필수 검증: checkpoint gate, post-collection validate
- 핵심 출력: `outputs/master`, `outputs/raw`, `outputs/runtime`, `outputs/logs`
- Telegram 인증/폴백, DART, RSS, 뉴스, OCR 수집 규칙은 RUNBOOK에 통합했다.

## 데이터 수집 종류
### DB / 시계열 계열
- `signal.kr.ohlcv` — 한국 종목 OHLCV
- `signal.kr.supply` — 한국 종목 수급
- `signal.us.ohlcv` — 미국 종목 OHLCV
- `qualitative.kr.dart` — DART 공시 메타

### 정성 / 텍스트 계열
- `qualitative.market.rss` — RSS 피드 기사 메타
- `qualitative.market.news_url_index` — 뉴스 URL 인덱스
- `qualitative.market.news_selected_articles` — 선별 뉴스 본문
- `qualitative.text.telegram` — 텔레그램 채널 수집
- `qualitative.text.blog` — 블로그 본문 수집
- `qualitative.text.premium` — 프리미엄/유료 채널 수집
- `qualitative.text.image_map` — 이미지-텍스트 매핑 산출
- `qualitative.text.images_ocr` — OCR 텍스트 산출

### 구조 확인
- 수집 종류/범위/상태 SSOT: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- raw 전체 폴더 구조: 같은 파일의 `raw_tree`
- 백필 명령과 운영 재현 명령도 RUNBOOK에만 남긴다.
- Stage1 운영 변경은 기본적으로 RUNBOOK에 반영한다.
- 미해결 운영 이슈는 `TODO.md`에 tracked 상태로 남긴다.
- 공통 전략/단계 개요는 `docs/invest/STRATEGY_MASTER.md`, `docs/invest/STAGES_OVERVIEW.md`를 따른다.

## 바로가기
- [RUNBOOK.md](./RUNBOOK.md)
- [TODO.md](./TODO.md)
- raw coverage catalog: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
