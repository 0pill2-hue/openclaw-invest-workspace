# STAGE3_BRAIN_SCORING_DESIGN

status: CANONICAL-SUPPORTING
updated_at: 2026-03-13 KST
change_type: Strategy
scope: Stage3 adjudication / exception review design

## 1) 문서 목적
- 본 문서는 더 이상 Stage3 primary scoring 설계 문서가 아니다.
- primary scoring은 `external_review_primary` + `batch_scoring_mode`가 담당한다.
- 본 문서는 **adjudication / exception review**가 언제, 어떻게 개입하는지 규정한다.

---

## 2) adjudication이 필요한 경우
아래 중 하나면 adjudication 대상이다.
1. external response schema mismatch
2. expected item count / received item count mismatch
3. attachment 누락·훼손
4. item_type 충돌 또는 focus entity 충돌
5. duplicate merge 판단이 high-impact
6. `ambiguous` / `insufficient_context`가 비정상적으로 많음
7. operator가 package quality 또는 JSON integrity를 신뢰하지 못함

---

## 3) 역할 분리
### external primary lane
- mixed analysis item의 canonical qualitative scoring writer

### local support lane
- prefilter / routing / dedup / grouping / priority / sanity-check support

### adjudication lane
- exception triage
- response repair policy 결정
- re-batch / re-review 여부 판정
- high-impact conflict 정리

adjudication lane은 기본 lane이 아니라 **예외 처리 lane**이다.

---

## 4) adjudication input set
최소 입력:
- original batch manifest
- item attachments
- external raw JSON response
- schema validation error 또는 integrity note
- local support dedup / grouping note

선택 입력:
- operator short note
- prior batch lineage
- duplicate ledger snapshot

---

## 5) adjudication allowed actions
허용:
- item_type를 `mixed` / `unknown`으로 되돌리는 보수적 수정
- duplicate를 `merge_candidate`로 승격
- attachment mismatch를 `insufficient_context`로 확정
- re-batch 필요 판정
- human review 필요 flag 부여
- malformed JSON repair 요청 또는 재회수

금지:
- entire batch를 local-only score로 대체
- chatter/opinion/no-symbol item의 silent delete
- stock-only schema로 강제 재구성
- external primary 결과를 설명 없이 wholesale overwrite

---

## 6) adjudication decision priority
1. attachment integrity
2. item lineage / identity integrity
3. item_type correctness
4. evidence traceability
5. duplicate / merge correctness
6. final_result_label refinement
7. operator convenience

---

## 7) outputs
adjudication 결과는 아래 중 하나여야 한다.
- `accept_as_is`
- `accept_with_relabel`
- `accept_with_merge_candidate`
- `rerun_batch_required`
- `human_review_required`
- `reject_due_to_package_failure`

각 판정은 short reason을 남긴다.

---

## 8) practical rule
정상 배치는 adjudication 없이 바로 canonical normalized JSON로 간다.
adjudication은 예외 처리에만 쓰며, Stage3의 primary engine으로 승격하지 않는다.
