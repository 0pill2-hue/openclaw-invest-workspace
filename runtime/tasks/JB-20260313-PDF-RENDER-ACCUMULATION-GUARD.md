# JB-20260313-PDF-RENDER-ACCUMULATION-GUARD

- ticket: JB-20260313-PDF-RENDER-ACCUMULATION-GUARD
- status: IN_PROGRESS
- checked_at: 2026-03-13 16:41 KST

## Goal
PDF page render가 다시 쌓이지 않도록 기본 보존 정책을 최근 1개월 hot-window 중심으로 바꾸고, 이미 쌓인 old render 적체도 정리한다.

## Landed
1. `invest/stages/common/stage_pdf_artifacts.py`
   - hot window 밖 문서는 manifest 재사용 시 기존 `render_rel_path`를 prune 하도록 변경
   - 신규 artifact 생성 시 hot window 밖 문서는 render 파일을 즉시 삭제하고 manifest에는 빈 `render_rel_path`만 남기도록 변경
   - old/outside-hot-window 문서는 `render_status=disabled`, `render_reason=outside_hot_window`로 기록
2. 기존 적체 정리
   - `message_date < now-30d` + `pdf_pages.render_rel_path != ''` 대상 old render를 일괄 정리
   - 결과: `removed_old_render_files=3397`, `removed_old_render_gib=1.518`, `docs_touched=1007`, `remaining_old_render_refs=0`

## Remaining
- render 외에 old raw text / other PDF raw artifacts(최근 1개월 초과분)까지 어디까지 삭제할지 policy를 코드와 cleanup run에 확정해야 한다.
- `JB-20260313-PDF-RAW-RETENTION-POLICY`에서 recent 1개월 보존 기준으로 raw/text/bundle 정리 범위를 이어서 마무리한다.

## Proof
- `invest/stages/common/stage_pdf_artifacts.py`
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3`
- runtime cleanup result: old render refs older than 30d => 0 remaining
