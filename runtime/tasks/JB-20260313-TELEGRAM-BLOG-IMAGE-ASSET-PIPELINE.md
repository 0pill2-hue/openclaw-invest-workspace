# JB-20260313-TELEGRAM-BLOG-IMAGE-ASSET-PIPELINE

## 한줄 결론
선택적 보존 계약은 **지금 바로 시작 가능**합니다. 방향은 `텍스트 본문은 가볍게 유지`하되, 이미지/페이지 자산은 **drop / preview_only / keep_for_analysis / keep_and_ocr** 네 등급으로 분리하고, **Stage1 DB에는 자산 계보를 전부 남기되 Stage2 clean·Stage3에는 필요한 것만 통과**시키는 쪽이 맞습니다. **naive keep-all은 저장소를 크게 폭증시킬 가능성이 높습니다.**

## 이번 점검 범위
- 코드/문서/런타임 산출물만 소규모 점검
- production data 삭제/수정 없음

## 핵심 증거
- `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py:109-118`
  - Telegram attachment 기본 cap: `ATTACH_PDF_MAX_PAGES=25`, `ATTACH_RENDER_MAX_WIDTH=1200`, `ATTACH_PDF_KEEP_ORIGINAL=0`, `ATTACH_PDF_KEEP_BUNDLE=0`.
- `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py:675-900`
  - Telegram attachment artifact 저장.
  - `kind == 'image'`는 원본/preview/OCR 없이 meta만 남기고 종료.
- `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py:917-934`
  - Telegram raw markdown에는 `image`일 때 `ATTACH_META_PATH`/`ATTACH_ORIGINAL_PATH`를 기록하지 않음.
- `invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py:123-132, 155-165, 456-486`
  - blog HTML을 `_strip_html()`로 평탄화해서 markdown 저장. `<img>`/attachment 계열은 Stage1에서 바로 소실.
- `invest/stages/common/stage_pdf_artifacts.py:61-152, 615-887`
  - PDF page artifact는 PNG thumbnail + page text + manifest로 생성.
  - render는 `max_width` 기반 downscale, hot window 밖이면 prune.
- `invest/stages/common/stage_raw_db.py:122-134, 539-547, 802-815, 1009-1290`
  - Stage1 DB는 `qualitative/attachments/telegram`만 추적.
  - Stage2 compact mirror는 `__bundle.zip`, `__page_*.png`를 제외.
  - PDF index는 사실상 `telegram_attachment` family 하드코딩.
- `invest/stages/stage2/scripts/stage02_onepass_refine_full.py:146, 2774-2892, 3033-3090`
  - 운영 주석상 image 계열은 Stage1/2 범위에서 제외.
  - Stage2는 telegram PDF를 본문 inline 승격한 뒤 residue를 strip.
  - quarantine는 텍스트 preview만 보존.
- `invest/stages/stage3/scripts/stage03_build_input_jsonl.py:1-8, 739-877`
  - Stage3는 Stage2 clean `text/telegram`, `text/blog`만 읽음.
  - Telegram PDF도 inline text만 소비.
  - `text_image_map`, `text_images_ocr` source family enum은 있으나 현재 builder는 없음.
- 런타임 증거
  - `invest/stages/stage1/outputs/runtime/stage1_attachment_recovery_summary.json`
    - `pdf_meta_total=63966`, `pdf_canonical_ready_total=16523`, `unrecoverable_missing=47443`, `pdf_page_mapping_missing_total=47511`.
  - `invest/stages/stage2/outputs/runtime/stage2_integrity_summary.json`
    - `attachment_recovery_status=WARN:UNRECOVERABLE`, `severe_missing_ratio=0.744789`, `stage3_ready_status=DEGRADED`.
  - `invest/stages/stage3/outputs/STAGE3_INPUT_BUILD_latest.json`
    - Stage3는 `rows_from_text_telegram=2140`, `rows_from_text_blog=38467`만 소비. 이미지/페이지 artifact 직접 소비 없음.

## 현재 파이프라인 요약
1. **Stage1 Telegram**
   - 텍스트/메시지 로그 생성.
   - PDF/doc/text attachment는 meta/extracted/manifest/page artifact 일부 생성.
   - **image attachment는 meta만 남고 원본/preview/OCR 없음.**
2. **Stage1 Blog**
   - HTML body를 text markdown으로만 저장.
   - **blog image/inline asset는 수집 자체가 없음.**
3. **Stage1 DB sync**
   - raw tree를 DB에 넣고, PDF는 `pdf_documents`/`pdf_pages`로 별도 색인.
   - **blog attachment family는 없음. PDF source_family도 telegram 중심.**
4. **Stage2 clean/quarantine**
   - 텍스트 정제 중심.
   - Telegram PDF는 본문으로 승격 가능.
   - **이미지는 clean/quarantine에 canonical survivor가 없음.**
5. **Stage3 input build**
   - clean text만 읽음.
   - **PDF page/image artifact 직접 소비 없음.**

---

## 선택적 보존 계약 초안

### 공통 retention class 정의
| class | 의미 | Stage1 DB | Stage2 clean | Stage3 |
|---|---|---|---|---|
| `drop` | 분석 가치 낮음. decorative/logo/중복 썸네일 | metadata/hash만 | 통과 안 함 | 미소비 |
| `preview_only` | 사람 확인용 preview만 필요 | preview path + dims/hash + source lineage | sidecar로만 유지 | 기본 미소비, 필요시 ref만 |
| `keep_for_analysis` | 원본/고해상도는 남기되 OCR는 아직 선택 안 함 | analysis-grade binary/path + lineage | clean sidecar로 생존 | 필요시 ref 기반 선택 소비 |
| `keep_and_ocr` | 분석-grade + OCR/page text 필요 | binary/path + OCR/page text + quality | clean sidecar + 텍스트/페이지 요약 유지 | OCR text/페이지 ref 소비 |

기본 원칙:
- **Stage1 DB는 lineage SSOT**: source message/post id, asset hash, mime, size, width/height, retention class, preview/original/analysis/OCR 경로를 모두 기록.
- **Stage2 clean은 가벼워야 함**: body 본문은 lean 유지, asset는 sidecar/manifest 중심.
- **Stage3는 필요한 asset만 선택 소비**: preview를 무조건 넣지 않고, OCR text/ref 기반으로 최소 주입.

---

## 1) Telegram posts

### 현재 어디서 잃거나 degrade되는가
- `stage01_scrape_telegram_highspeed.py:724-729`
  - `kind == 'image'`는 `no_supported_media`로 meta만 저장하고 종료.
- `stage01_scrape_telegram_highspeed.py:917-926`
  - image는 raw markdown에 attach path marker를 남기지 않음.
  - 결과적으로 Stage2 text path에서 image lineage가 사실상 끊김.
- PDF는 Stage1 artifact가 있으나:
  - original delete 가능 (`ATTACH_PDF_KEEP_ORIGINAL=0` 기본값).
  - page render는 1200px preview 계열.
  - Stage2/3는 inline text만 소비.
- legacy `msg_<id>/meta.json`와 bucketed `msg_<id>__meta.json`가 혼재하여 fallback logic이 이미 복잡함.

### Stage1 DB에 반드시 저장해야 할 것
- message-level attachment manifest row (신규/확장)
  - `source_family=telegram_post`
  - `channel_slug`, `message_id`, `message_date`
  - `asset_kind` (`image|pdf|doc|web_preview|...`)
  - `retention_class`
  - `mime`, `declared_size`, `width`, `height`, `sha1`
  - `preview_rel_path`, `analysis_rel_path`, `original_rel_path`, `ocr_text_rel_path`
  - `ocr_status`, `ocr_reason`, `analysis_grade`, `human_review_window_until`
  - `derived_from_message_marker=true/false`
- image도 최소 `preview_only` 이상이면 **실제 binary path**가 필요.
- PDF는 기존 `pdf_documents/pdf_pages`를 유지하되 `retention_class`와 `analysis_grade`를 추가하는 쪽이 안전.

### Stage2 clean에 살아남아야 할 것
- 본문 text는 현재처럼 lean 유지.
- 대신 clean sidecar(예: `*.attachments.json`) 또는 classification sidecar 확장으로 아래 생존 필요:
  - selected asset list
  - retention class
  - preview/analysis/OCR refs
  - dense-text 여부, OCR 필요 여부
- Telegram PDF는 inline text 승격을 유지하되, **page manifest ref는 sidecar에도 남겨야 함**.
- image는 본문 residue로 지우더라도 **lineage ref는 clean에서 끊기면 안 됨**.

### Stage3가 소비해야 할 것
- 기본: 현재와 같이 telegram text body.
- 추가:
  - `keep_and_ocr`: OCR text / page-marked text
  - `keep_for_analysis`: asset ref만 전달하고 실제 vision 호출 시 lazy materialize
  - `preview_only`: 기본 미소비, UI/review용 ref만
- Stage3 source family는 기존 enum을 활용해 `text_image_map`, `text_images_ocr` builder를 추가하는 게 자연스러움.

### downscale 가능 / analysis-grade 유지 기준
- **안전하게 downscale 가능**
  - 일반 사진, 풍경, 이벤트 사진, 장식성 이미지
  - social preview 이미지
- **analysis-grade 유지 필요**
  - 차트/캡처/슬라이드/표/작은 글씨가 많은 스크린샷
  - annotate된 리서치 이미지
  - OCR 가치가 높은 문서형 이미지

### 권장 class 매핑
- decorative photo / meme / generic preview → `drop` 또는 `preview_only`
- chart/screenshot/slide/image with dense text → `keep_for_analysis`
- OCR가 필요한 scanned image / text-heavy screenshot → `keep_and_ocr`

---

## 2) Blog posts

### 현재 어디서 잃거나 degrade되는가
- `stage01_scrape_all_posts_v2.py:123-132, 155-165`
  - `_strip_html()`가 tag를 제거하고 `_extract_body()`는 text body만 반환.
- `stage01_scrape_all_posts_v2.py:456-486`
  - blog output markdown는 title/date/source/body만 저장.
- `stage_raw_db.stage2_default_prefixes()`에도 `qualitative/attachments/blog`가 없음.
- 실제 경로 확인 결과 `invest/stages/stage1/outputs/raw/qualitative/attachments/blog`는 없음.

### Stage1 DB에 반드시 저장해야 할 것
- post-level asset manifest row (신규)
  - `source_family=blog_post`
  - `blog_id`, `log_no`, `post_url`, `published_date`
  - `asset_url`, `asset_order`, `asset_kind=image|iframe_thumb|embed_thumb|file_link`
  - `alt_text`, `caption_text`, 주변 문맥 excerpt
  - `preview_rel_path`, `analysis_rel_path`, `original_url`, `sha1`, `mime`, `width`, `height`
  - `retention_class`, `ocr_status`
- 외부 URL은 rot 위험이 있으므로 `keep_*` class는 Stage1에서 파일로 고정 저장 필요.

### Stage2 clean에 살아남아야 할 것
- clean markdown는 본문 텍스트 중심 유지.
- 하지만 blog clean sidecar에 아래를 남겨야 함:
  - asset manifest
  - title/caption/alt text
  - `retention_class`
  - OCR text/ref
- quarantine도 지금처럼 텍스트 preview만 남기면 asset 증거가 사라지므로 `asset_count`, `asset_classes`, 대표 preview ref 정도는 같이 남겨야 함.

### Stage3가 소비해야 할 것
- 기본: clean blog text
- 추가:
  - `keep_and_ocr`: OCR text 블록 또는 `text_images_ocr` row
  - `keep_for_analysis`: `text_image_map` row 또는 asset ref
  - `preview_only`: 기본 미소비

### downscale 가능 / analysis-grade 유지 기준
- **downscale 가능**: decorative inline image, product photo, 일반 썸네일
- **analysis-grade 필요**: 블로그에 삽입된 표/차트/증권사 슬라이드/캡처형 이미지, 스캔 문서 이미지

### 권장 class 매핑
- header/footer/decorative image → `drop`
- 일반 inline photo → `preview_only`
- chart/table/screenshot → `keep_for_analysis`
- 스캔/텍스트-heavy 이미지 → `keep_and_ocr`

---

## 3) PDFs / page artifacts

### 현재 어디서 잃거나 degrade되는가
- `stage01_scrape_telegram_highspeed.py:109-118`
  - `ATTACH_PDF_MAX_PAGES=25`, `ATTACH_RENDER_MAX_WIDTH=1200` cap.
- `stage_pdf_artifacts.ensure_pdf_support_artifacts()`
  - page render는 thumbnail PNG 계열이라 preview 성격.
  - hot window 밖이면 render prune 가능.
- `stage_raw_db._stage2_generated_residue_rel_path()`
  - Stage2 compact mirror는 `__bundle.zip`, `__page_*.png`를 제거.
- `stage03_build_input_jsonl.py:1-8`
  - Stage3는 PDF page artifact를 직접 읽지 않고 inline promoted text만 소비.
- 런타임 summary:
  - `pdf_meta_total=63966`
  - `pdf_canonical_ready_total=16523`
  - `unrecoverable_missing=47443`
  - `pdf_page_mapping_missing_total=47511`

### Stage1 DB에 반드시 저장해야 할 것
기존 `pdf_documents` / `pdf_pages`를 SSOT로 유지하되 필드 보강:
- document-level
  - `source_family`를 telegram 고정이 아니라 일반화 (`telegram_attachment`, 향후 `blog_pdf`, `linked_pdf` 등)
  - `retention_class`
  - `analysis_grade`
  - `original_rel_path`, `preview_bundle_rel_path`, `analysis_source_rel_path`
  - `original_deleted_after_decompose`
  - `ocr_status`, `ocr_reason`
  - `page_cap_applied`, `width_cap_applied`
- page-level
  - `page_no`, `text_rel_path`, `preview_render_rel_path`, `analysis_render_rel_path`, `tile_manifest_rel_path`, `ocr_text_rel_path`
  - `text_chars`, `width`, `height`, `needs_tiling`

### Stage2 clean에 살아남아야 할 것
- clean body에는 **page-marked text**만 기본 유지.
- sidecar에는 반드시 남겨야 함:
  - manifest rel path
  - declared/indexed/materialized page counters
  - bounded_by_cap 여부
  - 어떤 page가 text-only / render-only / missing 인지
  - selected analysis pages / tile manifest refs
- compact mirror에서 preview PNG를 전부 빼는 현재 정책은 용량 면에서는 맞지만, **keep_for_analysis / keep_and_ocr로 선택된 page render나 tile만 예외적으로 살아남게 해야 함**.

### Stage3가 소비해야 할 것
- 기본: page-marked text (`keep_and_ocr` 또는 text layer 존재시)
- 선택: dense page만 image/tile ref 소비
- Stage3는 전체 PDF render를 무조건 먹지 말고,
  - text layer 빈 page
  - OCR confidence 낮은 page
  - chart/table dense page
  에 한해 on-demand vision 입력으로 승격하는 구조가 맞음.

### downscale 가능 / analysis-grade 유지 기준
- **preview_only**: 1200px 이하 page preview, 대표 1-3 page
- **keep_for_analysis**: 원본 PDF 또는 analysis raster 유지, Stage3엔 기본 ref만
- **keep_and_ocr**: OCR text + 필요 page tile 유지
- **analysis-grade 필요**
  - scan PDF
  - small-font slide deck
  - 표/차트가 많은 page
  - text layer 빈 page

---

## 저장소 위험 추정 및 제어안

### 왜 naive keep-all이 위험한가
런타임 수치 기반 대략치:
- `stage1_attachment_recovery_summary.json`에서 recovered original 평균
  - `282,775,282 bytes / 253 ≈ 1.066 MB/original`
- 이 평균을 `pdf_meta_total=63,966` 전체에 단순 적용하면
  - **original만 유지해도 약 66.6 GB**
- `stage2_integrity_summary.json`의 sample page density
  - `9606 pages / 378 docs ≈ 25.41 pages/doc`
- page preview를 문서당 평균 25.4 page, page당 150KB만 잡아도
  - **원본 + preview 합산 약 299 GB**
- page당 200KB면
  - **약 376.6 GB**

즉, **keep-all은 고확률로 저장소를 크게 폭증**시킵니다.

### 권장 제어안
1. **class별 저장 한도**
   - `drop`: binary 저장 없음, metadata/hash만
   - `preview_only`: 대표 preview 1개(이미지) 또는 대표 1~3 page(PDF)
   - `keep_for_analysis`: 원본 또는 analysis-grade normalized copy 1개
   - `keep_and_ocr`: 원본 + OCR text + 선택 page/tile만
2. **preview cap**
   - 일반 image preview: long edge `<= 768px`, `<= 200KB`
   - PDF preview page: long edge `<= 1200px`, `<= 250KB`
3. **analysis cap**
   - text-dense image: long edge `<= 2048px` 또는 원본 유지(작으면 원본)
   - page raster는 전 page 생성 금지, selected page 또는 tile only
4. **tiling only when needed**
   - OCR confidence 낮음
   - small-font dense chart/table
   - page text layer 없음
5. **retention lifecycle**
   - hot window(기존 31일 활용): original/analysis를 넉넉히 유지
   - cold transition 후:
     - `preview_only`: original 삭제, preview만 유지
     - `keep_for_analysis`: original 또는 normalized copy 1개만 유지, preview 다중본 정리
     - `keep_and_ocr`: OCR text + selected tiles 유지, 불필요 full-page preview prune
6. **DB mirror 정책**
   - 현재처럼 all-preview PNG를 Stage2 compact mirror에서 빼는 기본 정책은 유지
   - 대신 `keep_for_analysis`/`keep_and_ocr`로 선택된 asset만 예외 경로로 materialize

---

## 바로 시작할 첫 파일 수정 3개

### 1) `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py`
**첫 수정 내용**
- `kind == 'image'` short-circuit 제거 → retention classifier 도입
- image에 대해 `preview_path` / `analysis_path` / `retention_class` / `ocr_status`를 meta에 기록
- raw markdown에도 image용 marker (`ATTACH_META_PATH`, `ATTACH_PREVIEW_PATH`, `ATTACH_RETENTION_CLASS`)를 남기기

### 2) `invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py`
**첫 수정 내용**
- `_strip_html()` 전에 `<img>`/asset 후보 추출
- `outputs/raw/qualitative/attachments/blog/...` 신규 저장 + post-level manifest 생성
- markdown 본문에 asset marker/sidecar ref 삽입

### 3) `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
**첫 수정 내용**
- image/PDF asset manifest를 clean sidecar로 보존
- `drop`/`preview_only`는 body에서 제거하되 sidecar 생존
- `keep_for_analysis`/`keep_and_ocr`는 Stage3-ready ref(`text_image_map`/`text_images_ocr`) 생성 준비

### 바로 뒤따를 파일
- `invest/stages/stage3/scripts/stage03_build_input_jsonl.py`
  - `text_image_map`, `text_images_ocr` builder 실제 구현
  - text-only 기본 경로는 유지, image/OCR row는 선택 주입

---

## 구현 계약 제안 (짧은 버전)
- **Telegram**: image도 meta-only에서 끝내지 말고 최소 preview lineage를 Stage1에 저장. chart/screenshot는 keep_for_analysis 이상.
- **Blog**: 지금은 이미지가 Stage1에서 완전 유실되므로, 가장 먼저 attachment/blog manifest를 만들어야 함.
- **PDF/page artifact**: Stage1 DB는 계보 SSOT, Stage2 clean은 page-marked text + sidecar, Stage3는 선택 페이지/OCR만 소비.
- **저장소 정책**: keep-all 금지. preview cap, analysis cap, hot/cold retention, tile-on-demand가 필수.

## 최종 판단
- **contract 방향**: selective retention + lineage-first + Stage2/3 selective consume
- **exact first files**: 
  1. `invest/stages/stage1/scripts/stage01_scrape_telegram_highspeed.py`
  2. `invest/stages/stage1/scripts/stage01_scrape_all_posts_v2.py`
  3. `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- **naive keep-all storage explosion 여부**: **예, 매우 가능성 높음** (현재 수치 기준 대략 수십~수백 GB대로 커질 수 있음)
