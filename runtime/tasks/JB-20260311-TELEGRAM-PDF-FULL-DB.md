# JB-20260311-TELEGRAM-PDF-FULL-DB

- requested_at: 2026-03-11 09:45 KST
- updated_at: 미확인
- status: DONE
- owner: subagent

## what
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
  - PDF는 canonical meta만 처리하도록 정리해서 중복/구버전 meta가 `missing_original`/recovery 후보로 재집계되지 않게 수정.
  - `deleted_after_decompose` 상태를 도입/유지해서, 원본이 이미 삭제된 뒤 재실행해도 기존 `extract/manifest/decompose` 상태를 유지하도록 수정.
  - legacy full-log reconcile 단계가 삭제된 PDF 원본을 다시 복사하지 않도록 차단.
  - status JSON이 DB 기준(`pdf_documents / extract_ok / decompose_ok / pdf_pages`)을 authoritative count로 기록하도록 수정.
- `invest/stages/common/stage_raw_db.py`
  - canonical PDF merge 시 `deleted_after_decompose`가 있으면 과거 duplicate meta의 `original_path`가 다시 살아나지 않도록 수정.
- 실제 파일 정리
  - decomposed 완료 상태의 Telegram PDF originals 삭제.
  - 첫 삭제 후 legacy reconcile 버그로 재생성된 56개도 패치 후 재삭제.

## why
- 병목의 본질은 meta/extract가 아니라 **original 보존 정책**과 **원본 삭제 후 재실행 시 상태 퇴행**이었다.
- 실제 canonical 기준 확인 결과:
  - `pdf_documents=63735`
  - `extract_ok=59672`
  - `decompose_ok(manifest)=608`
  - 기존 실물 original 존재는 `608`뿐이었고, 이 608개는 전부 이미 decomposed 상태였다.
- 따라서 안전한 최고가치 조치는:
  1. decomposed 완료 original 전량 삭제
  2. 삭제 후에도 backfill/reindex가 이를 `missing_original` 실패나 recovery 대상으로 되돌리지 않게 코드/메타 정리
  3. 보고 기준을 DB 수치로 고정

## result
- 실제 삭제한 PDF original 파일 수:
  - `664`회 삭제
    - 고유 canonical originals `608`
    - legacy reconcile 버그로 재생성된 originals `56` 재삭제
- 새로 분해 후 삭제한 수: `0`
  - 남아 있던 originals 608개는 이미 모두 decomposed 상태였음.
- 최종 확인된 DB 기준 수치:
  - `pdf_documents = 63735`
  - `extract_ok = 59672`
  - `decompose_ok = 608`
  - `pdf_pages = 9632`
- 남은 Telegram PDF original 파일 수: `0`

## bounded_checks
1. canonical PDF 점검
   - existing originals `608`
   - `original_exists_but_not_decomposed = 0`
2. 삭제 직후 파일계 점검
   - `remaining_pdf_original_files = 0`
3. backfill 재실행 1회 후 DB/status 점검
   - status JSON에 DB authoritative fields 기록 확인
   - `pdf_db_documents_total=63735`
   - `pdf_db_extract_ok_total=59672`
   - `pdf_db_decomposed_total=608`
   - `pdf_db_pages_total=9632`
4. 재실행 중 발견된 회귀 버그 수정
   - legacy reconcile이 originals `56` 재복사하는 문제 확인 후 패치
   - 재삭제 후 재실행 결과 `legacy_original_copied = 0`
   - 최종 `remaining_pdf_original_files = 0` 재확인
5. 코드/DB 안전성 확인
   - patched canonical merge 결과 `merged_original_path_nonblank = 0`
   - `deleted_after_decompose_docs = 608`
   - DB `original_rel_path blank = 63735`

## proof
- 코드 수정:
  - `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
  - `invest/stages/common/stage_raw_db.py`
- 상태 산출물:
  - `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- DB:
  - `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- 파일계 확인 대상:
  - `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram`

## remaining_risk
- 본 턴 중 auto `stage01_sync_raw_to_db.py` 경합으로 일시적인 DB lock은 있었음.
- 다만 최종적으로 status/DB/file-system을 다시 확인했고, 원본 재복사 0 / 남은 original 0 / DB `original_rel_path blank = 63735`까지 확인했다.

## next
- 메인 보고는 원본 파일 수가 아니라 위 DB 수치(`pdf_documents / extract_ok / decompose_ok / pdf_pages`)를 기준으로만 요약하면 됨.
