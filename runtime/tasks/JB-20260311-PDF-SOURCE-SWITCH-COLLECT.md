# JB-20260311-PDF-SOURCE-SWITCH-COLLECT

- requested_at: 2026-03-11 08:52 KST
- status: DONE_SUBAGENT
- owner: subagent

## what
- source-switch 경로를 확인했다.
  - from: `qualitative/attachments/telegram` 원본 첨부 PDF 중심
  - to: `qualitative/text/{telegram,blog,premium}` 내 URL 기반 원문/링크 PDF sidecar 수집 (`invest/stages/stage1/scripts/stage01_collect_link_sidecars.py`)
- 기존 full run status를 확인했다.
- status 생성 이후 변경된 `text/telegram` 파일 17개(신규/갱신 13 + sidecar 누락 4)만 안전하게 증분 재처리했다.
- adjacent source로 `stage01_collect_selected_news_articles.py` / `news_selected_articles_status.json` 도 확인해, 다음 확장 후보가 맞는지 점검했다.

## why
- Telegram attachment original PDF 쪽은 ceiling이 낮아 추가 수집량 증대가 제한적이다.
- 반면 link sidecar 수집기는 `text/blog`, `text/telegram`, `text/premium/startale` 의 URL을 canonicalize 후 본문/링크 PDF를 직접 fetch한다.
- 전체 4만+ 파일 재실행 대신, status 이후 변경분 17개만 재처리하는 방식이 가장 안전하고 빠른 incremental rerun 이었다.

## result
### 1) source-switch 경로 확인
- `stage01_collect_link_sidecars.py` 는 실제로 다음 폴더를 target 으로 사용한다.
  - `text/blog`
  - `text/telegram`
  - `text/premium/startale`
- 본문이 짧거나 비어 있을 때만 URL fetch 를 시도하고, 링크가 PDF면 PDF text extraction 도 수행한다.

### 2) 기존 full run 실증 수치
기존 full status (`invest/stages/stage1/outputs/runtime/link_enrich_sidecar_status.json`) 기준:
- files_seen: 41,984
- sidecars_written: 41,980
- body_enrichment_needed_files: 1,503
- blocks_written_files: 904
- total_blocks: 909
- canonical_urls_total: 291,843
- fetch_attempted_urls: 2,507
- fetch_successful_urls: 909
- fetched_text_too_short_urls: 1,465
- pdf_urls: 1
- folder별 blocks_written_files
  - `text/blog`: 633
  - `text/telegram`: 0
  - `text/premium/startale`: 271

판정:
- attachment-only 축 대비, 링크 원문/링크 PDF 축으로의 전환 자체는 **실제로 추가 수집을 늘렸다**. 적어도 sidecar block 기준 `904 files / 909 blocks` 가 이미 확보되어 있다.
- 다만 그 증가분은 현재까지는 `blog + premium` 에 집중되어 있고, `telegram` 쪽은 canonical URL 기록은 많지만 block 추가는 아직 없었다.

### 3) 이번 incremental rerun (telegram 변경분 17개)
증분 실행 proof: `invest/stages/stage1/outputs/runtime/link_enrich_sidecar_incremental_telegram_20260311T0900KST.json`

대상 판정:
- `text/telegram` 총 파일: 73
- status 이후 newer 파일: 13
- missing sidecar 파일: 4
- 처리 대상 합계: 17

증분 처리 결과:
- processed_files: 17
- blocks_written_files: 0
- after_blocks_total: 0
- delta_blocks_vs_before_known: 0
- canonical_only_files: 13
- no_canonical_urls_files: 4
- after_canonical_urls_total: 16,845
- fetch_attempted_urls_total: 0
- fetch_successful_urls_total: 0
- pdf_urls_total: 0
- body_enrichment_needed_files: 0
- body_validation_ok=false 파일: 0

해석:
- 이번에 새로 들어온 telegram public fallback 텍스트들은 URL 수는 매우 많았지만, 이미 본문 길이가 충분해서 `body_enrichment_needed=false` 였다.
- 따라서 링크 fetch 자체가 발생하지 않았고, 이번 증분 rerun 으로는 **telegram 구간 추가 blocks 증가가 없었다**.
- sidecar 누락 4건은 재처리 결과 모두 `no_canonical_urls` 로 정리되었다.

### 4) 링크 PDF 실증
현재 full status 기준 링크 PDF 실제 적중은 1건 확인했다.
- source: `qualitative/text/blog/syprus/222850414064.md`
- sidecar: `invest/stages/stage1/outputs/raw/qualitative/link_enrichment/text/blog/syprus/222850414064.md.json`
- canonical URL 예시:
  - `https://tapiocathai.org/Graph/starch%20export%20price.pdf`
- 해당 sidecar 는 `pdf_urls=1`, `blocks=1`

즉, 링크 PDF 경로는 코드상 가설이 아니라 **실제 hit 이 이미 1건 증빙**되어 있다.

### 5) adjacent source 점검 (`selected_articles`)
`invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py` 와
`invest/stages/stage1/outputs/runtime/news_selected_articles_status.json` 확인 결과:
- status: `PASS`
- output_file: `invest/stages/stage1/outputs/raw/qualitative/market/news/selected_articles/selected_articles_20260310-235350.jsonl`
- index_file_count: 56
- url_index_count: 1,760,186
- existing_url_count: 9,574
- candidate_count: 5,000
- selected_count: 33
- failed_count: 4,967
- failure_samples 30개 중 `unsupported_content_type:application/pdf` 샘플: 21개

해석:
- adjacent source 는 이미 돌아가고 있고 별도 market/news 축이다.
- 여기서는 PDF URL이 꽤 보이지만 collector 가 `application/pdf` 를 지원하지 않아 탈락한 흔적이 뚜렷하다.
- 따라서 **추가 수집량을 더 늘릴 다음 확장 후보**로는 타당하다.

## proof
- 수집 스위치 스크립트: `invest/stages/stage1/scripts/stage01_collect_link_sidecars.py`
- full run status: `invest/stages/stage1/outputs/runtime/link_enrich_sidecar_status.json`
- 증분 rerun proof: `invest/stages/stage1/outputs/runtime/link_enrich_sidecar_incremental_telegram_20260311T0900KST.json`
- link sidecar root: `invest/stages/stage1/outputs/raw/qualitative/link_enrichment/`
- telegram fallback coverage/start 증빙: `invest/stages/stage1/outputs/runtime/telegram_public_fallback_status.json`
  - saved_files: 22
  - saved_msgs: 60,637
  - target_date: `2016-03-12`
  - max_msgs_per_channel: 5,000
- adjacent source status: `invest/stages/stage1/outputs/runtime/news_selected_articles_status.json`
- selected_articles collector: `invest/stages/stage1/scripts/stage01_collect_selected_news_articles.py`

추가 세부 증빙:
- 증분 처리에서 canonical URL 상위 파일 예시
  - `kyaooo_public_fallback.md`: 3,101 URLs
  - `prroeresearch_public_fallback.md`: 2,967 URLs
  - `orangeboard_public_fallback.md`: 2,548 URLs
  - `jake8lee_public_fallback.md`: 2,513 URLs
  - `kimcharger_public_fallback.md`: 2,206 URLs
- no_canonical_urls 정리된 4파일
  - `서현윤미stock_rockrockstock_full.md`
  - `스타테일_리서치_방송전용_채널_statalebangsong_full.md`
  - `승도리의_뉴스클리핑_2024년_4분기_10_11-1_10_2390268997_full.md`
  - `승도리의_뉴스클리핑_2025년_2분기_04_11-7_10_2615735039_full.md`

## next
- 1순위 다음 액션:
  - `stage01_collect_selected_news_articles.py` 쪽에도 `application/pdf` 허용 + PDF text extraction 을 붙여, 현재 `unsupported_content_type:application/pdf` 로 버려지는 adjacent source PDF를 회수 가능한지 검증.
- 이번 턴 결론:
  - from `telegram attachment original PDF` -> to `text/{telegram,blog,premium} link original/PDF sidecars` 전환은 유효했다.
  - 다만 최신 telegram 증분 17개에서는 추가 blocks 증가가 없었고, 당장 더 늘릴 여지는 selected_articles 쪽 PDF unsupported 개선이 더 커 보인다.

## memory_draft
- 2026-03-11: Telegram attachment ceiling 대응으로 stage1 link-sidecar source-switch를 확인했고, full status 기준 904 files/909 blocks 추가 수집이 이미 성립했지만 최신 telegram 증분 17건은 0 block 증가였음; 다음 확장 후보는 selected_articles의 PDF unsupported(application/pdf) 해소. Proof: `invest/stages/stage1/outputs/runtime/link_enrich_sidecar_status.json`, `invest/stages/stage1/outputs/runtime/link_enrich_sidecar_incremental_telegram_20260311T0900KST.json`, `invest/stages/stage1/outputs/runtime/news_selected_articles_status.json`
