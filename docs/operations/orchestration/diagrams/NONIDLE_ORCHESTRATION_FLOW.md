# NONIDLE ORCHESTRATION FLOW

상위 인덱스: `docs/operations/orchestration/README.md`

> status: diagram / explainer only
> canonical rules live in `TASKS.md`

```mermaid
flowchart TD
    A[ready task in pool] --> B[assign-pool / dispatch_tick]
    B --> C[orchestrator picks assigned ticket]

    C --> D{inline finish 가능?}
    D -- yes --> E[task proof update]
    E --> F[terminal close<br/>DONE / REWORK / BLOCKED(real blocker)]

    D -- no --> G[launch background program / subagent / watcher]
    G --> H[record_task_event or mark-phase]
    H --> I[IN_PROGRESS + nonterminal waiting phase<br/>resume_due set if needed]
    I --> J[release assignee/run metadata]
    J --> K[dispatcher keeps worker slot free]
    K --> L[other ready task can be assigned]

    G --> M[background progress / completion event]
    M --> N[same task_id proof sync]
    N --> O[phase becomes main_resume or equivalent]
    O --> P[main picks task again]
    P --> Q[review / finalize / close]

    I -. deadline exceeded .-> R[watchdog promotes to BLOCKED]
```

## reading note
- 사각형 `I`가 detached waiting의 핵심이다.
- 이 상태는 ongoing이지만, worker slot은 `J`에서 풀린다.
- 따라서 메인은 `L` 경로로 다음 ready task를 계속 집을 수 있다.
