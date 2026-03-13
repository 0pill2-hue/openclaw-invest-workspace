# JB-20260312-CLEANUP-DEAD-WRAPPERS-OBSOLETE

- ticket: JB-20260312-CLEANUP-DEAD-WRAPPERS-OBSOLETE
- status: BLOCKED
- checked_at: 2026-03-12 07:28 KST

## Goal
외부 사용 여부 1회 확인 후 dead wrapper, obsolete script, legacy pycache를 제거한다.

## Blocked reason
- 주인님이 `JB-20260312-TELEGRAM-PDF-RECOVERY-FIX`를 현재 최우선으로 재지시했고, cleanup/research 계열은 대기시키라고 명시했다.
- dead wrapper/obsolete 제거는 PDF recovery/fetch fix와 직접 연관되지 않으므로 지금 실행하지 않는다.

## Prereq ticket
- `JB-20260312-TELEGRAM-PDF-RECOVERY-FIX`

## Unblock condition
- PDF recovery/fetch fix 완료 또는 주인님이 cleanup 병행을 다시 명시 승인

## Next action
- PDF recovery/fetch fix 완료 후 외부 사용 여부와 import/call/reference를 1회 확인해 제거 가능한 항목만 확정한다.
