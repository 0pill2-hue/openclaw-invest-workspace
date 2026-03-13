# JB-20260312-CLEANUP-STAGE2-TELEGRAM-PDF-DOC-CANON

- ticket: JB-20260312-CLEANUP-STAGE2-TELEGRAM-PDF-DOC-CANON
- status: DONE
- checked_at: 2026-03-12 KST
- scope: Stage2 Telegram PDF path/recovery docs only
- guardrail: Telegram PDF recovery code 자체는 수정하지 않음

## Summary
Stage2 Telegram PDF path/recovery 문서를 **기존 canonical 2문서 + README index** 기준으로 정리했다.
핵심 정리는 아래 2가지다.

1. **현재 canonical path를 bucketed flat artifact로 통일**
   - `attachments/telegram/<channel_slug>/bucket_<nn>/msg_<id>__*`
   - legacy `msg_<id>/meta.json` 디렉터리는 current path가 아니라 **fallback-only historical shadow** 로 강등

2. **Stage2에서 말하는 recovery 범위를 명확히 분리**
   - Stage2 recovery = marker/path rewrite + local fallback resolve + local extract fallback
   - Stage1 recovery = missing original 재다운로드/credential/session 기반 upstream reacquire

즉, Stage2 문서가 더 이상 Stage1 upstream recovery 이슈와 섞여 보이지 않게 canonical boundary를 고정했다.

## Canonical structure after cleanup
### Canonical
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`

### Historical / non-canonical reference only
- `runtime/tasks/JB-20260311-TELEGRAM-PDF-FULL-DB.md`
- `runtime/tasks/JB-20260311-TELEGRAM-PDF-NAVER-RECOVERY.md`
- `runtime/tasks/JB-20260311-TELEGRAM-PDF-PAGE-DECOMPOSE-RERUN.md`
- `runtime/tasks/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX.md`
- `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`

위 runtime/tasks 문서들은 운영 로그/증빙/조사 기록이며, Stage2 path/recovery 계약 SSOT가 아님을 README에 명시했다.

## Touched paths
- `docs/invest/stage2/README.md`
- `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`
- `runtime/tasks/JB-20260312-CLEANUP-STAGE2-TELEGRAM-PDF-DOC-CANON.md`

## What changed
### 1) `docs/invest/stage2/README.md`
- canonical 문서 역할 설명에 Telegram PDF path resolution / recovery boundary를 추가
- runtime/tasks Telegram PDF 문서들을 historical/non-canonical reference로 명시

### 2) `docs/invest/stage2/STAGE2_RULEBOOK_AND_REPRO.md`
- raw qualitative Telegram attachment 입력 경로를 **bucketed flat canonical path** 기준으로 수정
- legacy `msg_<id>/meta.json`는 fallback-only non-canonical이라고 명시
- Telegram PDF inline promotion 계약에 path resolution order를
  - marker
  - bucketed flat canonical fallback
  - legacy dir fallback
  순으로 고정
- Stage2 recovery boundary(로컬 resolve/extract only)와 Stage1 upstream recovery 분리를 명시

### 3) `docs/invest/stage2/STAGE2_PDF_REFINEMENT_DESIGN.md`
- Stage1 저장 위치를 bucketed flat artifact 기준으로 수정
- current Stage2 처리 상태를 `marker → bucketed flat canonical fallback → legacy dir fallback` 순서로 정렬
- fallback discovery를 현재 코드 계약에 맞게 bucketed flat 우선으로 재서술
- recovery boundary 전용 subsection을 추가해 Stage2와 Stage1 recovery 의미를 분리

## Proof
### Authoritative evidence used
1. Stage1 canonical docs already declare bucketed flat artifact as SSOT
   - `docs/invest/stage1/RUNBOOK.md`
   - `docs/invest/stage1/STAGE1_RULEBOOK_AND_REPRO.md`
   - `docs/invest/stage1/stage01_data_collection.md`

2. Stage2 implementation already matches bucketed flat canonical + legacy fallback
   - `invest/stages/stage2/scripts/stage02_onepass_refine_full.py`
   - helper names observed: `_telegram_attach_bucket_name`, `_telegram_attach_bucket_dir`, `_telegram_attach_meta_path`, `_telegram_attach_legacy_dir`
   - resolver order observed: marker path 우선 후 bucket meta probe, 마지막에 legacy dir probe

3. Audit seed that identified the doc mismatch
   - `runtime/tasks/JB-20260312-LEGACY-CLEANUP-AUDIT.md`

### Consolidation judgment
- duplicated/obsolete current wording was in Stage2 docs themselves (legacy `msg_<id>/` 경로를 current처럼 서술)
- runtime/tasks Telegram PDF reports were kept as **historical evidence**, not deleted, because they still contain useful chronology/proof
- no Stage2 code path was changed

## Next step
메인에서 본 티켓을 검토할 때는 아래만 보면 된다.
1. Stage2 docs는 이제 bucketed flat path를 canonical로 본다.
2. legacy `msg_<id>/`는 fallback-only historical path다.
3. Stage2 문서의 recovery는 local consume/resolve 의미이고, Telegram re-download recovery는 여전히 Stage1 티켓(`JB-20260312-TELEGRAM-PDF-RECOVERY-FIX`) 범위다.
