# JB-20260312-OPS-DEEP-WEB-REVIEW-EX-INVEST

- ticket: JB-20260312-OPS-DEEP-WEB-REVIEW-EX-INVEST
- status: BLOCKED
- checked_at: 2026-03-12 06:22 KST

## Goal
invest 제외 운영프로그램 전체를 GitHub commit 기준으로 deep web-review 받아 구조/운영/설계 개선점을 찾는다.

## Prerequisite check
- web-review는 반드시 commit/push 기준선이 먼저 고정되어야 한다.
- 현재 운영프로그램 전체 scope는 아직 review 전용 clean baseline으로 분리되지 않았다.
- runtime/current task churn, watchdog/generated/runtime artifacts, 진행 중 변경들이 섞여 있어 지금 commit을 잡으면 운영프로그램 review baseline이 오염될 가능성이 높다.

## Blocked reason
- invest 제외 운영프로그램 review scope를 clean commit baseline으로 분리/고정한 뒤에만 의미 있는 deep web-review가 가능하다.

## Next action
1. invest 제외 운영프로그램 review scope 확정
2. runtime/generated noise 제외한 clean commit/push baseline 고정
3. 그 다음 web-review prompt 작성 및 deep review 실행
