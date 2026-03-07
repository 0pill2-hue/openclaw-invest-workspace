# STAGE1_RULEBOOK_AND_REPRO

## 목적
- Stage1은 외부 원천에서 데이터를 **수집(ingestion/acquisition)** 하고 raw/master/runtime 기준선을 만든다.
- Stage2가 정제/검역을 수행할 수 있도록 원천에 가까운 산출물을 재현 가능하게 남긴다.

## 책임 범위
- 외부 소스에서 데이터 가져오기
- 최소한의 형식 정규화
  - 컬럼명 통일
  - 날짜 파싱
  - 저장 포맷 정리
- 수집 시점 메타데이터 기록
- 수집 성공/실패 상태 기록
- 기술적 오류 감지
  - 응답 실패
  - 파싱 실패
  - 필수 컬럼 부재

## 비책임 범위
- 공격적 값 정제
- 이상치 제거의 최종 판정
- 비즈니스 규칙 기반 삭제
- clean 데이터셋 확정
- quarantine 최종 판정

## 실제 디렉토리 구조
- docs: `invest/stages/stage1/docs/`
- inputs: `invest/stages/stage1/inputs/`
- outputs: `invest/stages/stage1/outputs/`
- scripts: `invest/stages/stage1/scripts/`

실제 출력 하위 구조:
- master: `invest/stages/stage1/outputs/master/`
- raw: `invest/stages/stage1/outputs/raw/`
- runtime: `invest/stages/stage1/outputs/runtime/`
- reports: `invest/stages/stage1/outputs/reports/`
- logs: `invest/stages/stage1/outputs/logs/`

## 입력물
### 설정 / 시드
- `invest/stages/stage1/inputs/config/news_sources.json`
- `invest/stages/stage1/inputs/config/telegram_channel_allowlist.txt`
- `invest/stages/stage1/inputs/config/dart_api_key.txt`

### 외부 원천
- FinanceDataReader
- pykrx
- yfinance
- FRED
- RSS feeds
- DART API
- Telegram
- 웹/블로그/프리미엄 채널

## 출력물
### master
- `invest/stages/stage1/outputs/master/kr_stock_list.csv`

### raw
- `invest/stages/stage1/outputs/raw/signal/kr/ohlcv/*.csv`
- `invest/stages/stage1/outputs/raw/signal/kr/supply/*_supply.csv`
- `invest/stages/stage1/outputs/raw/signal/us/ohlcv/*.csv`
- `invest/stages/stage1/outputs/raw/signal/market/macro/*.csv`
- `invest/stages/stage1/outputs/raw/qualitative/kr/dart/*.csv`
- `invest/stages/stage1/outputs/raw/qualitative/market/rss/*.json`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/*.jsonl`
- `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/*.jsonl`
- `invest/stages/stage1/outputs/raw/qualitative/text/telegram/**/*.md`
- `invest/stages/stage1/outputs/raw/qualitative/text/blog/**/*.md`
- `invest/stages/stage1/outputs/raw/qualitative/text/premium/**/*.md`
- `invest/stages/stage1/outputs/raw/qualitative/text/image_map/*`
- `invest/stages/stage1/outputs/raw/qualitative/text/images_ocr/*`

### runtime / checkpoints / reports
- `invest/stages/stage1/outputs/runtime/daily_update_status.json`
- `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
- `invest/stages/stage1/outputs/runtime/telegram_collector_status.json`
- `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
- anomaly/reject reports under `invest/stages/stage1/outputs/reports/data_quality/`

### tracked canonical output exceptions
- `invest/stages/stage1/outputs/raw/source_coverage_index.json`
- `invest/stages/stage1/outputs/raw/qualitative/kr/dart/coverage_summary.json`

## 스크립트 목록
### 메인 진입점
- `invest/stages/stage1/scripts/stage01_daily_update.py`
- `invest/stages/stage1/scripts/stage01_checkpoint_gate.py`
- `invest/stages/stage1/scripts/stage01_post_collection_validate.py`

### 핵심 수집기
- `stage01_fetch_stock_list.py`
- `stage01_fetch_ohlcv.py`
- `stage01_fetch_supply.py`
- `stage01_fetch_us_ohlcv.py`
- `stage01_fetch_macro_fred.py`
- `stage01_fetch_global_macro.py`
- `stage01_fetch_dart_disclosures.py`
- `stage01_fetch_news_rss.py`
- `stage01_build_news_url_index.py`
- `stage01_collect_selected_news_articles.py`
- `stage01_scrape_all_posts_v2.py`
- `stage01_scrape_telegram_launchd.py`
- `stage01_image_harvester.py`
- `stage01_collect_premium_startale_channel_auth.py`
- `stage01_update_coverage_manifest.py`

### 보조 / full fetch / repair
- `stage01_full_fetch_ohlcv.py`
- `stage01_full_fetch_supply.py`
- `stage01_full_fetch_us_ohlcv.py`
- `stage01_full_fetch_dart_disclosures.py`
- `stage01_backfill_10y.py`
- `stage01_backfill_10y_coverage_audit.py`
- `stage01_supply_autorepair.py`
- `stage01_rss_date_repair.py`
- `stage01_telegram_undated_repair.py`
- `stage01_path_and_date_judgment_fix.py`

## 표준 실행 순서
1. `stage01_fetch_stock_list.py`
2. KR/US/매크로/DART/RSS/뉴스/블로그/텔레그램/프리미엄 수집기 실행
3. `stage01_update_coverage_manifest.py`
4. `stage01_checkpoint_gate.py`
5. `stage01_post_collection_validate.py`

일일 통합 진입점은 `stage01_daily_update.py`다.

## 일일 실행 규칙
- `stage01_daily_update.py`는 하위 수집 스크립트의 성공/실패를 모두 기록한다.
- 상태 JSON은 항상 남긴다.
- 하위 작업 하나라도 실패하면 마지막에 non-zero exit로 끝난다.
- fallback이 사용된 경우 상태 JSON과 로그에 남긴다.
- 성공처럼 보이지만 exit code가 0인 거짓 양성 상태를 만들지 않는다.

## 재실행 규칙
증분 저장 기본 절차:
1. 기존 데이터 로드
2. 신규 데이터 수집
3. concat/merge
4. dedup
5. 날짜 정렬
6. temp 파일 저장
7. atomic replace

원칙:
- append-only 저장으로 중복을 키우지 않는다.
- 경계 날짜 재실행 시에도 중복 누적을 막는다.
- 기존 파일 파싱 실패 시 조용히 덮어쓰지 말고 실패로 처리한다.

## Raw 저장 원칙
- raw는 가능한 한 원천 보존 성격을 유지한다.
- Stage1에서 행을 조용히 버리지 않는다.
- 이상치/의심값은 가능하면 raw 유지 + anomaly/report 분리로 처리한다.
- 삭제가 불가피하면 무엇이 왜 빠졌는지 재현 가능한 report를 남긴다.
- 최종 정제/삭제 판단은 Stage2 책임이다.

## 실패 기준
- 외부 응답 실패
- 파싱 실패
- 필수 컬럼 부재
- 기존 raw 파일 파싱 실패
- checkpoint gate 실패
- post-collection validate 실패
- 하위 fetch job 하나라도 non-zero 종료

## 검증 방법
1. `invest/stages/stage1/outputs/runtime/daily_update_status.json`
2. `invest/stages/stage1/outputs/reports/data_quality/stage01_checkpoint_status.json`
3. `invest/stages/stage1/outputs/runtime/post_collection_validate.json`
4. `invest/stages/stage1/outputs/raw/source_coverage_index.json`

검증 시 확인 항목:
- `failed_count`
- 실패 source / error summary
- raw coverage earliest/latest
- `needs_incremental_update`
- known stale source 여부

## 다음 stage로 넘기는 조건
- checkpoint gate 통과
- post-collection validate 통과
- 필요한 source가 raw/master/runtime 기준선에 정상 기록됨
- Stage2가 입력을 읽을 수 있는 경로가 존재함

## 변경 이력
- 2026-03-07: Stage1 canonical RULEBOOK 신설, Stage1 책임/outputs/fail-close/증분 저장 정책 명문화
