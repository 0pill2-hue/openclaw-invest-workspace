# Stage2 PDF Refinement Design

- Status: **VALIDATED / implemented in `invest/stages/stage2/scripts/stage02_onepass_refine_full.py` (`stage2-refine-20260308-r4`)**
- Change type: **Rule**
- Scope: Stage1에 **이미 존재하는 로컬** Telegram attachment artifact(`original/meta/extracted`)를 Stage2 refine 입력으로 승격하는 canonical 계약 + 구현 기준
- Goal: Stage1이 저장한 Telegram PDF 원본/메타를 Stage2 clean corpus가 실제로 읽어 downstream(Stage3)까지 활용 가능하게 만든다.
- Non-goal:
  - Stage1 책임을 clean/quarantine까지 확장하지 않는다.
  - image 계열 attachment/OCR 재도입은 하지 않는다.
  - 외부 API/클라우드 OCR/LLM 요약은 사용하지 않는다.

## 1) Canonical decision

이번 설계의 canonical 결정은 아래다.

1. **Telegram PDF는 별도 `telegram_pdf` corpus를 만들지 않는다.**
2. Stage2는 기존 `qualitative/text/telegram` 정제 흐름을 유지하되, **메시지 단위 parser + PDF sidecar join**을 추가한다.
3. PDF 본문은 해당 Telegram 메시지 본문에 **inline 승격**한다.
4. clean/quarantine 판정은 **메시지 caption/body + PDF 정제 본문 합산 기준**으로 수행한다.
5. attachment-specific 실패 사유는 새 독립 corpus가 아니라 **report/sidecar diagnostics**로 남긴다.

왜 이렇게 결정하는가:
- 별도 `telegram_pdf` 트랙을 만들면 Stage3 입력 계약까지 손대야 한다.
- 같은 메시지의 caption과 PDF 본문이 분리되면 문맥이 깨진다.
- 기존 `text/telegram` clean output을 유지한 채 additive하게 확장하는 편이 downstream 변경이 가장 작다.

## 2) 현재 관측 사실 (grounded)

### Stage1 저장 위치
- Telegram raw log: `invest/stages/stage1/outputs/raw/qualitative/text/telegram/*.md`
- Telegram attachment artifact canonical root: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/<channel_slug>/bucket_<nn>/`
- canonical file family: `msg_<message_id>__{meta,original,extracted,pdf_manifest,page_XXX,bundle}.<ext>`
- legacy compatibility shadow: `.../<channel_slug>/msg_<message_id>/meta.json` 디렉터리 구조가 historical data에 남을 수 있으나, current Stage1/Stage2 code에서는 **fallback only** 로 취급한다.

### Stage1 raw Telegram message marker
Stage1 raw Telegram 로그에는 아래 marker가 관측된다.
- `[ATTACH_KIND] pdf|image|...`
- `[ATTACH_ARTIFACT_DIR] ...`
- `[ATTACH_ORIGINAL_PATH] ...`
- `[ATTACH_META_PATH] ...`
- `[ATTACH_TEXT_PATH] ...`
- `[ATTACH_TEXT] ... [/ATTACH_TEXT]`
- `[ATTACH_TEXT_STATUS] ...`

### Stage1 attachment meta.json 관측 필드
현재 샘플 meta.json에는 아래 필드가 존재한다.
- `saved_at`
- `channel_title`
- `channel_username`
- `channel_slug`
- `message_id`
- `message_date`
- `kind`
- `mime`
- `declared_size`
- `original_name`
- `artifact_dir`
- `original_path`
- `extract_path`
- `meta_path`
- `original_store_status`
- `original_store_reason`
- `extraction_status`
- `extraction_reason`

### 현재 Stage2 처리 상태
- `stage02_onepass_refine_full.py` 입력 루트는 `invest/stages/stage2/inputs/upstream_stage1`이다.
- 구현본(`stage2-refine-20260308-r4`)은 `raw/qualitative/text/telegram/*.md`를 메시지 단위로 파싱하고, 같은 채널의 `attachments/telegram` sidecar를 **marker 우선 → bucketed flat canonical fallback → legacy dir fallback** 순으로 조인한다.
- canonical clean 출력은 계속 `qualitative/text/telegram/*.md`이며, 승격 성공 시 `[ATTACHED_PDF] <normalized_title>` 블록으로 inline merge한다.
- attachment marker/fallback이 모두 불충분한 historical 케이스는 clean 승격 대신 report diagnostics(`telegram_pdf_orphan_artifacts`)로 남긴다.
- Stage2에서 말하는 recovery는 **로컬 artifact 경로 복구(path resolution) + local extract fallback** 까지다. Telegram에서 missing original을 다시 다운로드하는 upstream recovery는 Stage1 범위다.

### 현재 데이터 스냅샷(문서 작성 시점 관측)
- historical raw log와 attachment tree는 항상 1:1로 완전 일치한다고 가정하면 안 된다.
- 과거 raw에는 `ATTACH_META_PATH` marker가 빠진 메시지가 존재할 수 있다.
- Stage1의 inline `[ATTACH_TEXT]`는 legacy/image residue를 포함할 수 있으므로 **PDF clean body의 primary source로 쓰면 안 된다.**

## 3) 설계 원칙

1. Stage1은 raw/state 저장까지만 책임진다. clean/quarantine 판정은 Stage2 책임이다.
2. Telegram PDF는 `text/telegram`의 **메시지 보강 입력**이지 별도 정성 corpus가 아니다.
3. image attachment는 계속 제외한다. image에서 나온 inline `ATTACH_TEXT`도 PDF 승격 입력으로 쓰지 않는다.
4. Stage2는 Telegram message lineage(`channel + message_id + date`)를 잃지 않은 상태에서만 PDF를 승격한다.
5. 경로 해석, 본문 추출, residue 제거, 중복 판정은 결정적(deterministic)이어야 한다.
6. 기존 `text/telegram` clean/quarantine 계약을 깨지 않는 additive rollout이어야 한다.

## 4) 입력 계약 (Input Contract)

계약명: `telegram_pdf_candidate_v1`

### 입력 단위
Stage2가 승격하는 최소 단위는 **Telegram message + PDF artifact pair**다.
PDF 파일만 단독으로 clean 승격하지 않는다.

### 필수 입력 구성
1. parent telegram raw message block
2. attachment `meta.json`
3. attachment `original` PDF file
4. attachment `extracted.txt`는 optional

### parent message에서 필요한 값
- `telegram_log_rel_path`
- `channel_slug` (또는 현재 naming에서 derivable slug)
- `message_id`
- `message_date`
- `attach_kind=pdf`

### meta.json에서 필요한 값
- `kind=pdf`
- `channel_slug`
- `message_id`
- `artifact_dir`
- `meta_path`
- `original_path` 또는 실제 original PDF 존재
- `extraction_status`
- `extract_path` (있으면)

### optional fields
- `channel_title`
- `channel_username`
- `mime`
- `declared_size`
- `original_name`
- raw marker의 `ATTACH_*_PATH`

### source-of-truth 우선순위
- message lineage: parent telegram block
- attachment identity: `meta.json`
- attachment bytes: original PDF
- extracted text seed: `extracted.txt`
- inline `[ATTACH_TEXT]`는 lineage 보조 참고값일 뿐 canonical source가 아니다.

## 5) Discovery / path resolution

### 5.1 Primary discovery
1. Stage2가 `raw/qualitative/text/telegram/*.md`를 읽는다.
2. 파일 단위가 아니라 **message block 단위**로 파싱한다.
3. 아래 조건을 만족하면 PDF candidate로 본다.
   - `MessageID:` 존재
   - `Date:` 존재
   - `[ATTACH_KIND] pdf` 존재
4. block 안의 `ATTACH_META_PATH` / `ATTACH_ORIGINAL_PATH`가 있으면 우선 사용한다.

### 5.2 Path rewrite rule
Stage1 raw marker에는 Stage1 기준 경로가 남을 수 있다.
예:
- Stage1 marker: `outputs/raw/qualitative/attachments/telegram/...`
- Stage2 upstream actual root: `invest/stages/stage2/inputs/upstream_stage1/raw/qualitative/attachments/telegram/...`

따라서 Stage2는 아래 rewrite를 적용한다.
- `outputs/raw/qualitative/...` → `raw/qualitative/...`
- rewritten relative path를 `invest/stages/stage2/inputs/upstream_stage1/` 아래에서 resolve

### 5.3 Secondary fallback discovery
primary marker path가 없거나 resolve 실패하면 fallback을 허용한다.
- telegram log stem이 `<channel_slug>_full.md`면 `_full` 제거 후 `channel_slug` 사용
- fallback order:
  1. bucketed flat canonical path
     - `raw/qualitative/attachments/telegram/<channel_slug>/bucket_<nn>/msg_<message_id>__meta.json`
     - 같은 bucket의 `msg_<message_id>__original__*`, `msg_<message_id>__extracted.txt`
  2. legacy compatibility dir
     - `raw/qualitative/attachments/telegram/<channel_slug>/msg_<message_id>/meta.json`
     - 같은 디렉터리의 original PDF / extracted.txt

주의:
- current Stage1/Stage2 contract에서 **bucketed flat path가 canonical** 이고, legacy dir는 historical shadow/fallback일 뿐이다.
- `bucket_<nn>` 값은 `message_id`에서 결정적으로 계산되며, 문서에서는 bucket count 상수를 하드코딩하지 않는다.
- 규칙이 맞지 않으면 추정하지 말고 `미확인`/quarantine 처리한다.

### 5.4 Orphan artifact policy
attachment tree에 file이 있어도 parent message block을 찾지 못하면 clean 승격하지 않는다.
권장 disposition:
- report/diagnostics에 orphan count 집계
- candidate가 아니라 orphan artifact로 별도 diagnostics reason 처리

### 5.5 Recovery boundary (canonical)
이 문서에서 recovery는 아래까지만 뜻한다.
1. marker path rewrite
2. bucketed flat canonical fallback resolve
3. legacy dir fallback resolve
4. local original PDF가 있을 때 Stage2 extractor chain으로 본문 복구

이 문서의 recovery에 **포함되지 않는 것**:
- Telegram API/credential/session을 사용한 missing original 재다운로드
- Stage1 attachment writer/backfill 정책 자체 변경
- upstream artifact 재수집 orchestration

즉, missing original을 다시 가져오는 upstream recovery의 SSOT는 Stage1 문서/코드이며, Stage2 문서는 그 결과로 **로컬에 존재하는 artifact를 어떻게 소비하는지**만 고정한다.

## 6) Promotion flow

### Step A. Candidate selection
- raw Telegram message block에서 `ATTACH_KIND=pdf`만 선택
- image/docx/text_doc/unsupported kind는 본 설계 범위 밖

### Step B. Artifact resolution
- primary marker path resolve
- 실패 시 secondary fallback resolve
- `meta/original/extracted` 존재 여부와 parent-message 매칭 검증

### Step C. Text source selection
우선순위는 아래다.
1. `meta.extraction_status == ok` 이고 `extract_path`가 실제 존재하면 Stage1 `extracted.txt` 재사용
2. 아니면 Stage2가 `original` PDF에서 로컬 deterministic extractor chain 수행
3. 둘 다 실패하면 clean 승격하지 않고 diagnostics/quarantine로 남김

권장 extractor order:
- `pypdf`
- `pdfminer`

금지:
- 외부 API
- 클라우드 OCR
- 모델 기반 요약/재작성

### Step D. Inline promotion
PDF 본문은 별도 corpus가 아니라 **부모 Telegram 메시지 본문에 붙인다.**

권장 merge 규칙:
1. 기존 message caption/body를 먼저 유지
2. 본문이 비어 있지 않으면 blank line 1~2개 추가
3. attachment 제목은 `original_name` 정규화 또는 파일명에서 추출
4. 그 아래에 정규화된 PDF 본문을 붙인다
5. `ATTACH_*`, `MEDIA`, `MIME`, `FILE_SIZE`, transport residue는 clean output에서 제거한다

### Step D-1. Canonical merge wording
clean telegram 본문에는 장황한 provenance 문구를 넣지 않고, 아래의 **최소 표식 한 줄만** 허용한다.

```text
[ATTACHED_PDF] <normalized_title>
<pdf_body_text>
```

규칙:
- `<normalized_title>`은 `original_name` 또는 파일명 기반으로 정규화한다.
- `saved_at`, `meta_path`, `original_path`, `extract_source`, `reason` 같은 provenance/debug 정보는 **본문에 넣지 않는다**.
- 동일 메시지 내 다중 PDF가 있을 때는 attachment 순서대로 위 블록을 반복한다.
- PDF 본문이 비어 있거나 추출 실패면 `[ATTACHED_PDF]` 표식 자체를 clean 본문에 남기지 않는다.

결과적으로 Stage2 clean telegram 메시지는 아래 의미를 갖는다.
- 원래 메시지 텍스트
- + 같은 메시지에 첨부된 PDF의 실질 본문

### Step E. Validation
최소 clean 계약:
- lineage 필드 완비
- `kind=pdf`
- original PDF 존재 확인
- normalize 후 body non-empty
- 동일 `(channel_slug, message_id)` 중복 아님

의미 본문 판정은 **message body + promoted PDF body 합산 기준**으로 수행한다.
즉 기존 telegram 본문이 짧아도 PDF 본문이 충분하면 clean 승격 가능하다.

### Step F. Report / diagnostics
attachment 실패가 메시지/채널 전체를 자동 FAIL로 만들 필요는 없다.
대신 아래 통계를 refine report에 추가한다.
- `telegram_pdf_total`
- `telegram_pdf_stage1_extract_reused`
- `telegram_pdf_stage2_extract_ok`
- `telegram_pdf_extract_failed`
- `telegram_pdf_messages_promoted_by_pdf`
- `telegram_pdf_orphan_artifacts`
- `telegram_pdf_path_resolution_marker`
- `telegram_pdf_path_resolution_fallback`

## 7) Deterministic normalization rules

규칙명: `telegram_pdf_normalize_v1`

1. `kind=pdf`만 허용
2. Stage1-relative marker path를 Stage2 upstream root 기준으로 rewrite
3. text source precedence는 `stage1_extracted > stage2_pdf_extract`
4. UTF-8 decode/CRLF→LF/null byte 제거
5. trailing space 제거
6. 연속 blank line은 최대 2개로 축약
7. `ATTACH_*`, `MEDIA`, `FILE_NAME`, `MIME`, `FILE_SIZE`, transport/meta line 제거
8. body 양끝 trim
9. semantic rewrite 금지(요약/번역/추론/투자판단 라벨링 금지)
10. image residue는 clean 본문에 남기지 않는다
11. PDF-specific cleanup을 추가한다.
   - 페이지 번호만 있는 line 제거
   - 문서 전반에 반복되는 header/footer 후보 line 제거(동일/유사 line이 여러 page chunk에서 반복될 때만)
   - `본 자료는`, `무단전재`, `저작권`, `배포 금지`, `면책` 등 전형적 배포 boilerplate는 반복/고정 패턴일 때 제거
   - 줄바꿈 때문에 쪼개진 문장/하이픈 분절은 결정적 규칙으로만 복원한다
   - 표/멀티컬럼 추출 찌꺼기는 과도하게 재구성하지 않고, 비문자/공백 위주 residue만 최소 제거한다
12. `pdf_body_text`는 기존 telegram effective-body 규칙 전에 아래 추가 신호를 계산한다.
   - `pdf_chars_added`
   - `pdf_nonempty_lines_added`
   - `pdf_source=stage1_extracted|stage2_pdf_extract`

## 8) Diagnostics / quarantine taxonomy

attachment-specific 실패 사유는 가능하면 기존 `telegram_effective_body_*`를 깨지 않고, report extra/meta 또는 quarantine payload에 남긴다.

권장 reason names:

### discovery / contract
- `telegram_pdf_parent_block_missing`
- `telegram_pdf_kind_not_pdf`
- `telegram_pdf_meta_missing`
- `telegram_pdf_path_unresolvable`
- `telegram_pdf_meta_message_mismatch`
- `telegram_pdf_meta_channel_mismatch`
- `telegram_pdf_orphan_artifact`

### source artifact
- `telegram_pdf_original_missing`
- `telegram_pdf_original_not_pdf`
- `telegram_pdf_extract_failed`

### normalization / validation
- `telegram_pdf_body_empty_after_normalize`
- `telegram_pdf_duplicate_source_message`
- `telegram_pdf_exception:<ExceptionType>`

운영 원칙:
- `stage1 extracted.txt`가 없다는 이유만으로 바로 quarantine하지 않는다.
- original PDF가 있고 Stage2 extraction이 성공하면 clean 승격 가능하다.
- attachment-specific 실패는 가능한 한 per-message diagnostics로 남기고, 채널 전체 FAIL로 과대 승격하지 않는다.

## 9) Output contract

### 9.1 Canonical clean output
canonical clean output은 계속 기존 경로를 사용한다.
- `invest/stages/stage2/outputs/clean/production/qualitative/text/telegram/*.md`

즉, **별도 `text/telegram_pdf` output folder를 canonical로 두지 않는다.**

### 9.2 Quarantine / diagnostics output
PDF 관련 세부 실패는 별도 sidecar diagnostics로 남기는 것을 권장한다.
예:
- `invest/stages/stage2/outputs/quarantine/production/qualitative/text/telegram_pdf_diagnostics/*.jsonl`
- 또는 refine report JSON 안의 dedicated section

목적:
- 기존 telegram clean corpus는 그대로 유지
- attachment 실패/경로 mismatch는 structured diagnostics로 추적
- Stage3 입력 계약은 변경하지 않음

### 9.3 Clean lineage extension
기존 clean telegram output에는 본문만 inline으로 승격하고, structured lineage/provenance는 report JSON 또는 internal sidecar에 남긴다.
권장 structured field:
- `channel_slug`
- `message_id`
- `attachment_meta_rel_path`
- `attachment_original_rel_path`
- `promotion_text_source` (`stage1_extracted|stage2_pdf_extract`)
- `promotion_body_chars`
- `pdf_chars_added`
- `pdf_nonempty_lines_added`
- `pdf_title_normalized`
- `pdf_promoted` (bool)

### 9.4 Report / diagnostics meta (recommended)
refine report 또는 diagnostics sidecar에는 아래 집계를 추가한다.
- run-level
  - `telegram_pdf_total`
  - `telegram_pdf_stage1_extract_reused`
  - `telegram_pdf_stage2_extract_ok`
  - `telegram_pdf_extract_failed`
  - `telegram_pdf_messages_promoted_by_pdf`
  - `telegram_pdf_chars_added_total`
- per-message / diagnostics
  - `pdf_promoted`
  - `pdf_source`
  - `pdf_chars_added`
  - `pdf_nonempty_lines_added`
  - `pdf_title_normalized`
  - `pdf_extract_failure_reason` (있을 때만)
  - `attachment_meta_rel_path`
  - `attachment_original_rel_path`

원칙:
- provenance/debug 값은 report/sidecar에 남기고 clean 본문에는 넣지 않는다.
- attachment-specific failure는 기존 telegram folder quality gate를 과도하게 깨지 않도록 먼저 diagnostics로 집계한다.

## 10) Incremental / 재현성 규칙

telegram file signature는 raw markdown만 보면 안 된다.
해당 채널의 signature에 attachment subtree digest를 함께 포함해야 한다.

권장 구성:
- telegram raw file: `size + mtime + path`
- plus attachment subtree digest for same channel:
  - `meta.json`
  - original PDF
  - extracted.txt
  - 각 file의 `size + mtime + relative path`

이유:
- raw telegram markdown이 그대로여도
- 새 PDF가 저장되거나
- `extracted.txt`가 뒤늦게 생기거나
- backfill로 추출 상태가 바뀌면
Stage2가 재처리를 해야 하기 때문이다.

## 11) Backward-compat policy

1. 기존 `text/telegram` clean/quarantine 결과는 canonical 경로를 유지한다.
2. Telegram PDF 승격은 **같은 telegram corpus의 inline 보강**으로만 추가한다.
3. image/legacy `ATTACH_TEXT`는 PDF 승격 입력으로 사용하지 않는다.
4. marker path가 없어도 current naming 규칙에 맞으면 fallback resolve를 허용한다.
5. fallback으로도 artifact를 확정할 수 없으면 추정하지 않고 diagnostics/quarantine 처리한다.
6. report schema는 깨지지 않도록 telegram PDF 통계는 **추가 field**로만 확장한다.

## 12) Validation plan

### Phase 0. 문서 확정
- 본 문서를 canonical design으로 승인
- `STAGE2_RULEBOOK_AND_REPRO.md`와 본 문서의 방향을 일치시킨다.

### Phase 1. Read-only audit
구현 전 먼저 dry audit를 권장한다.
- candidate message 수
- marker resolve 성공/실패 수
- fallback resolve 성공/실패 수
- `meta.kind=pdf` mismatch 수
- original missing 수
- image mis-promotion 0건 확인

### Phase 2. Parser + promotion implementation
- `stage02_onepass_refine_full.py`에 message block parser 추가
- sidecar resolver 추가
- local extractor chain 추가
- signature salt 확장

### Phase 3. Report extension
- `FULL_REFINE_REPORT_*.json`에 telegram PDF section 추가
- per-message diagnostics count와 reason count 확인

### Phase 4. Authoritative rebuild
- `--force-rebuild`로 Stage2 authoritative rebuild 수행
- clean telegram corpus에 PDF 본문이 inline 승격되는지 확인
- Stage3 입력 계약 변경 없이 downstream이 그대로 작동하는지 확인

## 12-1) Rerun policy
질문: PDF 승격 규칙이 추가되면 Stage2를 처음부터 다시 돌려야 하는가?

답:
1. **설계 문서만 바뀐 현재 시점**에는 rerun 필요 없음
2. **실제 구현이 들어간 뒤**에는 `stage02_onepass_refine_full.py --force-rebuild`가 사실상 필요하다
   - 이유: telegram 본문 자체가 달라지고
   - attachment subtree digest/signature 규칙도 바뀌며
   - 과거 clean telegram output은 PDF inline 승격이 없는 상태라 authoritative replacement가 아니기 때문이다
3. `stage02_qc_cleaning_full.py`는 signal QC writer이므로 **PDF-only 변경 검증만 놓고 보면 필수 rerun 대상은 아니다**
4. 다만 **Stage2 전체 authoritative 패키지/PASS 판정**을 다시 만들 때는 관례상 refine + QC 둘 다 다시 돌리는 편이 안전하다

권장 실행 순서:
```bash
python3 invest/stages/stage2/scripts/stage02_onepass_refine_full.py --force-rebuild
python3 invest/stages/stage2/scripts/stage02_qc_cleaning_full.py
```

한 줄 요약:
- **지금은 안 돌려도 됨**
- **구현 후에는 최소 refine 쪽은 full rebuild가 맞음**

## 13) 핵심 결정 요약

- Telegram PDF 승격 입력 단위는 **message + artifact pair**다.
- `meta.json`과 original PDF를 canonical source로 보고, `extracted.txt`는 optional seed로 본다.
- Stage1 marker path는 Stage2 upstream root 기준으로 rewrite 해석한다.
- image/legacy `ATTACH_TEXT`는 PDF 승격 입력에서 제외한다.
- canonical output은 새 `telegram_pdf` corpus가 아니라 **기존 `text/telegram` clean corpus에 inline 승격**이다.
- attachment 실패 사유는 report/diagnostics로 남기고, Stage3 계약은 그대로 유지한다.

## 14) Implementation status / authoritative proof (2026-03-08)

- 구현 위치: `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
- 구현 범위:
  - telegram message block parser + PDF sidecar join
  - marker path rewrite + limited fallback resolution
  - `stage1 extracted.txt -> stage2 local PDF extract(pypdf/pdfminer)` 우선순위
  - `[ATTACHED_PDF] <normalized_title>` inline merge
  - attachment subtree digest 포함 incremental signature
  - refine report의 telegram PDF 통계 확장
- authoritative rerun proof:
  - refine: `invest/stages/stage2/outputs/reports/qc/FULL_REFINE_REPORT_20260308_224737.json`
  - QC: `invest/stages/stage2/outputs/reports/QC_REPORT_20260308_225134.json`
- authoritative rerun 관측값:
  - `quality_gate.verdict=PASS`
  - `telegram_pdf_total=160`
  - `telegram_pdf_stage1_extract_reused=42`
  - `telegram_pdf_messages_promoted_by_pdf=42`
  - `telegram_pdf_extract_failed=0`
  - `telegram_pdf_orphan_artifacts=118`
