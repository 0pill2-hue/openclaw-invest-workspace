# CONTEXT HANDOFF FORMAT

역할: **컨텍스트 clean reset/cutover용 최소 인계 포맷**.

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`
관련 정책: `docs/operations/CONTEXT_POLICY.md`, `docs/operations/CONTEXT_LOAD_POLICY.md`

이 문서는 `runtime/context-handoff.md`의 **고정 포맷**을 정의한다.
문서 자체는 규격서이고, 실제 값은 런타임 파일에 채운다.

## 핵심 원칙
- 목적은 세션 내 장문 유지가 아니라 **짧은 외부 인계 + 필요 시 clean reset/cutover 대비**다.
- `runtime/context-handoff.md`는 **평소 프롬프트에 상시 적재하지 않는다**. reset/cutover 직후에만 읽는다.
- handoff는 **business context 보존용**이다. 운영 이벤트가 본작업 goal/next_action을 덮어쓰면 안 된다.
- clean reset/cutover는 **valid handoff가 있을 때만** 허용한다.

## 파일
- 규격서: `docs/operations/CONTEXT_HANDOFF_FORMAT.md`
- 런타임 실제값: `runtime/context-handoff.md`

## 필수 필드
`runtime/context-handoff.md`는 아래 키를 반드시 포함한다.

- `source_ticket_id`
- `source_directive_ids`
- `business_goal`
- `last_completed_step`
- `next_action`
- `latest_proof`
- `touched_paths`
- `required_action`
- `reset_guard`

권장 추가 필드:
- `handoff_version`
- `generated_at`
- `source`
- `task_status`
- `task_runtime_state`
- `handoff_reason`
- `trigger`
- `observed_total_tokens`
- `threshold`
- `required_paths_or_params`
- `notes`

## 의미 규칙
- `business_goal`: 원래 업무 목표. 예) Stage1 canonical 완료
- `last_completed_step`: 방금 끝낸 실제 업무 단계
- `next_action`: reset 직후 바로 이어갈 1개 액션
- `required_action`: 기본 `read_then_resume`, 임계치 대응 시 기본값은 `finish_current_step_then_prepare_handoff`이며 실제 reset이 꼭 필요할 때만 `clean_reset`
- `reset_guard`: 기본 `valid_handoff_required_before_clean_reset`
- `trigger`: `work_update` | `context_tokens_high` 등

## 생성 규칙
- `python3 scripts/context_policy.py snapshot ...`은 `runtime/current-task.md`와 함께 `runtime/context-handoff.md`도 갱신한다.
- watchdog이 **120k threshold 도달/초과**를 감지하면 `python3 scripts/context_policy.py handoff-from-current ...`로 handoff metadata를 다시 채워 다음 턴 재개/필요 시 reset에 대비한다.
- handoff는 짧게 유지한다. 장문 회고/일일 메모리를 복사하지 않는다.

## 검증 규칙
- `python3 scripts/context_policy.py handoff-validate --strict`
- strict 실패 조건:
  - 필수 필드 누락/placeholder
  - `source_ticket_id`와 `runtime/current-task.md`의 `ticket_id` 불일치

## reset/cutover 규칙
1. task/directive summary 확인
2. `runtime/current-task.md` 확인
3. `runtime/context-handoff.md` 검증 통과
4. 그 다음 clean reset/cutover
5. 새 세션에서 `runtime/context-handoff.md`를 먼저 읽고 `next_action`부터 재개

## 금지
- handoff 없이 빈 세션 reset
- 운영 메모가 `business_goal`/`next_action`을 덮어쓰기
- 본작업 진행이 가능한데도 handoff 준비만을 이유로 작업을 불필요하게 중단하기
