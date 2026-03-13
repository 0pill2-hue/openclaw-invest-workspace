# JB-20260313-STAGE3-EXTERNAL-PARTIAL-COMPARE

- ticket: JB-20260313-STAGE3-EXTERNAL-PARTIAL-COMPARE
- status: IN_PROGRESS
- checked_at: 2026-03-13 13:22 KST

## Goal
batch_04a를 제외한 external 9/10 결과만으로 local/main/external 부분 비교를 먼저 만든다.

## Scope
- include: completed external batches except 04a
- exclude: batch_04a (send_not_confirmed)
- outputs: joined comparison artifact, concise summary memo, comparability limits

## Next action
- subagent가 완료 batch(01a,01b,02a,02b,03a,03b,04b,05a,05b) 기준으로 external normalized outputs를 집계
- local/main과 join 가능한 표를 만들고, coverage/score/status/time 한계까지 정리
- proof 경로를 이 티켓에 남긴다

## 2026-03-13 13:22-13:32 KST | partial compare prepared
- completed external batches fixed as: batch_01a, batch_01b, batch_02a, batch_02b, batch_03a, batch_03b, batch_04b, batch_05a, batch_05b
- excluded: batch_04a / S061-S075 (`send_not_confirmed`, detached watcher completion proof 미확인)
- external partial coverage: 85/100 samples
- external status counts: scored 48 / ambiguous 11 / insufficient_context 26
- local exact record bridge: 85/85, but local nonzero eval rows are 71/85 (`__NOSYMBOL__` 등으로 14건은 count=0)
- main usable rows in this bounded partial compare: 26/85
  - rerun-aligned window: S036-S060 (25 samples, nonzero tri-lane comparable 22)
  - singleton direct carryover from sample100 actual: S012
- remaining main rows are `미확인` instead of guessed
- proof:
  - `runtime/tasks/proofs/JB-20260313-STAGE3-EXTERNAL-PARTIAL-COMPARE/partial_compare_rows.csv`
  - `runtime/tasks/proofs/JB-20260313-STAGE3-EXTERNAL-PARTIAL-COMPARE/partial_compare_summary.json`
  - `runtime/tasks/proofs/JB-20260313-STAGE3-EXTERNAL-PARTIAL-COMPARE/memo.md`

## Auto updates

### 2026-03-13 13:22:23 KST | owner_partial_compare
- summary: Started 04a-excluded Stage3 partial compare via subagent run 95a61b7d-c7c9-4611-870f-a8be30c5e74d
- phase: delegated_to_subagent
- detail: child_session=agent:main:subagent:2e1ce118-c4fe-47bd-95ee-cd15eea231e9 include=9/10 external batches exclude=batch_04a
