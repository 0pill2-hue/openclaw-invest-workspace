# JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE — subagent verification report

작성시각: 2026-03-14 Asia/Seoul  
범위: **read-only 우선**으로 Stage1 backfill 이후 이미지/페이지 자산 파이프라인 점검 (Telegram, Blog, DB, Stage3 연결 상태)

---

## 한줄 결론
- **Telegram 일반 이미지**: 저장/resize/link/DB typed hydration이 현재 **정상 동작하지 않음 (FAIL)**
- **PDF page render**: `max_width=1200` preview resize는 **정상 확인 (PASS)**
- **Blog 이미지**: Stage1에서 수집/보존 자체가 없음 **(FAIL)**
- **DB**: raw blob sync는 되지만, typed hydration은 **PDF 전용**이며 image/blog는 미구현 **(FAIL)**

---

## 섹션별 판정

| Section | Verdict | 판단 |
|---|---|---|
| 1. Telegram 일반 이미지 저장/resize | **FAIL** | image는 meta만 쓰고 즉시 skip. 원본/preview/extract/path 미생성 |
| 2. PDF page preview resize/downscale | **PASS** | `ATTACH_RENDER_MAX_WIDTH=1200` 적용, 실제 PNG 1199px 확인 |
| 3. Telegram ↔ image linking integrity | **FAIL** | raw markdown에 image path marker가 0건 |
| 4. Blog image capture/linking | **FAIL** | HTML strip으로 `<img>` 소실, `attachments/blog` 디렉터리/DB row 없음 |
| 5. DB import / typed hydration | **FAIL** | raw DB sync는 있음. 그러나 typed index는 `pdf_documents/pdf_pages` + `telegram_attachment` only |
| 6. Stage3 image handoff | **FAIL** | Stage3는 `text/telegram`, `text/blog`만 읽음. image asset 직접 소비 없음 |

---

## 1) Telegram 일반 이미지 저장/resize 상태 — FAIL

### 코드 증거
`invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py`
- `109-118`: attachment 관련 cap 정의
  - `ATTACH_PDF_MAX_PAGES=25`
  - `ATTACH_RENDER_MAX_WIDTH=1200`
  - `ATTACH_PDF_KEEP_ORIGINAL=0`
- `724-730`: image는 즉시 skip
  - `if not kind or kind == 'image':`
  - `extraction_status = 'skip'`
  - `extraction_reason = 'no_supported_media'`
- `926-936`: image는 attach path 통계/본문 marker에서 제외됨
  - `kind not in ('', 'image')` 조건으로 path marker counting

### 런타임/파일시스템 증거
실행 커맨드(요약): Telegram attachment meta/file census, raw markdown image message census

주요 결과:
- Telegram attachment meta kind counts
  - `pdf: 63963`
  - `image: 3839`
  - `docx: 2`
  - `unknown: 109`
  - `document: 70`
- `telegram_image_meta_total = 3839`
- 그중
  - `telegram_image_meta_with_original_path = 0`
  - `telegram_image_meta_with_extract_path = 0`
  - `telegram_image_meta_with_manifest_path = 0`
- attachment 저장소 확장자 집계
  - `*.jpg 0`
  - `*.jpeg 0`
  - `*.webp 0`
  - `*.gif 0`
  - `*.png 4073` ← PDF page render PNG

즉, **Telegram 일반 이미지용 binary survivor가 현재 없음**.

### 샘플 meta 증거
샘플 파일:
- `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/Nihil_s_view_of_data_information_viewofdata/bucket_122/msg_3066__meta.json`
- 확인값:
  - `kind: image`
  - `mime: image/jpeg`
  - `original_path: ""`
  - `extract_path: ""`
  - `extraction_status: skip`
  - `extraction_reason: no_supported_media`

### 판정
- Telegram 일반 이미지는 **저장도 안 되고, resize/downscale도 안 되고, extract도 안 됨**.
- 현재 동작하는 resize는 **PDF page render 서브경로뿐**이다.

---

## 2) PDF page preview resize/downscale 상태 — PASS

### 코드 증거
`invest/stages/common/stage_pdf_artifacts.py`
- `106-117`
  - `pdf_page_artifacts.swift <...> <max_pages> <max_width> <max_chars>`
  - `maxWidth = max(320, Int(args[5]) ?? 1200)`
- `861-869`
  - manifest에 `max_width_applied` 기록
  - `render_status`, `render_reason` 기록
- `827-830`
  - hot window 밖이면 render prune

### 샘플 manifest + 실제 PNG 치수
DB에서 recent `render_status='ok'` 문서 1건 추출:
- doc: `telegram:루팡_bornlupin:16999`
- manifest: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/루팡_bornlupin/bucket_103/msg_16999__pdf_manifest.json`
- manifest 핵심값:
  - `max_width_applied: 1200`
  - `render_status: ok`
  - `quality_grade: A`
  - page 1 render path 존재

실제 치수 확인 커맨드:
```bash
sips -g pixelWidth -g pixelHeight \
  /Users/jobiseu/.openclaw/workspace/invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/루팡_bornlupin/bucket_103/msg_16999__page_001.png
```
결과:
- `pixelWidth: 1199`
- `pixelHeight: 1694`

### 판정
- **PDF page preview render는 width cap ~1200px로 실제 적용되고 있음.**
- 단, 이 PASS는 **PDF page render 전용**이며, Telegram 일반 이미지 파이프라인 PASS가 아님.

---

## 3) Telegram ↔ image linking integrity — FAIL

### raw markdown marker 구조 확인
커맨드(요약): Telegram raw markdown를 message 단위로 분해해 `[ATTACH_KIND] image` 메시지의 path marker 유무 집계

결과:
- `messages_total = 254686`
- `messages_with_image_kind = 5541`
- `image_messages_with_meta_path = 0`
- `image_messages_with_original_path = 0`
- `image_messages_with_text_path = 0`
- `image_messages_with_attach_text = 568`
- `image_messages_with_text_status = 763`

즉, **image message는 raw markdown 본문에서 asset path로 연결되지 않음**.

### 샘플 raw markdown 증거
파일:
- `invest/stages/stage1/outputs/raw/qualitative/text/telegram/Nihil_s_view_of_data_information_viewofdata_full.md`
- `MessageID: 3066` 근처 확인 결과:
  - `[MEDIA] MessageMediaWebPage`
  - `[MIME] image/jpeg`
  - `[FILE_SIZE] 123726`
  - `[ATTACH_KIND] image`
  - **`[ATTACH_META_PATH]` 없음**
  - **`[ATTACH_ORIGINAL_PATH]` 없음**
  - **`[ATTACH_TEXT_PATH]` 없음**

파일:
- `invest/stages/stage1/outputs/raw/qualitative/text/telegram/Stock_Trip_stocktrip_full.md`
- `MessageID: 5415` 근처 확인 결과도 동일:
  - `[MEDIA] MessageMediaPhoto`
  - `[ATTACH_KIND] image`
  - path marker 없음

### 특이사항
- image 메시지 중 `568`건은 `[ATTACH_TEXT]` 블록이 있고, `763`건은 `[ATTACH_TEXT_STATUS]`가 있음.
- **하지만 path marker는 0건**이라서, 이 텍스트가 있어도 **어느 binary/image asset에서 나온 것인지 lineage가 끊겨 있음**.
- 이 inline text의 기원은 **미확인**. 확인된 사실은 “path-linked image asset은 없다”는 점뿐.

### 판정
- Telegram image linkage는 **깨져 있음**.
- 메시지 본문에 image 존재 표시만 있고, **asset path / preview path / original path / extract path를 따라갈 수 없다**.

---

## 4) Blog image capture / linking — FAIL

### 코드 증거
`invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py`
- `123-132`: `_strip_html()`가 `<img>` 포함 모든 태그를 제거
- `155-165`: `_extract_body()`는 stripped text만 반환
- `463-486`: 저장되는 것은 `title/date/source/body` 텍스트뿐

즉, Blog는 **본문 HTML에서 image asset를 별도 추출하지 않고 text flatten만 수행**.

### 파일시스템/출력 증거
커맨드:
```bash
find invest/stages/stage1/outputs/raw/qualitative -maxdepth 2 -type d | sort | grep '/attachments'
```
결과:
- `.../qualitative/attachments`
- `.../qualitative/attachments/telegram`
- **`attachments/blog` 없음**

전체 blog markdown 스캔 결과:
- `files = 41551`
- `img_tag_hits = 0`
- `md_image_hits = 0`
- `http_image_url_hits = 4` (plain URL 잔존 수준)

### DB 증거
SQLite query 결과:
- `raw_blog_attachment_rows = 0`

### 판정
- Blog 이미지는 **수집되지 않고**, 따라서 **linking도 불가**.
- Stage1 backfill 이후에도 Blog image asset pipeline은 **사실상 미구현 상태**.

---

## 5) DB import / integration / typed hydration — FAIL

### raw DB sync 자체는 존재
DB 파일:
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`

`sync_meta` 확인 결과:
- `last_sync_finished_at = 2026-03-14T01:05:30.181771+00:00`
- `schema_version = 4`
- `last_sync_summary.scanned_files = 459815`
- `raw_artifacts COUNT = 537765`

즉, **raw blob ingest 자체는 수행됨**.

### 그러나 typed hydration은 PDF-only
`invest/stages/common/stage_raw_db.py`
- `120-137`: tracked attachment path는 `qualitative/attachments/telegram`만 특별 처리
- `802-817`: `stage2_default_prefixes()`에 `qualitative/attachments/blog` 없음
- `1039-1043`: `index_pdf_artifacts_from_raw()`는 `kind != 'pdf'`면 continue
- `1141-1152`: typed table insert 대상은 `pdf_documents`
- source family는 실제 DB에서 전부 `telegram_attachment`

실제 DB query 결과:
- `pdf_documents_total = 63966`
- `pdf_pages_total = 247828`
- `pdf_documents_source_family = [('telegram_attachment', 63966)]`
- `raw_telegram_attachment_rows = 367151`
- `raw_blog_attachment_rows = 0`

즉,
1. raw artifact blob는 들어감  
2. typed hydration은 `pdf_documents/pdf_pages` 중심  
3. image/blog 전용 typed table/typed hydration은 없음

### backfill status와 DB reindex 특이사항
파일:
- `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`

핵심값:
- `pdf_db_reindex_attempted = 1`
- `pdf_db_reindex_ok = 0`
- `pdf_db_reindex_failed = 1`
- `pdf_db_status = error`
- `pdf_db_error = OperationalError`

반면 현재 DB는 populated 상태(`pdf_documents=63966`)라서,
- backfill 당시 DB reindex step은 **에러 스냅샷이 남아 있음**
- 하지만 이후 시점 DB 파일에는 PDF typed rows가 존재함

### 판정
- **raw DB import = PASS에 가까움**
- **image/blog typed hydration = FAIL**
- 사용자가 묻는 “DB-hydrated correctly after backfill?”에 대한 보수적 결론은 **FAIL**
  - 이유: image/blog 자산은 typed lineage로 안 올라오고, PDF만 부분적으로 올라옴

---

## 6) Stage3 handoff 상태 — FAIL (image 관점)

### 코드/런타임 증거
`invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
- `1-8`: Telegram PDF는 Stage2 clean text inline 승격분만 인입한다고 명시
- `739-877`: 실제 builder는 `text/telegram`, `text/blog` markdown만 읽음

런타임 summary:
- `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json`
- `rows_from_text_telegram = 2140`
- `rows_from_text_blog = 38467`
- image asset source family 직접 소비 수치 없음

### 판정
- Stage3는 **image asset lineage를 직접 소비하지 않음**.
- 즉 Stage1 image pipeline이 살아 있어도 현재 Stage3는 그 자산을 직접 활용하지 않는 구조다.

---

## 최종 판단

### 확인된 것
1. **PDF page preview resize는 정상**이다. (`max_width≈1200px` 실제 파일로 확인)
2. **Telegram 일반 이미지**는 현재 backfill/Stage1 파이프라인에서 **저장되지 않고**, 따라서 **downscale/link/DB typed hydration도 안 된다**.
3. **Blog 이미지**는 Stage1에서 **아예 수집되지 않는다**.
4. **DB는 raw sync는 되지만 typed hydration은 PDF 전용**이라 image/blog 자산 lineage SSOT로 보기 어렵다.

### 최종 답변
- “이미지가 downscaled 되는가?”  
  - **Telegram 일반 이미지: 아니오 (FAIL)**  
  - **PDF page render preview: 예 (PASS)**
- “Telegram/Blog image linking이 되는가?”  
  - **아니오 (FAIL)**
- “DB가 backfill 후 image/blog asset까지 hydration 되었는가?”  
  - **아니오. PDF 일부만 typed hydration, image/blog는 미흡/미구현 (FAIL)**

---

## 운영 가드레일 반영 (주인님 지시)
- **이번 티켓에서는 블로그·텔레그램·PDF 관련 산출물은 보류**한다.
- **이미지 저장이 안 된 데이터 / 안전성 미확정 이미지 데이터는 삭제·이동 금지**
- 삭제/수정 시 **`이미지 관련 없음` 기준을 엄격 적용**한다.
- **미확인 이미지 경로는 건드리지 않는다.**
  - 예: `outputs/raw/qualitative/attachments/telegram/**`
  - 예: selected 이미지 캐시 / image preview cache / bundle / render archive 성격의 경로 전반
- 우선 점검/조치 범위는 **임시 로그, 텍스트/메타/인덱스/상태파일/중간결과, 비이미지 파생 산출물, review/docs 증빙류**로 제한
- 이미지 관련 조치는 **보존 우선, read-only 확인 우선, 경로 분리 명시** 원칙 적용

## 이번 티켓 제외 범위 (명시)
다음은 **이번 티켓에서 검토/정리/수정 대상에서 제외**한다:
1. **Blog 관련 산출물 전반**
   - blog raw/clean/quarantine 및 blog attachment 성격 경로
2. **Telegram 관련 산출물 전반**
   - telegram raw/clean/quarantine 및 attachment 성격 경로
3. **PDF 관련 산출물 전반**
   - pdf original / manifest / page text / render / bundle / pdf DB typed hydration 관련 산출물
4. 이미지 cache / preview / bundle / render archive / selected image cache 성격 경로 전반
5. provenance 미확정 image/message 흔적 전반

즉, **이번 티켓의 실제 우선 검토/정리 대상은 블로그·텔레그램·PDF를 제외한 나머지 비이미지 산출물**이다.

## 삭제·변경 대상 / 예외 분리

### A. 우선 처리 가능 (권장)
다음은 **블로그·텔레그램·PDF와 무관하고 `이미지 관련 없음`이 명확한 경로만** 검토 권장:
1. `outputs/runtime/*.json` 계열의 **상태 요약/재생성 가능한 통계 파일**
   - 단, blog/telegram/pdf 전용 상태파일은 이번 티켓에서 제외
2. `runtime/tmp/**` 계열의 **실험/검증용 중간 산출물** 중 image cache/bundle과 무관한 경로
3. 재생성 가능한 **text/review/docs/임시로그/임시증빙**
4. 비이미지 **텍스트/메타/인덱스/상태파일/중간결과**의 검증/정리
5. 비이미지 파생 산출물의 구조/명명/증빙 정리

### B. 삭제·변경 금지 / 예외 취급 (보류 범위 포함)
다음은 **삭제·이동·정리 대상에서 제외**:
1. `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/**` 전체
2. Blog 관련 산출물 전반
3. Telegram 관련 산출물 전반
4. PDF 관련 산출물 전반
5. selected 이미지 캐시 / preview cache / render cache / bundle / archive로 해석될 수 있는 경로 전반
6. path가 비어 있더라도 image 계열로 분류된 Telegram attachment 흔적
7. 이미지와 연결되었을 가능성이 있으나 provenance가 불명확한 inline `[ATTACH_TEXT]`, `[ATTACH_TEXT_STATUS]` 증거
8. 현재 binary가 없더라도 추후 recovery 단서가 될 수 있는 image/message metadata

### C. 제한적 변경 허용 (이번 티켓 실제 범위)
다음은 **블로그·텔레그램·PDF를 제외한 비이미지 경로에서만** 변경 검토 가능:
1. text-only ingest/validation 보강
2. 비이미지 메타/인덱스/상태파일 정합성 점검
3. DB summary/report 쿼리 개선
4. 중간 로그/요약 리포트의 포맷 정리
5. review/docs/text 증빙 파일의 구조화·정리
6. 재생성 가능한 중간결과/임시 산출물 정리

## 추천 후속 액션 (판정용 메모)
1. **즉시 조치 우선순위는 임시 산출물/중간 로그 정리**로 제한
   - runtime summary/status/proof 산출물 중 재생성 가능한 파일만 정리 후보로 관리
2. Telegram image는 **삭제/이동 없이 현 상태 보존**
   - `kind=image` meta, raw markdown image markers, 관련 status 증거는 보존
3. Blog image는 **수집 미구현 상태를 유지한 채 증거만 정리**
   - 성급한 backfill 재시도나 경로 정리는 보류
4. DB 측은 **image/blog typed hydration 추가 전까지 현행 상태를 FAIL로 유지**
   - 단, raw sync/PDF typed index와 image 미지원 상태를 리포트에서 분리 표기
5. 차기 구현 작업이 열리면 그때에만
   - Telegram image `original/preview/meta_path` 생성
   - Blog `<img>` / asset manifest 추출
   - generalized asset table 또는 image/blog typed hydration 추가
   - Stage3 asset ref sidecar 소비 경로 추가

---

## Raw 삭제 후보 산정 (실제 삭제 미실행, 산정만)

요청 반영하여 **블로그/텔레그램/PDF 산출물은 후보 계산에서 제외**하고, 나머지 비이미지/비해당 prefix를 기준으로 재산정했습니다.

- 산정 기준: Stage1 raw에서 `최근 1개월 초과분`을 `2026-03-14` 기준으로 `2026-02-14` 이전으로 판정
- 산정 대상은 **파일명 기반 날짜 추론이 가능한 비이미지/비보류(prefix)** 중심
- 산정 방식: 실제 삭제/이동 없이 경로 스캔 + 후보 목록 추출 + 증빙 저장만 수행

### 산정 결과 요약

- 후보 경로 수: **1,800건**
- 후보 용량: **5,452,735 bytes**
- 산정 근거 파일:
  - `runtime/tasks/proofs/JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE_raw_delete_candidates_nonimage.tsv`
  - `runtime/tasks/proofs/JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE_raw_delete_candidate_summary.json`
  - `runtime/tasks/proofs/JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE_raw_delete_excluded_prefixes.json`

### 삭제 후보(비이미지 위주) prefix별(유효 후보 수 기준 상위)

1) `qualitative/text/premium/startale`
- 총 파일: 972
- 삭제후보: 900
- 후보용량: 2,730,300 bytes

2) `qualitative/link_enrichment/text/premium`
- 총 파일: 972
- 삭제후보: 900
- 후보용량: 2,722,435 bytes

나머지 prefix는 다음 이유로 후보가 0건이거나 날짜 규칙 미적용:
- `signal/kr/ohlcv`, `signal/kr/supply`, `signal/us/ohlcv`, `signal/market/macro`: 롤링(현재상태) CSV형태로 파일명에 run-date 없음
- `qualitative/kr/dart`: `dart_list_YYYYMMDD_...` 형식은 20260214 이후만 존재(현재 산정 기준 미만 없음)
- `qualitative/market/rss`: `rss_YYYYMMDD-...` 형식은 20260214 이후만 존재
- `qualitative/market/news/selected_articles`: 202603xx만 존재
- `qualitative/market/news/url_index`: 20260305~ 기준 스냅샷 중심, 2026-02-14 이전 없음
- `qualitative/text/premium/startale_channel_direct`: 메타/디스커버리성 경로(스냅샷 날짜 규칙 적용 제외)

## 삭제 후보 제외 항목 (명시 보류)

본 티켓의 raw 삭제 산정에서 아래는 **명시적으로 제외**했습니다.

1. `qualitative/attachments/telegram` (총 367,279건 / 6,451,958,394 bytes)
2. `qualitative/text/telegram` (총 75건 / 221,690,086 bytes)
3. `qualitative/text/blog` (총 41,551건 / 157,624,441 bytes)
4. `qualitative/link_enrichment/text/blog` (총 41,548건 / 43,515,538 bytes)
5. `qualitative/link_enrichment/text/telegram` (총 71건 / 15,001,643 bytes)

제외 사유:
- 사용자 지시: 티켓 범위에서 blog/telegram/pdf는 삭제/정리 대상이 아닌 보류
- 이미지 안전성 미확정 경로/선택지 경로 보전

### 최종 상태

- **실제 파일 조치 없음**: 이번 단계는 산정(리스트업)만 수행했고, 삭제/이동은 없습니다.
