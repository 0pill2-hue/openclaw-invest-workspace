# MAIN BRAIN GUARD

프로그램 총람: `docs/operations/PROGRAMS.md`

상위 인덱스: `docs/operations/OPERATIONS_BOOK.md`

역할: **메인 운영 경로 전체를 감시하고, 가능한 범위는 자동 복구하며, 불가한 범위는 즉시 경고하는 상위 가드**.

`local_brain_guard`는 이 문서가 정의하는 메인브레인가드의 **하위 복구 컴포넌트**이지만, 판정상으로는 **별도 local advisory**로 분리한다.
메인브레인가드는 로컬뇌 상태만이 아니라 **Gateway / 메인 세션 / 응답 채널 / 작업 재기동 경로**까지 포함한다.

## 1. 감시 대상
1. **Gateway 생존성**
   - `openclaw status`에서 Gateway reachable / service running 이어야 한다.
2. **메인뇌 응답성**
   - 메인 세션이 정상 응답 가능해야 한다.
   - 로컬뇌 fallback 경로가 필요한 경우 `local_brain_guard` 복구가 동작해야 한다.
3. **응답 채널 생존성**
   - Telegram 등 활성 채널이 configured/OK 상태여야 한다.
   - 응답 채널 장애는 "모델은 살아 있으나 사용자 응답이 끊긴 상태"로 별도 취급한다.
4. **작업 재기동 경로**
   - `tasks watchdog` + `auto-dispatch`가 살아 있어야 하며, 남은 작업이 있을 때 다음 작업을 다시 태울 수 있어야 한다.
5. **현재 작업 컨텍스트 복구성**
   - `runtime/current-task.md`가 placeholder가 아니어야 하며, TASKS/DIRECTIVES DB summary로 현재 상태를 복원할 수 있어야 한다.

## 2. 하위 가드와 역할 분리
### `local_brain_guard`
- 범위: 로컬 llama / Gateway 상태 점검과 복구
- 복구: llama 재시작 → 2초 대기 → 재점검
- 제약: 메인 세션(`agent:main:main`) 엔트리/파일을 직접 reset하지 않는다.
- 성격: **컴포넌트 복구 가드**

### 메인 heartbeat
- 범위: 운영 상태 요약/경고 전달
- 성격: **보고/감시 가드**

### `tasks watchdog`
- 범위: stale `IN_PROGRESS`, waiting phase의 `resume_due` 초과 task 감지/전환 + context threshold의 메인 reset 트리거 전달
- 현재 동작: **nonterminal waiting phase가 아닌** stale task만 `BLOCKED`로 되돌리고, delegated/awaiting/long-running wait phase는 age만으로 닫지 않는다. context threshold에서는 maintenance task와 메인 wake event를 통해 메인이 현재 step 완료 후 reset을 실행하게 한다.
- 성격: **ledger 정합성 + 메인 reset 트리거 가드**

### `auto-dispatch`
- 범위: assign-next → 메인 오케스트레이터 호출 → 티켓 close 확인
- 성격: **작업 재기동 가드**

## 3. 실패 기준
아래 중 하나면 메인브레인가드 FAIL로 본다.
- Gateway unreachable / service not running
- 메인 운영 경로 자체의 상태 점검 실패(`openclaw status`, channel, watchdog, auto-dispatch, current-task 복구성)
- Telegram 채널 configured 상태가 아니거나 상태 점검 실패
- `tasks watchdog`/`auto-dispatch` launchd job 미적재 또는 반복 오류
- 단, `tasks watchdog`은 **주인님 명시 지시로 pause directive가 활성화되고 실제 launchctl disabled 상태가 current-task 증빙으로 확인되는 경우** 예외로 두며, 이때는 FAIL로 보지 않는다.
- 남은 assignable task가 있는데도 `auto-dispatch`가 재기동하지 못함
- `runtime/current-task.md`가 placeholder라 현재 작업 복구 불가
- `local_brain_guard` FAIL은 별도 advisory로 기록하며, 단독으로는 메인브레인가드 FAIL 조건이 아니다.

## 4. 복구 우선순위
1. **Gateway/로컬뇌 계층**
   - `local_brain_guard`가 우선 복구 시도
2. **작업 계층**
   - stale task는 `scripts/watchdog/watchdog_recover.py`가 정리
   - 남은 작업은 `dispatch_tick.py`가 재배정/재기동
3. **채널 계층**
   - 자동 복구가 불명확한 경우 즉시 경고하고 수동 조치로 승격
4. **컨텍스트 계층**
   - `python3 scripts/tasks/db.py summary --top 5 --recent 5`
   - `python3 scripts/directives/db.py summary --top 5 --recent 5`
   - `python3 scripts/context_policy.py resume-check --strict`

## 5. 현재 확인된 운영 포인트 (2026-03-07)
- `local_brain_guard` launchd는 존재하며 로컬뇌/Gateway 복구를 담당한다.
- `tasks watchdog` launchd는 600초 간격으로 ledger 정합성만 본다.
- `auto-dispatch` launchd는 300초 간격으로 task 재기동을 담당한다.
- `tasks watchdog`의 실제 실행 로그는 `runtime/tasks/watchdog.launchd.log`로 미러링해 점검한다. 현재 로드된 launchd plist의 stdout/stderr는 레거시 경로(`invest/stages/stage1/outputs/logs/runtime/launchd_stage01_watchdog.log`)를 계속 쓸 수 있으므로, 재로드 전까지는 두 경로가 공존할 수 있다.
- `auto-dispatch`의 recent transition 판정은 `updated_at` 기준의 로컬 시각 비교로 봐야 한다. UTC 기반 SQL `now` 비교를 쓰면 한국 시간 저장값과 어긋나 오래된 DONE/BLOCKED 티켓을 계속 최근 전이로 오인할 수 있다.
- `auto-dispatch`는 오케스트레이터 spawn 후 20초 안에 티켓이 안 닫혀도, DB가 `IN_PROGRESS/PENDING`이면 **진행 중**으로 취급하고 launchd hard-fail로 보지 않는다. 실제 실패는 close 상태가 비정상일 때만 본다.
- 따라서 **"일 안 하고 있는데 일 남음" 문제는 watchdog 단독이 아니라 auto-dispatch까지 포함해 봐야 한다.**
- 상위 집계 스크립트는 `scripts/heartbeat/main_brain_guard.py`로 구현한다. 이 스크립트는 `local_brain_guard`를 먼저 실행하되 이를 **advisory component**로만 기록하고, `openclaw status`의 Telegram `ON/OK`, `launchctl list`의 `local-brain-guard/watchdog/auto-dispatch` 라벨 상태, `runtime/tasks/watchdog.launchd.log`, `runtime/tasks/auto_dispatch_status.json`, `python3 scripts/context_policy.py resume-check --strict`를 묶어 단일 JSON/alert를 만든다.
- 예외적으로 watchdog가 `launchctl disabled` 상태이면서 `runtime/current-task.md`의 directive/notes/proof에서 **주인님 명시 pause 상태**가 확인되면, `main_brain_guard.py`는 watchdog missing/old log를 오탐으로 보지 않고 `checks.watchdog.paused=true`로 기록한다.

## 6. 설계 원칙
- 완전 통합보다 **역할 분리 + 상태/경고 통합**을 우선한다.
- heartbeat는 보고, local-brain-guard는 복구, watchdog/dispatch는 작업 재기동에 집중한다.
- 상위 메인브레인가드는 이 하위 가드들의 상태를 한 관점으로 묶어 판단한다.
- 문서상 정의와 실제 launchd/script 경로가 불일치하면 FAIL로 본다.

## 7. 운영 체크리스트
- `openclaw status`
- `launchctl list | grep -i 'openclaw\|watchdog\|dispatch'`
- `python3 scripts/watchdog/watchdog_validate.py`
- `python3 scripts/watchdog/watchdog_recover.py`
- `tail -n 50 runtime/tasks/watchdog.launchd.log`
- `cat runtime/tasks/auto_dispatch_status.json`
- `tail -n 50 runtime/tasks/auto_dispatch_debug.log`
- `python3 scripts/context_policy.py resume-check --strict`
- `python3 scripts/heartbeat/main_brain_guard.py`

`main_brain_guard.py` 출력은 단일 JSON이며, 최소 필드는 아래를 가진다.
- `ok`: 상위 메인브레인가드 최종 판정
- `summary`: `local_brain/telegram/watchdog/auto_dispatch/current_task`의 상태 요약(`local_brain`은 필요 시 `WARN`)
- `failed_components`: main FAIL에 반영되는 실패 컴포넌트 목록
- `advisory_components`: main FAIL에는 반영하지 않는 advisory 컴포넌트 목록
- `issues`: main FAIL 판정용 기계 판독 이유 목록
- `advisory_issues`: advisory 컴포넌트 이유 목록
- `alert`: heartbeat가 그대로 전달할 수 있는 메인 경고 문구
- `checks.*`: 세부 근거(JSON)

## 8. 채널 health-check 구현 상태
- 현재 상위 메인브레인가드는 `openclaw status`의 Channels 표에서 **Telegram이 `ON/OK`인지**를 1차 health-check로 본다.
- 이 값은 `main_brain_guard.py` JSON의 `checks.telegram.status`에 그대로 남기고, `ON`/`OK`가 아니면 즉시 FAIL로 집계한다.
- 아직 표준화된 "최근 송신 실패 이벤트" 파일/명령이 없어서, **실송신 self-check는 이번 구현 범위에서 보수적으로 제외**했다.
- 따라서 현 구현은 **채널 설정/연결 상태 확인**까지를 자동 판정 범위로 두고, 실송수신 검증은 후속 과제로 남긴다.
- 자동 복구는 수행하지 않는다. 채널 문제는 임의 재연결보다 **즉시 경고 + 수동 확인 유도**를 우선한다.

## 9. 서브에이전트 완료 callback 정책
- 장시간 실행 서브에이전트는 poll 기반 대기 대신 **완료 직전 `openclaw system event --mode now`** 로 메인을 깨운다.
- 서브를 붙인 직후 task에는 반드시 **nonterminal waiting phase** 를 남긴다. 기본은 `IN_PROGRESS` 유지이며, legacy `BLOCKED + waiting phase`도 hygiene 상 ongoing으로 취급하지만 신규 사용은 권장하지 않는다.
  - 예: `delegated_to_subagent`, `subagent_running`, `awaiting_callback`, `long_running_execution`
  - callback/child result 대기라면 deadline(`resume_due`)을 함께 기록한다. long-running active execution은 필요 시 heartbeat성 phase 갱신만 하고 `resume_due` 없이 유지할 수 있다.
- 메인은 이 이벤트를 받으면 같은 턴에서:
  1) child report 확인
  2) proof 반영
  3) task 상태 전이(DONE/REWORK/BLOCKED)
  를 즉시 처리한다.
- deadline을 넘겼는데 callback이 없으면 watchdog은 그때 `BLOCKED`로 승격한다. deadline 전에는 wait phase를 blocker로 취급하지 않는다.
- 기본 텍스트 형식 예시:
  - `SUBAGENT_DONE ticket=<id> summary=<brief>`

## 10. 후속 보강 과제
- 메인 채널(예: Telegram) 실제 송수신 health-check를 표준화
- 메인 세션 무응답/장기 무활동 기준 정의
- watchdog/dispatch가 최근 transition을 오래 끌고 가지 않도록 stale 판단을 엄격화
- main-brain-guard launchd 엔트리/heartbeat 보고 경로를 상위 집계 JSON 기준으로 정식 연결
