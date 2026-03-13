# JB-20260313-EVIDENCE-CARD-RUNTIME-REFORM

- ticket: JB-20260313-EVIDENCE-CARD-RUNTIME-REFORM
- status: DONE
- checked_at: 2026-03-13 14:12 KST

## Goal
logs/tmp/raw proof를 브레인의 기본 읽기 단위에서 격하하고, compact evidence card + proof index + slim current-task pointer 중심 런타임으로 개편한다.

## Reviewed design to apply
- L0 runtime canonical: current-task, context-handoff, task/directive summary
- L1 compact evidence card / proof index: 브레인이 기본 참조하는 유일 증거층
- L2 cold raw artifacts: tmp/log/raw stdout/stderr/full outputs, 기본 로드 금지

## Required implementation axes
1. closed task final evidence card 강제
2. proof index / canonical summary flag 도입
3. current-task slim pointer model
4. raw hot/warm/cold retention + archive/compaction
5. evidence search wrapper(canonical default, raw opt-in)
6. close/watchdog validation에서 evidence card missing 검출

## Landed vs Remaining (exact)
- landed:
  - terminal close path(`DONE`/terminal `BLOCKED`)에서 compact evidence card(`runtime/tasks/evidence/cards/<ticket>.json`) 자동 생성
  - proof index(`runtime/tasks/evidence/proof-index.jsonl`) 도입 및 `canonical_summary=true` 기록
  - close proof 포인터를 canonical evidence card로 정규화 (`proof` 필드)
  - raw/log/tmp reference를 hot/warm/cold JSONL manifest로 분류 기록 + non-destructive archive/compaction hook 기록
  - `python3 scripts/tasks/db.py evidence-search` 추가 (default canonical-only, `--include-raw` opt-in)
  - current-task/context-handoff 출력을 slim pointer 중심으로 정리 (`touched_paths`, `latest_proof`, `evidence_card`, `proof_index`)
  - watchdog validate/recover에 reform cutoff 이후 closed task evidence hygiene 검사 추가
  - context/operations policy 문서에 L0/L1/L2 canonical load tier 반영
- remaining:
  - 없음 (본 티켓 범위 내 구현 완료)

## Proof
- `PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m py_compile scripts/tasks/db.py scripts/tasks/record_task_event.py scripts/watchdog/watchdog_recover.py scripts/watchdog/watchdog_validate.py scripts/context_policy.py` → pass
- `python3 scripts/tasks/db.py --help` → `evidence-search` subcommand 노출 확인
- `python3 scripts/tasks/db.py evidence-search --limit 2` → canonical-only 기본 동작 JSON 확인
- `python3 scripts/watchdog/watchdog_validate.py` → bounded 실행(현 clone에 tasks db 부재로 expected fail payload 반환)
- `python3 scripts/watchdog/watchdog_recover.py` → bounded 실행(현 clone에 tasks db 부재로 expected fail payload 반환)
