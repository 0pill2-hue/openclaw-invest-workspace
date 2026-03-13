# JB-20260312-TELEGRAM-PDF-RECOVERY-FIX

- ticket: JB-20260312-TELEGRAM-PDF-RECOVERY-FIX
- status: BLOCKED
- checked_at: 2026-03-13 07:19 KST

## Goal
Telegram PDF/attachment recovery를 다시 움직여 실제 recovery/fetch 경로가 자동수집 런타임에서 막히지 않도록 복구한다.

## What was verified
- 기존 실질 blocker는 extractor 자체가 아니라 **env bootstrap gate**였다.
  - 이전 로직은 `_bootstrap_stage1_env()`가 `os.environ.setdefault(...)`만 사용해서, launchd/cron/process env에 `TELEGRAM_API_ID=""`, `TELEGRAM_API_HASH=""` 같은 빈 placeholder가 이미 있으면 stage1 env 파일의 실제 값이 로드되지 않았다.
  - 새 로직은 quote 제거 + empty-like(`""`, `0`, `none`, `null`) 판정을 추가해, 빈 placeholder가 있을 때는 env 파일 값으로 덮어쓴다.
- focused regression proof를 새로 남겼다.
  - `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_gate_regression.json`
  - 여기서 `legacy_setdefault_kept_empty_api_id/hash=true` 와 `fixed_bootstrap_loaded_api_id/hash=true` 로 root cause와 fix를 같이 재현했다.
- 수정 스크립트는 문법 검증을 통과했다.
  - `python3 -m py_compile invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- 샘플 recovery provenance는 여전히 meta에 남아 있다.
  - sample: `캬오의_공부방_Kyaooo / msg_30087`
  - `original_store_origin = telegram_redownload`
  - `original_recovered_at = 2026-03-12T05:47:15.011779+00:00`
- 단, 샘플의 **현재 최신 상태**는 `deleted_after_decompose`다.
  - 즉 recovery 직후 잠시 생긴 original PDF는 이후 decompose pass에서 삭제되었고,
  - 대신 `extract_path`와 `pdf_manifest_path`는 현재도 존재한다.
  - 따라서 이 샘플의 최신 증빙은 `original PDF 실파일`이 아니라 `meta + extract + manifest`를 봐야 맞다.

## Runtime check (2026-03-13 07:19 KST)
- 이 서브세션의 실제 process env 시작 상태에서는 `TELEGRAM_API_ID/HASH`가 둘 다 비어 있었다.
- stage1 bootstrap fallback 경로를 점검한 결과:
  - `invest/stages/stage1/.env` 는 없음
  - `~/.config/invest/invest_autocollect.env` 는 존재하지만 `TELEGRAM_API_ID=` / `TELEGRAM_API_HASH=` 가 **키만 있고 값은 비어 있음**
- 따라서 bootstrap 이후에도 `TELEGRAM_API_ID/HASH`는 여전히 비어 있었고, 이번 턴에서는 bounded live batch를 실행할 수 없었다.
- 반면 `invest/stages/stage1/scripts/jobis_mtproto_session.session` 은 존재했다.
  - 즉 현재 최소 blocker는 **session 부재가 아니라 credential source 자체가 empty** 인 상태다.

## Code path changed
- `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
  - env bootstrap이 empty placeholder를 실제 값으로 대체하도록 수정
  - recovery auto gate / disabled reason / channel/date filter helper 추가
  - bounded recovery selection 로직 정리

## Conclusion so far
- 최고 신뢰도의 인스코프 fix는 **empty placeholder env가 recovery credential을 가려버리던 bootstrap 버그 수정**이다.
- fix 자체와 기존 recovery provenance는 proof로 남아 있다.
- 하지만 **현재 운영 fallback env 파일 자체가 비어 있으므로** live recovery/fetch 검증은 여기서 더 진행할 수 없다.
- 따라서 현재 상태는 코드 이슈가 아니라 **운영 credential 재주입 대기**다.

## Next action
- `~/.config/invest/invest_autocollect.env` 또는 stage1 `.env` 에 **non-empty** `TELEGRAM_API_ID`, `TELEGRAM_API_HASH` 를 재주입한다.
- 재주입 직후 아래 bounded validation 1회를 다시 실행한다.
  - `TELEGRAM_ATTACH_RECOVER_MISSING_ORIGINALS=1`
  - `TELEGRAM_ATTACH_RECOVER_LIMIT=1`
  - 가능하면 `TELEGRAM_ATTACH_RECOVER_CHANNEL_SLUGS=<slug>` + `TELEGRAM_ATTACH_RECOVER_DATE_FROM/TO=<yyyymmdd>` 로 1건 범위 고정
- 그 실행 후 `telegram_recovery_attempted / telegram_recovery_ok / extracted_ok` delta를 status로 다시 확인한다.

## Proof
- regression proof: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_gate_regression.json`
- runtime env diag: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_runtime_diag_20260313T0719KST.json`
- sample meta: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/캬오의_공부방_Kyaooo/bucket_007/msg_30087__meta.json`
- sample extract: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/캬오의_공부방_Kyaooo/bucket_007/msg_30087__extracted.txt`
- sample manifest: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/캬오의_공부방_Kyaooo/bucket_007/msg_30087__pdf_manifest.json`
- runtime status target: `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- script: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
