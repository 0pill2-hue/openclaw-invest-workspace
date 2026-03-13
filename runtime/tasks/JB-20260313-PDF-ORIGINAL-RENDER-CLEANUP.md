# JB-20260313-PDF-ORIGINAL-RENDER-CLEANUP

- ticket: JB-20260313-PDF-ORIGINAL-RENDER-CLEANUP
- status: DONE
- checked_at: 2026-03-13 16:20 KST

## Goal
PDF 분해 후 남은 페이지 캡처(render)와 원본 PDF 저장물 상태를 정리한다.

## Landed
1) 페이지 캡처(render) 대량 정리
- 조건: `pdf_pages`에서 `text_rel_path`가 존재하는 페이지의 `render_rel_path`만 삭제 (텍스트 추출 완료본 우선)
- 삭제 수: `155,407` files
- 회수 용량: `56,249,614,850 bytes` (~`52.387 GiB`)
- 동기화: `pdf_pages.render_rel_path` 비움, 관련 `raw_artifacts` 항목 삭제, 해당 문서 manifest/meta의 render 카운트 갱신

2) 원본 PDF 잔여 제거
- 남아있던 `__original__*.pdf` 2개(총 4,325,376 bytes) 삭제
- 함께 발견된 빈 meta 파일 1개 삭제 (`msg_121041__meta.json`, empty)
- 결과: `remaining_original_pdf_count = 0`

## Why
- 주인님 지시: "페이지 캡쳐파일 삭제", "원본 저장됐으면 분해/DB화 후 삭제"
- 실제 상태 확인 결과, 페이지 캡처가 저장공간 대부분을 차지했고(약 52.4GiB), 원본 PDF는 2개만 잔존한 이상치였다.

## Remaining
- `render_only` 페이지(텍스트 미추출인데 render만 있는 페이지) 4,976개는 보존(안전삭제 범위 밖)
- 이 집합은 추후 재분해/재추출 후 삭제 대상

## Proof
- `df -h .` (삭제 전후)
- `invest/stages/stage1/outputs/db/stage1_raw_archive.sqlite3` (`pdf_pages`, `raw_artifacts`)
- 삭제 대상 경로:
  - `.../msg_121041__original__...pdf`
  - `.../msg_649__original__...pdf`
  - `.../msg_121041__meta.json`
