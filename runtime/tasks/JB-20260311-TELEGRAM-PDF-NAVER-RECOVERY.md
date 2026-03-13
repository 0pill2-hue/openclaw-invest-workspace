# JB-20260311-TELEGRAM-PDF-NAVER-RECOVERY

- requested_at: 2026-03-11 09:05 KST
- updated_at: 2026-03-11 09:45 KST
- status: DONE
- owner: subagent

## what
### 1) telegram PDF 병목 계측
- `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram` 전체 meta를 **unique `(channel_slug,message_id)` 기준 dedup** 해서 재계수했다.
- 결과
  - supported unique: `63,737`
  - pdf unique: `63,735`
  - pdf original 존재: `608`
  - pdf original 누락: `63,127`
  - pdf extract 존재: `20,931`
  - pdf extract 누락: `42,804`
- 집중 병목 채널
  - `선진짱_주식공부방_1378197756` 한 채널에만 missing pdf `63,042`건 집중.
- 해석
  - 병목은 parser/분해 엔진이 아니라 **원본 PDF(original) 부재**다.
  - 이미 extract 텍스트는 `20,931`건 있으나, canonical original이 있는 건 `608`건뿐이라 “유효 저장/분해”가 600건대에 묶여 있다.

### 2) telegram original redownload 복구 경로 보강
- 수정 파일: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- 반영 내용
  - missing_original dedup 후보를 모아 **Telethon 기반 원본 재다운로드 경로** 추가.
  - cron/system python에서 `telethon`이 없으면 **workspace venv(`.venv/bin/python3`)로 자동 re-exec** 하도록 추가.
  - env 로더가 `invest/stages/stage1/.env`뿐 아니라 `~/.config/invest/invest_autocollect.env`도 읽도록 보강.
  - recovery stats(`telegram_recovery_*`)를 status/pipeline event에 남기도록 확장.

### 3) 네이버 대체 뉴스 소스 경로 구현
- 신규 파일: `invest/stages/stage1/scripts/stage01_fetch_naver_finance_news_index.py`
- 반영 내용
  - `finance.naver.com/news/news_list.naver` 섹션/페이지를 긁어 Stage1 `url_index/*.jsonl` 스키마로 저장.
  - finance.naver.com article 링크를 그대로 쓰지 않고, 실제 본문이 열리는 **`https://n.news.naver.com/mnews/article/{office_id}/{article_id}`** 로 정규화.
  - 따라서 기존 `selected_articles`를 **수정 없이 재사용** 가능하게 함.

## why
- 주인님 지시의 핵심은 두 가지였다.
  1. `selected_articles` 확장은 보류하고, 더 확장성 있는 뉴스 소스로 실제 source switch 경로 확보.
  2. telegram PDF 수천건 대비 600건대에 묶인 병목을 찾아 개선하고, 가능 범위에서 실제 회복 증빙.
- 계측 결과, telegram 쪽은 `missing_original`이 절대 병목이라 parser 추가보다 **원본 재복구 경로**가 우선이었다.
- 뉴스 쪽은 기존 `selected_articles` 자체를 더 뜯기보다, **Naver list -> url_index -> selected_articles**로 붙이는 것이 가장 짧고 실제적인 전환 경로였다.

## result
### A. telegram PDF 병목 판정
- 최종 판정: **single-writer/큐/락보다 upstream original 부재가 1순위 병목**.
- 보조 status 기준
  - `telegram_attachment_extract_backfill_status.json` 최신 실행에서 `reason_counts.missing_original = 67,191`
  - dedup 기준으로는 실제 pdf original gap이 `63,127`
- 실패 사유 top
  - `missing_original`: `42,802` (dedup pdf extraction reason 기준)
  - `file_too_large:pdf`: `2`

### B. telegram 복구 실행/증빙
- 실제 시도 1: system python으로 backfill recovery 실행
  - 결과: `telethon` 부재로 recovery skip
  - 조치: venv auto re-exec 코드 추가
- 실제 시도 2: venv python으로 targeted recovery probe 실행
  - 결과: `TELEGRAM_API_ID/HASH` 비어 있어 live recovery skip
  - 확인된 env gate
    - checked path: `~/.config/invest/invest_autocollect.env`
    - `TELEGRAM_API_ID`: empty
    - `TELEGRAM_API_HASH`: empty
- 실제 회복 delta
  - `pdf original 존재`: `608 -> 608` (delta `0`)
  - `pdf extract 존재`: `20,931 -> 20,931` (delta `0`)
- 결론
  - **코드상 recovery 경로는 열었지만**, 현재 세션/자동수집 env에 실 credential이 없어 live redownload는 아직 실행되지 못했다.
  - 따라서 이번 턴의 실제 회복 증가는 `0`이다.

### C. 네이버 source switch 실증
- 실행
  - `python3 invest/stages/stage1/scripts/stage01_fetch_naver_finance_news_index.py --sections 258,262 --pages 2`
  - 산출: `url_index_naver_finance_20260311-004214.jsonl`
  - 확보 row: `8`
- 이어서 검증
  - `python3 invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py --input-index ...url_index_naver_finance_20260311-004214.jsonl --max-candidates 5 --max-attempts 5 --min-selected 1 --timeout 15`
  - 결과: `selected_count=5`, `failed_count=0`, `status=PASS`
- 결론
  - **selected_articles 확장 없이도**
    - `Naver Finance list`
    - `-> n.news.naver.com article URL`
    - `-> existing selected_articles`
    경로로 source switch가 실제 작동한다.
  - 우선 추천 소스는 **Naver Finance 실시간 뉴스 list**다.

## proof
- telegram 병목/복구
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
  - `invest/stages/stage1/outputs/runtime/telegram_pdf_recovery_probe_20260311.json`
- naver source switch
  - `invest/stages/stage1/scripts/stage01_fetch_naver_finance_news_index.py`
  - `invest/stages/stage1/outputs/runtime/news_naver_finance_index_status.json`
  - `invest/stages/stage1/outputs/runtime/naver_finance_source_switch_probe_20260311.json`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/url_index/url_index_naver_finance_20260311-004214.jsonl`
  - `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260311-004216.jsonl`

## next
1. **telegram 1차 액션**
   - launchd/운영환경에 실제 `TELEGRAM_API_ID/HASH`를 다시 주입한 뒤,
   - `TELEGRAM_ATTACH_RECOVER_MISSING_ORIGINALS=1 TELEGRAM_ATTACH_RECOVER_LIMIT=100 python3 invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
   - 로 100건 bounded redownload를 먼저 돌려 delta를 확인.
2. **source switch 1차 액션**
   - daily/news profile에 `stage01_fetch_naver_finance_news_index.py`를 url_index build 직전 또는 직후에 연결.
   - 초기 운영은 `sections=258,262`, `pages=3` 정도로 시작하는 것이 안전.
3. **확장 우선순위**
   - telegram은 먼저 credential gate 해소 후 회복 batch.
   - 뉴스는 Naver Finance가 안정화되면 `258~262` 전체 섹션으로 확장.

## memory draft
- 2026-03-11: telegram PDF 병목은 parser가 아니라 `missing_original`(dedup pdf 63,735 중 original 존재 608, missing 63,127)로 확인했고, recovery code/venv/env-loader를 붙였지만 현재 TELEGRAM_API_ID/HASH 공백으로 live delta는 0; 대신 Naver Finance list -> n.news.naver.com -> selected_articles 경로를 구현해 8 URL index / 5 selected article 실증 완료.
