# Stage1 Docs

Stage1 문서는 **문서만 보고도 동일한 Stage1 동작을 재구현할 수 있는 수준**을 목표로 유지한다.
개요/색인/운영/계약/appendix 역할은 아래 5개 파일로 고정한다.

## 문서 역할 고정 템플릿
| 파일 | 상태 | 역할 | 업데이트 규칙 |
| --- | --- | --- | --- |
| `README.md` | canonical index | Stage1 개요/빠른 진입/문서 역할 안내 | 요약/링크만 유지, 상세 규칙 중복 금지 |
| `RUNBOOK.md` | canonical operations SSOT | 실행 명령, 환경변수, fallback, coverage 보고, 운영 절차 | 운영 동작이 바뀌면 먼저 여기 반영 |
| `STAGE1_RULEBOOK_AND_REPRO.md` | canonical stage contract | 재현 가능한 Stage1 계약: profile, gate, runtime status, pass/fail 기준 | orchestration/gate/runtime 계약이 바뀌면 여기 반영 |
| `stage01_data_collection.md` | canonical raw appendix | collector ↔ output path/source map + raw artifact 최소 스키마 | 원천/산출 포맷이 바뀌면 여기 반영 |
| `TODO.md` | tracked backlog | 미해결 운영 이슈와 후속 점검 목록 | 해결 전/후 상태만 추적, 실행 SSOT 금지 |

## 문서 충돌 해소 규칙
- 실행 명령/환경변수/폴백/launchd 절차 충돌 시 `RUNBOOK.md` 우선
- Stage1 범위/입력/출력/검증/프로파일/게이트 계약은 `STAGE1_RULEBOOK_AND_REPRO.md` 우선
- collector별 raw 경로와 **최소 파일 스키마**는 `stage01_data_collection.md` 우선
- 미해결 TODO는 `TODO.md`에만 남긴다

## Stage1 한 줄 요약
- 역할: 외부 원천을 수집해 `master/raw/runtime/logs/reports` 기준선을 만든다.
- 진입점: `invest/stages/stage1/scripts/stage01_daily_update.py`
- 체인 진입점: `invest/stages/stage1/scripts/launchd/run_stage1234_chain.sh`
- 필수 게이트: `stage01_checkpoint_gate.py` → `stage01_post_collection_validate.py`
- Stage2 경계: Stage1은 **clean/quarantine를 만들지 않는다.**

## 바로가기
- [STAGE1_RULEBOOK_AND_REPRO.md](./STAGE1_RULEBOOK_AND_REPRO.md)
- [RUNBOOK.md](./RUNBOOK.md)
- [stage01_data_collection.md](./stage01_data_collection.md)
- [TODO.md](./TODO.md)
- raw coverage index: `invest/stages/stage1/outputs/raw/source_coverage_index.json`
