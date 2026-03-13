# JB-20260312-TELEGRAM-PDF-RECOVERY-FIX

- ticket: JB-20260312-TELEGRAM-PDF-RECOVERY-FIX
- status: BLOCKED
- checked_at: 2026-03-13 13:20 KST

## Goal
Telegram PDF/attachment recovery를 다시 움직여 실제 recovery/fetch 경로가 자동수집 런타임에서 막히지 않도록 복구한다.

## What was verified earlier
- 기존 실질 blocker는 extractor 자체가 아니라 **env bootstrap gate**였다.
  - 이전 로직은 `_bootstrap_stage1_env()`가 `os.environ.setdefault(...)`만 사용해서, launchd/cron/process env에 `TELEGRAM_API_ID=""`, `TELEGRAM_API_HASH=""` 같은 빈 placeholder가 이미 있으면 stage1 env 파일의 실제 값이 로드되지 않았다.
  - 새 로직은 quote 제거 + empty-like(`""`, `0`, `none`, `null`) 판정을 추가해, 빈 placeholder가 있을 때는 env 파일 값으로 덮어쓴다.
- focused regression proof를 남겼다.
  - `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_gate_regression.json`
  - 여기서 `legacy_setdefault_kept_empty_api_id/hash=true` 와 `fixed_bootstrap_loaded_api_id/hash=true` 로 root cause와 fix를 같이 재현했다.
- 수정 스크립트는 문법 검증을 통과했다.
  - `python3 -m py_compile invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`
- 샘플 recovery provenance는 meta에 남아 있다.
  - sample: `캬오의_공부방_Kyaooo / msg_30087`
  - `original_store_origin = telegram_redownload`
  - `original_recovered_at = 2026-03-12T05:47:15.011779+00:00`
- 샘플의 최신 상태는 `deleted_after_decompose`다.
  - recovery 직후 original PDF는 이후 decompose pass에서 삭제되었고,
  - 대신 `extract_path`와 `pdf_manifest_path`는 남아 있다.

## Earlier runtime check (2026-03-13 07:19 KST)
- 이 서브세션의 실제 process env 시작 상태에서는 `TELEGRAM_API_ID/HASH`가 둘 다 비어 있었다.
- stage1 bootstrap fallback 경로를 점검한 결과:
  - `invest/stages/stage1/.env` 는 없음
  - `~/.config/invest/invest_autocollect.env` 는 존재하지만 `TELEGRAM_API_ID=` / `TELEGRAM_API_HASH=` 가 **키만 있고 값은 비어 있음**
- 따라서 bootstrap 이후에도 `TELEGRAM_API_ID/HASH`는 여전히 비어 있었고, 그 시점 이 세션에서는 bounded live batch를 실행할 수 없었다.
- `invest/stages/stage1/scripts/jobis_mtproto_session.session` 은 존재했다.
  - 즉 당시 최소 blocker는 session 부재가 아니라 credential source 자체가 empty인 상태였다.

## Latest post-run verification (2026-03-13 12:58 KST)
- 최신 runtime status 파일은 **오늘 recovery run이 실제로 끝났음**을 보여준다.
  - `saved_at = 2026-03-13T02:54:42.316836+00:00`
  - `finished_at = 2026-03-13T03:12:51.139887+00:00`
  - `status = WARN`
- 즉 오전 07:19 KST의 credential-empty 진단은 **최신 완료 런 기준 최종 상태가 아니며**, 이후 다른 런 컨텍스트에서는 recovery가 실제로 수행되었다.
- 최신 run에서 live recovery/fetch는 부분적으로는 동작했다.
  - `telegram_recovery_attempted = 24`
  - `telegram_recovery_ok = 7`
  - `extracted_ok = 7`
- 하지만 전체 건강 상태는 **정상(healthy) 아님 / 여전히 blocked** 이다.
  - `telegram_recovery_candidates_selected = 48029`
  - `telegram_recovery_failed = 48045`
  - 주요 reason:
    - `telegram_recovery_entity_unresolved = 13`
    - `telegram_recovery_file_too_large = 3`
    - `telegram_recovery_runtime_error:OSError = 1`
    - `missing_original = 48023`
    - `pdf_db_index_error:OperationalError = 1`
- dataset-wide current counters (DB/status basis):
  - `total pdf = 63735`
  - `original-present = 0`
  - `extract-ok = 15513`
  - `missing-original = 48101`
- live filesystem basis에서는 physical original PDF가 **1개** 남아 있었지만, 이는 empty meta와 짝인 orphan 상태였다.
  - original: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/선진짱_주식공부방_sunstudy1004/bucket_081/msg_121041__original__게임_미워도_다시_한번_v2_펄어비스_넷마블_데브시스터즈_조이시티_GameEntertainme_20260310.pdf`
  - empty meta: `invest/stages/stage1/outputs/raw/qualitative/attachments/telegram/선진짱_주식공부방_sunstudy1004/bucket_081/msg_121041__meta.json`
- 현재 시점에 `stage01_telegram_attachment_extract_backfill.py` 실행 중 프로세스는 보이지 않았다.
  - 즉 이 티켓은 **background ongoing** 이 아니라 **completed-with-warning / blocked** 판정이 맞다.

## Delta vs prior proof
- prior proof (`2026-03-13 07:19 KST`) 는 `blocked_missing_telegram_credentials`, `live_batch_executed=false` 였다.
- latest run proof에서는:
  - `live_batch_executed=true` 로 볼 수 있음 (`attempted=24`)
  - `telegram_recovery_ok +7`
  - `extracted_ok(in-run) +7`
- 단, prior proof에 dataset-wide global counters가 없어서 `total pdf / extract-ok / missing-original`의 정량 delta는 **미확인** 이다.

## Improvement pass (2026-03-13 13:20 KST)
- 오늘 observed failure에 대해 **로컬에서 안전하게 검증 가능한 고레버리지 수정 3개**를 반영했다.
  1. `telegram_recovery_runtime_error:OSError`
     - 기존 로직은 개별 candidate 처리 중 `download_media()/move()` 계열 `OSError` 가 나면 async 루프 밖으로 새어 나가고,
       바깥 `_recover_missing_originals()` 가 `len(selected_records)` 전체를 실패로 더해 `telegram_recovery_failed > telegram_recovery_candidates_selected` 같은 왜곡을 만들 수 있었다.
     - 새 로직은 **record 단위로 예외를 잡고 동일 reason key로 누적 후 다음 candidate로 계속 진행**한다.
     - 바깥 batch-level 예외 집계도 **남은 unattempted 개수만 실패로 반영**하도록 보정했다.
  2. `telegram_recovery_entity_unresolved`
     - 기존 로직은 `channel_slug` exact match + numeric tail만 봐서, 채널 title이 바뀌었지만 username은 유지된 slug(`여의도스토리_Ver20_YeouidoStory2` 류)에서 alias miss가 날 수 있었다.
     - 새 로직은 `channel_slug` 를 underscore suffix 후보들로 단계적으로 축소해 `username`/tail alias도 조회한다.
  3. original-present / missing-original accounting correctness
     - 기존 status payload는 live DB reindex가 `OperationalError` 로 실패하면 **stale DB totals** 를 fallback으로 사용해 현재 raw/meta 기준과 어긋날 수 있었다.
     - 새 로직은 canonical PDF meta 기준의 accounting(`original_present`, `deleted_after_decompose`, `missing_original`, `manifest_present`, `orphan_original`)을 별도 산출해 status에 싣고,
       DB reindex 실패 시 주요 totals는 **canonical meta fallback** 으로 내보낸다.
- `pdf_db_index_error:OperationalError` 의 **정확한 live root cause는 이번 턴에서 미확인** 이다.
  - 다만 같은 raw tree를 **temp DB** 로 다시 인덱싱한 bounded verification은 성공했다.
  - 따라서 오늘 status의 DB 오류는 최소한 `raw/meta 자체가 전부 깨져서 항상 재현되는 하드 오류` 라고 단정할 수는 없다.

## Conclusion
- **credential/bootstrap gate 자체는 최신 런 기준으로는 더 이상 최상위 blocker가 아니다.** 오늘 실제 recovery fetch가 24건 시도되고 7건 성공했다.
- 이번 improvement pass로
  - per-record `OSError` 가 전체 batch를 중단시키는 구조,
  - renamed channel slug의 username suffix miss,
  - DB reindex 실패 시 stale totals로 인해 current accounting이 흐려지는 구조
  를 각각 코드 차원에서 줄였다.
- 그러나 **live run 재검증은 아직 하지 않았으므로, 실제 production 효과는 미확인** 이다.
- 따라서 이 티켓의 현재 상태는 **code improvement applied + local bounded verification passed + live health 미확인으로 여전히 BLOCKED** 이다.

## Next action
- 다음 bounded/live run에서 아래를 재확인해야 한다.
  - `telegram_recovery_runtime_error:OSError` 가 batch abort 없이 per-record reason으로만 남는지
  - `telegram_recovery_entity_unresolved` 가 실제로 감소하는지
  - `pdf_accounting_basis`, `pdf_original_present_total`, `pdf_missing_original_total`, `pdf_orphan_original_total` 이 status에 기대대로 반영되는지
- live DB의 `OperationalError` 정확한 원인은 별도 분리 조사 필요 (`미확인`).
- empty meta + orphan original 1건은 인덱싱/정합성 관점의 별도 정리 후보다.

## Proof
- latest post-run verification: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_postrun_verification_20260313T1258KST.json`
- improvement pass proof: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_improvement_pass_20260313T1320KST.json`
- regression proof: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_gate_regression.json`
- earlier runtime env diag: `runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_env_runtime_diag_20260313T0719KST.json`
- runtime status target: `invest/stages/stage1/outputs/runtime/telegram_attachment_extract_backfill_status.json`
- script: `invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py`

## Auto updates

### 2026-03-13 13:08:29 KST | owner_improve
- summary: Started PDF recovery improvement pass via subagent run 773a7a73-f2f7-4e28-a185-a13fc1b7d7f2
- phase: delegated_to_subagent
- detail: focus=OSError/entity_unresolved/original-present accounting child_session=agent:main:subagent:5c7590ec-cafb-46b2-81e8-af1202cd8139

### 2026-03-13 13:20:51 KST | owner_improve
- summary: Applied bounded code improvements for Telegram PDF recovery failure handling and accounting fallback
- phase: blocked_waiting_next_live_verification
- detail: script_updated=invest/stages/stage1/scripts/stage01_telegram_attachment_extract_backfill.py proof=runtime/tasks/proofs/JB-20260312-TELEGRAM-PDF-RECOVERY-FIX_improvement_pass_20260313T1320KST.json live_effect=미확인
